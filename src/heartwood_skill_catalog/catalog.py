# This source file is part of the Heartwood Skills open-source project
#
# SPDX-FileCopyrightText: 2026 Stanford University and the project authors
#
# SPDX-License-Identifier: MIT

"""Validate complete Agent Skill trees and build reproducible catalog targets."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import ClassVar, Literal, cast

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")

from openhands.sdk.skills import Skill
from openhands.sdk.skills.exceptions import SkillError
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from yaml import YAMLError

_MAX_FILES = 256
_MAX_FILE_BYTES = 8 * 1024 * 1024
_MAX_TOTAL_BYTES = 64 * 1024 * 1024
_MAX_ARCHIVE_BYTES = 72 * 1024 * 1024
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
_REPOSITORY_PATTERN = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_HEARTWOOD_KEYS = {
    "heartwood.approval-summary",
    "heartwood.controlled-data",
    "heartwood.dataset-types",
    "heartwood.entrypoint",
    "heartwood.id",
    "heartwood.phi-risk",
    "heartwood.platforms",
    "heartwood.requires-network",
    "heartwood.version",
}


class CatalogBuildError(ValueError):
    """Raised when curated Skill content cannot produce a trusted catalog target."""


class _Record(BaseModel):
    """Strict immutable base model for generated catalog records."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)


class SkillFile(_Record):
    """One regular file covered by the canonical Skill tree digest."""

    path: str = Field(min_length=1)
    size: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)
    role: Literal["definition", "script", "reference", "asset", "mcp-config", "other"]
    executable: bool

    @field_validator("path")
    @classmethod
    def _path_is_safe(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError("Skill file path must be clean and relative")
        return value

    @field_validator("sha256")
    @classmethod
    def _hash_is_sha256(cls, value: str) -> str:
        normalized = value.lower()
        if not _SHA256_PATTERN.fullmatch(normalized):
            raise ValueError("Skill file hash must be SHA-256")
        return normalized


class SkillPolicy(_Record):
    """Heartwood policy declarations embedded in standard Agent Skills metadata."""

    schema_version: Literal["heartwood.skill-policy.v1"] = "heartwood.skill-policy.v1"
    skill_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    dataset_types: tuple[str, ...] = Field(min_length=1)
    platforms: tuple[str, ...] = Field(min_length=1)
    phi_risk: Literal["none", "reads-phi", "writes-outside-boundary"]
    requires_network: bool
    controlled_data: Literal["not-approved", "deployment-approved"]
    approval_summary: str = Field(min_length=1, max_length=500)
    entrypoint: str | None = None

    @field_validator("version")
    @classmethod
    def _version_is_semver(cls, value: str) -> str:
        if not _SEMVER_PATTERN.fullmatch(value):
            raise ValueError("Skill version must use Semantic Versioning")
        return value

    @field_validator("entrypoint")
    @classmethod
    def _entrypoint_is_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        path = PurePosixPath(value)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError("Skill entrypoint must be clean and relative")
        return value


class CatalogEntry(_Record):
    """One reviewed, immutable Agent Skill artifact in the generated catalog."""

    schema_version: Literal["heartwood.skill-catalog-entry.v1"] = "heartwood.skill-catalog-entry.v1"
    name: str = Field(min_length=1)
    description: str = Field(min_length=1, max_length=1024)
    license: str = Field(min_length=1)
    compatibility: str | None = None
    policy: SkillPolicy
    allowed_tools: tuple[str, ...]
    mcp_servers: tuple[str, ...]
    dynamic_context: bool
    files: tuple[SkillFile, ...] = Field(min_length=1)
    tree_sha256: str = Field(min_length=64, max_length=64)
    archive_sha256: str = Field(min_length=64, max_length=64)
    archive_size: int = Field(gt=0)
    target: str = Field(min_length=1)
    source_repository: str = Field(min_length=1)
    source_revision: str = Field(min_length=40, max_length=40)
    review: Literal["repository-reviewed"] = "repository-reviewed"
    controlled_data_ready: bool = False
    revoked: bool = False
    revocation_reason: str | None = None

    @field_validator("tree_sha256", "archive_sha256")
    @classmethod
    def _digest_is_sha256(cls, value: str) -> str:
        normalized = value.lower()
        if not _SHA256_PATTERN.fullmatch(normalized):
            raise ValueError("Catalog digest must be SHA-256")
        return normalized

    @field_validator("target")
    @classmethod
    def _target_is_safe(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError("Catalog target must be clean and relative")
        return value

    @field_validator("source_repository")
    @classmethod
    def _repository_is_https_github(cls, value: str) -> str:
        if not _REPOSITORY_PATTERN.fullmatch(value):
            raise ValueError("Source repository must be an HTTPS GitHub repository URL")
        return value

    @field_validator("source_revision")
    @classmethod
    def _revision_is_commit(cls, value: str) -> str:
        normalized = value.lower()
        if not _REVISION_PATTERN.fullmatch(normalized):
            raise ValueError("Source revision must be a full Git commit hash")
        return normalized

    @model_validator(mode="after")
    def _controlled_data_claim_has_policy_evidence(self) -> CatalogEntry:
        if self.controlled_data_ready != (self.policy.controlled_data == "deployment-approved"):
            raise ValueError("Controlled-data catalog status and Skill policy must agree")
        if self.revoked and not self.revocation_reason:
            raise ValueError("Revoked catalog entries require a reason")
        if not self.revoked and self.revocation_reason is not None:
            raise ValueError("Active catalog entries cannot declare a revocation reason")
        return self


class CatalogDocument(_Record):
    """Generated catalog target signed and distributed through TUF."""

    schema_version: Literal["heartwood.skill-catalog.v1"] = "heartwood.skill-catalog.v1"
    entries: tuple[CatalogEntry, ...]

    @model_validator(mode="after")
    def _identities_are_unique(self) -> CatalogDocument:
        names = [entry.name for entry in self.entries]
        skill_ids = [entry.policy.skill_id for entry in self.entries]
        if len(names) != len(set(names)):
            raise ValueError("Catalog contains duplicate Skill names")
        if len(skill_ids) != len(set(skill_ids)):
            raise ValueError("Catalog contains duplicate Skill identifiers")
        return self


class _InspectedSkill(_Record):
    """Validated source tree before deterministic packaging."""

    root: Path
    name: str
    description: str
    license: str
    compatibility: str | None
    policy: SkillPolicy
    allowed_tools: tuple[str, ...]
    mcp_servers: tuple[str, ...]
    dynamic_context: bool
    files: tuple[SkillFile, ...]
    tree_sha256: str


def inspect_skill(skill_root: Path) -> _InspectedSkill:
    """Validate one complete Agent Skill directory without executing bundled code."""
    root = skill_root.resolve()
    skill_path = root / "SKILL.md"
    if not root.is_dir() or not skill_path.is_file():
        raise CatalogBuildError(f"Skill is missing SKILL.md: {skill_root}")
    try:
        skill = Skill.load(skill_path, strict=True)
    except (OSError, SkillError, ValidationError, ValueError, YAMLError) as error:
        raise CatalogBuildError(f"OpenHands rejected Skill {skill_root.name}: {error}") from error
    if not skill.is_agentskills_format:
        raise CatalogBuildError(f"Skill does not use the Agent Skills format: {skill_root.name}")
    if not skill.description:
        raise CatalogBuildError(f"Skill description is required: {skill_root.name}")
    if not skill.license:
        raise CatalogBuildError(f"Skill license is required: {skill_root.name}")

    metadata = skill.metadata or {}
    missing = sorted(_HEARTWOOD_KEYS - metadata.keys())
    if missing:
        raise CatalogBuildError(
            f"Skill {skill.name} is missing Heartwood metadata: {', '.join(missing)}"
        )
    try:
        policy = SkillPolicy(
            skill_id=_required(metadata, "heartwood.id"),
            version=_required(metadata, "heartwood.version"),
            dataset_types=_csv(metadata, "heartwood.dataset-types"),
            platforms=_csv(metadata, "heartwood.platforms"),
            phi_risk=cast(
                Literal["none", "reads-phi", "writes-outside-boundary"],
                _required(metadata, "heartwood.phi-risk"),
            ),
            requires_network=_boolean(metadata, "heartwood.requires-network"),
            controlled_data=cast(
                Literal["not-approved", "deployment-approved"],
                _required(metadata, "heartwood.controlled-data"),
            ),
            approval_summary=_required(metadata, "heartwood.approval-summary"),
            entrypoint=_optional(metadata, "heartwood.entrypoint"),
        )
    except ValidationError as error:
        raise CatalogBuildError(f"Skill {skill.name} has invalid Heartwood metadata") from error

    files = _scan_tree(root)
    paths = {item.path for item in files}
    if policy.entrypoint is not None and policy.entrypoint not in paths:
        raise CatalogBuildError(f"Skill entrypoint does not exist: {policy.entrypoint}")
    dynamic_context = "!`" in skill_path.read_text(encoding="utf-8")
    mcp_servers = tuple(sorted((skill.mcp_tools or {}).keys()))
    if dynamic_context:
        raise CatalogBuildError(
            f"Skill {skill.name} uses automatic dynamic shell context, which is not curated"
        )
    if mcp_servers:
        raise CatalogBuildError(
            f"Skill {skill.name} embeds MCP servers; curated MCP policy is not configured"
        )
    return _InspectedSkill(
        root=root,
        name=skill.name,
        description=skill.description,
        license=skill.license,
        compatibility=skill.compatibility,
        policy=policy,
        allowed_tools=tuple(skill.allowed_tools or ()),
        mcp_servers=mcp_servers,
        dynamic_context=dynamic_context,
        files=files,
        tree_sha256=_tree_digest(files),
    )


def build_catalog(
    skills_root: Path,
    output_root: Path,
    *,
    source_repository: str,
    source_revision: str,
) -> CatalogDocument:
    """Build deterministic Skill archives and a canonical catalog target."""
    source_root = skills_root.resolve()
    if not source_root.is_dir():
        raise CatalogBuildError(f"Skills root does not exist: {skills_root}")
    inspected = tuple(
        inspect_skill(path) for path in sorted(source_root.iterdir()) if path.is_dir()
    )
    if not inspected:
        raise CatalogBuildError("Skills root does not contain any Skill directories")

    destination = output_root.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        entries: list[CatalogEntry] = []
        for skill in inspected:
            target = (
                PurePosixPath("skills")
                / skill.name
                / skill.policy.version
                / f"{skill.tree_sha256}.zip"
            )
            archive = staging / target
            archive.parent.mkdir(parents=True, exist_ok=True)
            _write_archive(skill, archive)
            archive_bytes = archive.read_bytes()
            entries.append(
                CatalogEntry(
                    name=skill.name,
                    description=skill.description,
                    license=skill.license,
                    compatibility=skill.compatibility,
                    policy=skill.policy,
                    allowed_tools=skill.allowed_tools,
                    mcp_servers=skill.mcp_servers,
                    dynamic_context=skill.dynamic_context,
                    files=skill.files,
                    tree_sha256=skill.tree_sha256,
                    archive_sha256=hashlib.sha256(archive_bytes).hexdigest(),
                    archive_size=len(archive_bytes),
                    target=target.as_posix(),
                    source_repository=source_repository,
                    source_revision=source_revision,
                    controlled_data_ready=(skill.policy.controlled_data == "deployment-approved"),
                )
            )
        document = CatalogDocument(entries=tuple(sorted(entries, key=lambda item: item.name)))
        catalog_path = staging / "catalog.json"
        catalog_path.write_text(
            json.dumps(
                document.model_dump(mode="json"),
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        if destination.exists():
            shutil.rmtree(destination)
        staging.replace(destination)
        return document
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def extract_skill_archive(entry: CatalogEntry, archive_path: Path, destination: Path) -> Path:
    """Verify and atomically extract one catalog archive into a new Skill directory."""
    source = archive_path.resolve()
    if not source.is_file():
        raise CatalogBuildError(f"Skill archive does not exist: {archive_path}")
    archive_size = source.stat().st_size
    if archive_size != entry.archive_size or archive_size > _MAX_ARCHIVE_BYTES:
        raise CatalogBuildError("Skill archive size does not match the signed catalog")
    if _file_digest(source) != entry.archive_sha256:
        raise CatalogBuildError("Skill archive digest does not match the signed catalog")

    target = destination.resolve()
    if target.exists():
        raise CatalogBuildError(f"Skill destination already exists: {destination}")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging_parent = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=target.parent))
    staging = staging_parent / entry.name
    staging.mkdir()
    expected = {f"{entry.name}/{item.path}": item for item in entry.files}
    try:
        with zipfile.ZipFile(source) as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            if len(names) != len(set(names)) or len(names) != len(
                {name.casefold() for name in names}
            ):
                raise CatalogBuildError("Skill archive contains duplicate paths")
            if set(names) != set(expected):
                raise CatalogBuildError("Skill archive contents do not match the signed catalog")
            for member in members:
                record = expected[member.filename]
                mode = member.external_attr >> 16
                if member.is_dir() or not stat.S_ISREG(mode):
                    raise CatalogBuildError(
                        f"Skill archive member is not a regular file: {member.filename}"
                    )
                if member.file_size != record.size or member.file_size > _MAX_FILE_BYTES:
                    raise CatalogBuildError(
                        "Skill archive member size does not match the signed catalog: "
                        f"{member.filename}"
                    )
                relative = PurePosixPath(record.path)
                output = staging.joinpath(*relative.parts)
                output.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                written = 0
                with archive.open(member) as input_file, output.open("xb") as output_file:
                    while chunk := input_file.read(1024 * 1024):
                        written += len(chunk)
                        if written > record.size:
                            raise CatalogBuildError(
                                f"Skill archive member exceeds its declared size: {member.filename}"
                            )
                        digest.update(chunk)
                        output_file.write(chunk)
                if written != record.size or digest.hexdigest() != record.sha256:
                    raise CatalogBuildError(
                        "Skill archive member digest does not match the signed catalog: "
                        f"{member.filename}"
                    )
                output.chmod(0o755 if record.executable else 0o644)
        extracted = inspect_skill(staging)
        if extracted.tree_sha256 != entry.tree_sha256 or extracted.name != entry.name:
            raise CatalogBuildError("Extracted Skill identity does not match the signed catalog")
        staging.replace(target)
        staging_parent.rmdir()
        return target
    except (CatalogBuildError, OSError, zipfile.BadZipFile):
        shutil.rmtree(staging_parent, ignore_errors=True)
        raise


def _scan_tree(root: Path) -> tuple[SkillFile, ...]:
    records: list[SkillFile] = []
    normalized_paths: set[str] = set()
    total_size = 0
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part == ".git" for part in relative.parts):
            raise CatalogBuildError("Skill trees cannot contain Git metadata")
        file_stat = path.lstat()
        if stat.S_ISDIR(file_stat.st_mode):
            continue
        if stat.S_ISLNK(file_stat.st_mode) or not stat.S_ISREG(file_stat.st_mode):
            raise CatalogBuildError(f"Skill trees may contain only regular files: {relative}")
        if file_stat.st_nlink != 1:
            raise CatalogBuildError(f"Skill files cannot be hard linked: {relative}")
        if file_stat.st_size > _MAX_FILE_BYTES:
            raise CatalogBuildError(f"Skill file exceeds {_MAX_FILE_BYTES} bytes: {relative}")
        total_size += file_stat.st_size
        if total_size > _MAX_TOTAL_BYTES:
            raise CatalogBuildError(f"Skill tree exceeds {_MAX_TOTAL_BYTES} bytes: {root.name}")
        if len(records) >= _MAX_FILES:
            raise CatalogBuildError(f"Skill tree exceeds {_MAX_FILES} files: {root.name}")
        content = path.read_bytes()
        relative_posix = relative.as_posix()
        normalized_path = relative_posix.casefold()
        if normalized_path in normalized_paths:
            raise CatalogBuildError(f"Skill tree contains duplicate paths: {relative_posix}")
        normalized_paths.add(normalized_path)
        executable = bool(file_stat.st_mode & 0o111)
        if executable and relative.parts[0] != "scripts":
            raise CatalogBuildError(
                f"Executable files must be contained in scripts/: {relative_posix}"
            )
        records.append(
            SkillFile(
                path=relative_posix,
                size=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
                role=_file_role(relative),
                executable=executable,
            )
        )
    if "SKILL.md" not in {record.path for record in records}:
        raise CatalogBuildError(f"Skill tree is missing its regular SKILL.md: {root.name}")
    return tuple(records)


def _tree_digest(files: Sequence[SkillFile]) -> str:
    payload = [item.model_dump(mode="json") for item in files]
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _write_archive(skill: _InspectedSkill, destination: Path) -> None:
    with zipfile.ZipFile(
        destination,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        for item in skill.files:
            source = skill.root / PurePosixPath(item.path)
            info = zipfile.ZipInfo(f"{skill.name}/{item.path}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            mode = 0o755 if item.executable else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            archive.writestr(info, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)


def _file_role(
    path: Path,
) -> Literal["definition", "script", "reference", "asset", "mcp-config", "other"]:
    if path.as_posix() == "SKILL.md":
        return "definition"
    if path.as_posix() == ".mcp.json":
        return "mcp-config"
    top = path.parts[0]
    if top == "scripts":
        return "script"
    if top == "references":
        return "reference"
    if top == "assets":
        return "asset"
    return "other"


def _required(metadata: Mapping[str, str], key: str) -> str:
    value = metadata.get(key, "").strip()
    if not value:
        raise CatalogBuildError(f"Skill metadata requires {key}")
    return value


def _optional(metadata: Mapping[str, str], key: str) -> str | None:
    value = metadata.get(key)
    if value is None or not value.strip():
        return None
    return value.strip()


def _csv(metadata: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(part.strip() for part in _required(metadata, key).split(",") if part.strip())
    if not values:
        raise CatalogBuildError(f"Skill metadata requires at least one {key} value")
    return values


def _boolean(metadata: Mapping[str, str], key: str) -> bool:
    value = _required(metadata, key).lower()
    if value == "true":
        return True
    if value == "false":
        return False
    raise CatalogBuildError(f"Skill metadata {key} must be true or false")
