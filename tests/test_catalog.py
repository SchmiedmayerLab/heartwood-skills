# This source file is part of the Heartwood Skills open-source project
#
# SPDX-FileCopyrightText: 2026 Stanford University and the project authors (see CONTRIBUTORS.md)
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from heartwood_skill_catalog import (
    CatalogBuildError,
    CatalogDocument,
    CatalogEntry,
    SkillFile,
    SkillPolicy,
    SkillRevocation,
    SkillRevocationSet,
    build_catalog,
    copy_skill_tree,
    extract_skill_archive,
    inspect_skill,
    load_revocations,
)
from heartwood_skill_catalog import catalog as catalog_module
from heartwood_skill_catalog.cli import _git_snapshot, main

_SKILLS = Path("skills/verified")
_REPOSITORY = "https://github.com/SchmiedmayerLab/heartwood-skills"
_REVISION = "a" * 40


def _copy_skill(tmp_path: Path, name: str = "aggregate-export") -> Path:
    root = tmp_path / name
    shutil.copytree(_SKILLS / name, root)
    return root


def _git_catalog_repository(tmp_path: Path) -> tuple[Path, Path, str]:
    repository = tmp_path / "repository"
    skills = repository / "skills/verified"
    shutil.copytree(_SKILLS, skills)
    (repository / "revocations.toml").write_text(
        'schema_version = "heartwood.skill-revocations.v1"\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "--quiet", str(repository)], check=True)
    subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "-c",
            "user.name=Heartwood Tests",
            "-c",
            "user.email=tests@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-m",
            "Create test repository",
        ],
        check=True,
    )
    revision = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return repository, skills, revision


def test_catalog_models_do_not_eagerly_import_openhands() -> None:
    completed = subprocess.run(
        (
            sys.executable,
            "-c",
            "import sys; import heartwood_skill_catalog; assert 'openhands.sdk' not in sys.modules",
        ),
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def _replace(root: Path, old: str, new: str) -> None:
    path = root / "SKILL.md"
    path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")


def _catalog_entry(tmp_path: Path) -> tuple[CatalogEntry, Path]:
    output = tmp_path / "catalog"
    document = build_catalog(
        _SKILLS,
        output,
        source_repository=_REPOSITORY,
        source_revision=_REVISION,
    )
    entry = next(item for item in document.entries if item.name == "aggregate-export")
    return entry, output / entry.target


def _entry_for_archive(entry: CatalogEntry, archive: Path) -> CatalogEntry:
    content = archive.read_bytes()
    return entry.model_copy(
        update={"archive_sha256": hashlib.sha256(content).hexdigest(), "archive_size": len(content)}
    )


def test_all_curated_skills_load_through_openhands_with_complete_resources() -> None:
    inspected = {path.name: inspect_skill(path) for path in sorted(_SKILLS.iterdir())}

    assert set(inspected) == {"aggregate-export", "baseline-model", "omop-cohort-summary"}
    assert inspected["aggregate-export"].policy.entrypoint == "scripts/run.py"
    assert {item.role for item in inspected["aggregate-export"].files} == {
        "asset",
        "definition",
        "script",
    }
    assert "reference" in {item.role for item in inspected["baseline-model"].files}
    assert all(item.sha256 != "0" * 64 for skill in inspected.values() for item in skill.files)
    assert all(skill.allowed_tools == ("terminal",) for skill in inspected.values())
    assert all(skill.policy.controlled_data == "not-approved" for skill in inspected.values())
    assert inspected["aggregate-export"].policy.phi_risk == "none"
    assert inspected["baseline-model"].policy.phi_risk == "reads-phi"
    assert inspected["omop-cohort-summary"].policy.phi_risk == "reads-phi"


def test_catalog_build_is_deterministic_and_archives_the_complete_skill_tree(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_document = build_catalog(
        _SKILLS,
        first,
        source_repository=_REPOSITORY,
        source_revision=_REVISION,
    )
    second_document = build_catalog(
        _SKILLS,
        second,
        source_repository=_REPOSITORY,
        source_revision=_REVISION,
    )

    assert first_document == second_document
    assert (first / "catalog.json").read_bytes() == (second / "catalog.json").read_bytes()
    assert first_document.entries == tuple(
        sorted(first_document.entries, key=lambda item: item.name)
    )
    for entry in first_document.entries:
        first_archive = first / entry.target
        second_archive = second / entry.target
        assert first_archive.read_bytes() == second_archive.read_bytes()
        assert entry.archive_size == first_archive.stat().st_size
        with zipfile.ZipFile(first_archive) as archive:
            assert sorted(archive.namelist()) == sorted(
                f"{entry.name}/{item.path}" for item in entry.files
            )
            for member in archive.infolist():
                mode = member.external_attr >> 16
                assert stat.S_ISREG(mode)
                assert mode & 0o022 == 0
                assert member.date_time == (1980, 1, 1, 0, 0, 0)

    payload = json.loads((first / "catalog.json").read_text(encoding="utf-8"))
    assert CatalogDocument.model_validate(payload) == first_document


def test_build_replaces_an_existing_output_atomically(tmp_path: Path) -> None:
    output = tmp_path / "catalog"
    output.mkdir()
    (output / "stale").write_text("stale", encoding="utf-8")

    build_catalog(
        _SKILLS,
        output,
        source_repository=_REPOSITORY,
        source_revision=_REVISION,
    )

    assert not (output / "stale").exists()
    assert (output / "catalog.json").is_file()


def test_catalog_archive_extracts_atomically_and_revalidates_openhands(tmp_path: Path) -> None:
    entry, archive = _catalog_entry(tmp_path)
    destination = tmp_path / "installed" / entry.name

    assert extract_skill_archive(entry, archive, destination) == destination.resolve()
    inspected = inspect_skill(destination)
    assert inspected.tree_sha256 == entry.tree_sha256
    assert not (destination / "scripts" / "run.py").stat().st_mode & stat.S_IXUSR
    assert not (destination / "SKILL.md").stat().st_mode & stat.S_IXUSR

    with pytest.raises(CatalogBuildError, match="already exists"):
        extract_skill_archive(entry, archive, destination)


def test_local_skill_copy_is_atomic_and_detects_source_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _copy_skill(tmp_path / "source")
    destination = tmp_path / "installed" / source.name
    assert copy_skill_tree(source, destination) == destination.resolve()
    assert inspect_skill(destination).tree_sha256 == inspect_skill(source).tree_sha256
    with pytest.raises(CatalogBuildError, match="changed after review"):
        copy_skill_tree(
            source,
            tmp_path / "digest-mismatch" / source.name,
            expected_tree_sha256="0" * 64,
        )

    changing_source = _copy_skill(tmp_path / "changing")
    changed_file = changing_source / "assets" / "output-schema.json"
    changed_file_resolved = changed_file.resolve()
    original_open = catalog_module._open_source_file
    replaced = False

    def replace_before_open(
        path: Path,
        flags: int,
    ) -> int:
        nonlocal replaced
        candidate = Path(path).resolve()
        if candidate == changed_file_resolved and not replaced:
            replaced = True
            content = changed_file.read_bytes()
            changed_file.unlink()
            changed_file.write_bytes(content)
        return original_open(path, flags)

    monkeypatch.setattr(catalog_module, "_open_source_file", replace_before_open)
    with pytest.raises(CatalogBuildError, match="changed during"):
        copy_skill_tree(changing_source, tmp_path / "rejected" / changing_source.name)
    assert not (tmp_path / "rejected" / changing_source.name).exists()


def test_bounded_skill_reads_reject_open_failure_growth_and_post_read_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _copy_skill(tmp_path)
    skill_file = source / "SKILL.md"
    relative = Path("SKILL.md")
    original_open = catalog_module._open_source_file

    def fail_open(_path: Path, _flags: int) -> int:
        raise PermissionError("synthetic denial")

    monkeypatch.setattr(catalog_module, "_open_source_file", fail_open)
    with pytest.raises(CatalogBuildError, match="Unable to open Skill file safely"):
        catalog_module._read_bounded_regular_file(skill_file, relative)

    linked = tmp_path / "linked-skill.md"
    linked.symlink_to(skill_file)
    with pytest.raises(CatalogBuildError, match="only regular files"):
        catalog_module._read_bounded_regular_file(linked, relative)

    monkeypatch.setattr(catalog_module, "_open_source_file", original_open)
    original_size = skill_file.stat().st_size
    monkeypatch.setattr(catalog_module, "_MAX_FILE_BYTES", original_size)
    grew = False

    def grow_before_open(path: Path, flags: int) -> int:
        nonlocal grew
        if not grew:
            grew = True
            with path.open("ab") as file:
                file.write(b"x")
        return original_open(path, flags)

    monkeypatch.setattr(catalog_module, "_open_source_file", grow_before_open)
    with pytest.raises(CatalogBuildError, match="Skill file exceeds"):
        catalog_module._read_bounded_regular_file(skill_file, relative)

    skill_file.write_bytes(skill_file.read_bytes()[:-1])
    monkeypatch.setattr(catalog_module, "_MAX_FILE_BYTES", catalog_module._MAX_TOTAL_BYTES)
    monkeypatch.setattr(catalog_module, "_open_source_file", original_open)
    original_read = os.read
    touched = False

    def touch_after_read(descriptor: int, size: int) -> bytes:
        nonlocal touched
        content = original_read(descriptor, size)
        if content and not touched:
            touched = True
            metadata = skill_file.stat()
            os.utime(
                skill_file,
                ns=(metadata.st_atime_ns, metadata.st_mtime_ns + 1_000_000),
            )
        return content

    monkeypatch.setattr(os, "read", touch_after_read)
    with pytest.raises(CatalogBuildError, match="changed during inspection"):
        catalog_module._read_bounded_regular_file(skill_file, relative)


def test_catalog_packaging_rejects_content_changed_after_inspection(tmp_path: Path) -> None:
    source = _copy_skill(tmp_path)
    inspected = inspect_skill(source)
    script = source / "scripts/run.py"
    content = script.read_bytes()
    changed = content.replace(b"aggregate export", b"aggregate output", 1)
    assert changed != content, "Fixture no longer contains the expected marker"
    script.write_bytes(changed)

    with pytest.raises(CatalogBuildError, match="changed before packaging"):
        catalog_module._write_archive(inspected, tmp_path / "changed.zip")


def test_catalog_archive_rejects_missing_or_substituted_content(tmp_path: Path) -> None:
    entry, archive = _catalog_entry(tmp_path)
    with pytest.raises(CatalogBuildError, match="does not exist"):
        extract_skill_archive(entry, tmp_path / "missing.zip", tmp_path / "missing")

    substituted = tmp_path / "substituted.zip"
    substituted.write_bytes(archive.read_bytes() + b"substitution")
    with pytest.raises(CatalogBuildError, match="size"):
        extract_skill_archive(entry, substituted, tmp_path / "substituted")

    same_size = tmp_path / "same-size.zip"
    content = bytearray(archive.read_bytes())
    content[len(content) // 2] ^= 1
    same_size.write_bytes(content)
    with pytest.raises(CatalogBuildError, match="digest"):
        extract_skill_archive(entry, same_size, tmp_path / "same-size")


@pytest.mark.parametrize("member_name", ["escape.txt", "Aggregate-Export/SKILL.md"])
def test_catalog_archive_rejects_extra_and_case_colliding_paths(
    tmp_path: Path,
    member_name: str,
) -> None:
    entry, archive = _catalog_entry(tmp_path)
    malicious = tmp_path / "malicious.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(malicious, "w") as output:
        for member in source.infolist():
            output.writestr(member, source.read(member))
        output.writestr(member_name, b"untrusted")

    with pytest.raises(CatalogBuildError, match=r"contents|duplicate"):
        extract_skill_archive(
            _entry_for_archive(entry, malicious),
            malicious,
            tmp_path / "installed",
        )
    assert not (tmp_path / "installed").exists()


def test_catalog_archive_rejects_non_regular_members_and_manifest_mismatches(
    tmp_path: Path,
) -> None:
    entry, archive = _catalog_entry(tmp_path)
    malicious = tmp_path / "symlink.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(malicious, "w") as output:
        for member in source.infolist():
            if member.filename.endswith("SKILL.md"):
                member.external_attr = (stat.S_IFLNK | 0o777) << 16
            output.writestr(member, source.read(member))
    with pytest.raises(CatalogBuildError, match="not a regular file"):
        extract_skill_archive(
            _entry_for_archive(entry, malicious), malicious, tmp_path / "symlinked"
        )

    changed = tmp_path / "changed.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(changed, "w") as output:
        for member in source.infolist():
            content = source.read(member)
            if member.filename.endswith("SKILL.md"):
                content = bytes([content[0] ^ 1]) + content[1:]
            output.writestr(member, content)
    with pytest.raises(CatalogBuildError, match="digest"):
        extract_skill_archive(_entry_for_archive(entry, changed), changed, tmp_path / "changed")

    wrong_tree = entry.model_copy(update={"tree_sha256": "f" * 64})
    with pytest.raises(CatalogBuildError, match="identity"):
        extract_skill_archive(wrong_tree, archive, tmp_path / "wrong-tree")


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('  heartwood.version: "1.0.0"\n', "", "missing Heartwood metadata"),
        ('heartwood.version: "1.0.0"', 'heartwood.version: "01.0.0"', "invalid"),
        (
            'heartwood.requires-network: "false"',
            'heartwood.requires-network: "maybe"',
            "true or false",
        ),
        (
            'heartwood.entrypoint: "scripts/run.py"',
            'heartwood.entrypoint: "scripts/missing.py"',
            "entrypoint does not exist",
        ),
    ],
)
def test_invalid_policy_metadata_fails_closed(
    tmp_path: Path,
    old: str,
    new: str,
    message: str,
) -> None:
    root = _copy_skill(tmp_path)
    _replace(root, old, new)

    with pytest.raises(CatalogBuildError, match=message):
        inspect_skill(root)


def test_active_skill_extensions_fail_closed(tmp_path: Path) -> None:
    dynamic = _copy_skill(tmp_path / "dynamic")
    skill_path = dynamic / "SKILL.md"
    skill_path.write_text(
        skill_path.read_text(encoding="utf-8") + "\nCurrent state: !`git status`\n",
        encoding="utf-8",
    )
    with pytest.raises(CatalogBuildError, match="dynamic shell context"):
        inspect_skill(dynamic)

    mcp = _copy_skill(tmp_path / "mcp")
    (mcp / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "synthetic": {
                        "command": "python",
                        "args": ["-c", "print('not executed')"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(CatalogBuildError, match="embeds MCP servers"):
        inspect_skill(mcp)


def test_instruction_only_skill_does_not_require_an_entrypoint(tmp_path: Path) -> None:
    root = _copy_skill(tmp_path)
    _replace(root, '  heartwood.entrypoint: "scripts/run.py"\n', "")

    inspected = inspect_skill(root)

    assert inspected.policy.entrypoint is None


def test_non_regular_or_unsafe_skill_content_fails_closed(tmp_path: Path) -> None:
    linked = _copy_skill(tmp_path / "linked")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    (linked / "assets" / "linked.txt").symlink_to(outside)
    with pytest.raises(CatalogBuildError, match="regular files"):
        inspect_skill(linked)

    executable = _copy_skill(tmp_path / "executable")
    asset = executable / "assets" / "output-schema.json"
    asset.chmod(asset.stat().st_mode | stat.S_IXUSR)
    with pytest.raises(CatalogBuildError, match="Executable files"):
        inspect_skill(executable)

    hard_linked = _copy_skill(tmp_path / "hard-linked")
    os.link(hard_linked / "SKILL.md", hard_linked / "duplicate.md")
    with pytest.raises(CatalogBuildError, match="hard linked"):
        inspect_skill(hard_linked)


def test_catalog_models_reject_inconsistent_revocation(tmp_path: Path) -> None:
    document = build_catalog(
        _SKILLS,
        tmp_path / "catalog",
        source_repository=_REPOSITORY,
        source_revision=_REVISION,
    )
    payload = document.entries[0].model_dump(mode="json")
    payload["revoked"] = True
    with pytest.raises(ValidationError, match="require a reason"):
        CatalogEntry.model_validate(payload)

    payload = document.entries[0].model_dump(mode="json")
    payload["revocation_reason"] = "No longer supported"
    with pytest.raises(ValidationError, match="cannot declare"):
        CatalogEntry.model_validate(payload)

    payload = document.entries[0].model_dump(mode="json")
    payload["files"] = [payload["files"][0], payload["files"][0]]
    with pytest.raises(ValidationError, match="duplicate paths"):
        CatalogEntry.model_validate(payload)

    with pytest.raises(ValidationError, match="Revocation digest must be SHA-256"):
        SkillRevocation.model_validate(
            {"name": "invalid", "tree-sha256": "g" * 64, "reason": "Invalid"}
        )

    revocation = SkillRevocation.model_validate(
        {"name": "duplicate", "tree-sha256": "a" * 64, "reason": "Duplicate"}
    )
    with pytest.raises(ValidationError, match="duplicate names"):
        SkillRevocationSet(revocations=(revocation, revocation))


def test_catalog_applies_only_exact_current_revocations(tmp_path: Path) -> None:
    inspected = inspect_skill(_SKILLS / "aggregate-export")
    revocations = SkillRevocationSet(
        revocations=(
            SkillRevocation.model_validate(
                {
                    "name": inspected.name,
                    "tree-sha256": inspected.tree_sha256,
                    "reason": "Synthetic withdrawal",
                }
            ),
        )
    )
    document = build_catalog(
        _SKILLS,
        tmp_path / "revoked",
        source_repository=_REPOSITORY,
        source_revision=_REVISION,
        revocations=revocations,
    )
    revoked = next(entry for entry in document.entries if entry.name == inspected.name)
    assert revoked.revoked
    assert revoked.revocation_reason == "Synthetic withdrawal"

    wrong_digest = revocations.model_copy(
        update={
            "revocations": (
                revocations.revocations[0].model_copy(update={"tree_sha256": "0" * 64}),
            )
        }
    )
    with pytest.raises(CatalogBuildError, match="does not match current Skill"):
        build_catalog(
            _SKILLS,
            tmp_path / "wrong-digest",
            source_repository=_REPOSITORY,
            source_revision=_REVISION,
            revocations=wrong_digest,
        )

    unknown = revocations.model_copy(
        update={
            "revocations": (
                revocations.revocations[0].model_copy(update={"name": "missing-skill"}),
            )
        }
    )
    with pytest.raises(CatalogBuildError, match="unknown Skill"):
        build_catalog(
            _SKILLS,
            tmp_path / "unknown",
            source_repository=_REPOSITORY,
            source_revision=_REVISION,
            revocations=unknown,
        )


def test_repository_revocation_register_is_valid() -> None:
    assert load_revocations(Path("revocations.toml")).revocations == ()


def test_catalog_rejects_controlled_data_approval_claims(tmp_path: Path) -> None:
    skill = _copy_skill(tmp_path / "controlled-data-claim")
    definition = skill / "SKILL.md"
    definition.write_text(
        definition.read_text(encoding="utf-8").replace(
            'heartwood.controlled-data: "not-approved"',
            'heartwood.controlled-data: "deployment-approved"',
        ),
        encoding="utf-8",
    )

    with pytest.raises(CatalogBuildError, match="invalid Heartwood metadata"):
        inspect_skill(skill)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("tree_sha256", "z" * 64, "SHA-256"),
        ("archive_sha256", "z" * 64, "SHA-256"),
        ("target", "../skill.zip", "clean and relative"),
        ("source_repository", "http://example.test/skills", "HTTPS GitHub"),
        ("source_revision", "z" * 40, "full Git commit"),
    ],
)
def test_catalog_entry_rejects_untrusted_source_fields(
    tmp_path: Path,
    field: str,
    value: str,
    message: str,
) -> None:
    document = build_catalog(
        _SKILLS,
        tmp_path / "catalog",
        source_repository=_REPOSITORY,
        source_revision=_REVISION,
    )
    payload = document.entries[0].model_dump(mode="json")
    payload[field] = value

    with pytest.raises(ValidationError, match=message):
        CatalogEntry.model_validate(payload)


def test_catalog_models_reject_unsafe_paths_and_duplicate_identities(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="clean and relative"):
        SkillFile(path="../SKILL.md", size=1, sha256="a" * 64, role="definition", executable=False)
    with pytest.raises(ValidationError, match="SHA-256"):
        SkillFile(path="SKILL.md", size=1, sha256="z" * 64, role="definition", executable=False)
    with pytest.raises(ValidationError, match="Semantic Versioning"):
        SkillPolicy(
            skill_id="heartwood.test",
            version="1",
            dataset_types=("synthetic",),
            platforms=("generic",),
            phi_risk="none",
            requires_network=False,
            controlled_data="not-approved",
            approval_summary="Test",
        )
    with pytest.raises(ValidationError, match="clean and relative"):
        SkillPolicy(
            skill_id="heartwood.test",
            version="1.0.0",
            dataset_types=("synthetic",),
            platforms=("generic",),
            phi_risk="none",
            requires_network=False,
            controlled_data="not-approved",
            approval_summary="Test",
            entrypoint="../run.py",
        )
    assert (
        SkillPolicy(
            skill_id="heartwood.test",
            version="1.0.0",
            dataset_types=("synthetic",),
            platforms=("generic",),
            phi_risk="none",
            requires_network=False,
            controlled_data="not-approved",
            approval_summary="Test",
        ).entrypoint
        is None
    )

    document = build_catalog(
        _SKILLS,
        tmp_path / "catalog",
        source_repository=_REPOSITORY,
        source_revision=_REVISION,
    )
    entry = document.entries[0]
    with pytest.raises(ValidationError, match="duplicate Skill names"):
        CatalogDocument(entries=(entry, entry))
    duplicate_id = document.entries[1].model_copy(update={"policy": entry.policy})
    with pytest.raises(ValidationError, match="duplicate Skill identifiers"):
        CatalogDocument(entries=(entry, duplicate_id))
    with pytest.raises(ValidationError, match="at most 256"):
        CatalogDocument(entries=(entry,) * 257)


def test_catalog_rejects_an_unbounded_number_of_skill_directories(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    for index in range(257):
        (skills / f"skill-{index:03d}").mkdir(parents=True)

    with pytest.raises(CatalogBuildError, match="256-Skill catalog limit"):
        build_catalog(
            skills,
            tmp_path / "catalog",
            source_repository=_REPOSITORY,
            source_revision=_REVISION,
        )


def test_catalog_build_failure_removes_staging_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "catalog"

    def fail_archive(*_args: object) -> None:
        raise RuntimeError("synthetic archive interruption")

    monkeypatch.setattr(catalog_module, "_write_archive", fail_archive)
    with pytest.raises(RuntimeError, match="synthetic archive interruption"):
        build_catalog(
            _SKILLS,
            output,
            source_repository=_REPOSITORY,
            source_revision=_REVISION,
        )

    assert not output.exists()
    assert not tuple(tmp_path.glob(".catalog-*"))


def test_cli_validates_and_builds_catalog(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["validate", str(_SKILLS)]) == 0
    validation_output = capsys.readouterr().out
    assert '"name": "aggregate-export"' in validation_output

    repository, skills, revision = _git_catalog_repository(tmp_path)
    output = tmp_path / "catalog"
    assert (
        main(
            [
                "build",
                str(skills),
                "--output",
                str(output),
                "--repository",
                _REPOSITORY,
                "--revision",
                revision,
                "--revocations",
                str(repository / "revocations.toml"),
            ]
        )
        == 0
    )
    assert "Built 3 Skill targets" in capsys.readouterr().out


def test_empty_skill_root_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(CatalogBuildError, match="does not contain"):
        build_catalog(
            tmp_path,
            tmp_path / "output",
            source_repository=_REPOSITORY,
            source_revision=_REVISION,
        )

    with pytest.raises(CatalogBuildError, match="does not exist"):
        build_catalog(
            tmp_path / "missing",
            tmp_path / "output",
            source_repository=_REPOSITORY,
            source_revision=_REVISION,
        )

    with pytest.raises(CatalogBuildError, match=r"missing SKILL\.md"):
        inspect_skill(tmp_path / "missing")


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('heartwood.id: "heartwood.research.aggregate-export"', 'heartwood.id: ""', "requires"),
        (
            'heartwood.dataset-types: "omop-cdm"',
            'heartwood.dataset-types: ","',
            "at least one",
        ),
        (
            'heartwood.entrypoint: "scripts/run.py"',
            'heartwood.entrypoint: ""',
            "entrypoint",
        ),
        (
            'heartwood.requires-network: "false"',
            'heartwood.requires-network: "true"',
            "network",
        ),
    ],
)
def test_policy_metadata_normalization(
    tmp_path: Path,
    old: str,
    new: str,
    message: str,
) -> None:
    root = _copy_skill(tmp_path)
    _replace(root, old, new)
    if message in {"entrypoint", "network"}:
        inspected = inspect_skill(root)
        if message == "entrypoint":
            assert inspected.policy.entrypoint is None
        else:
            assert inspected.policy.requires_network is True
        return

    with pytest.raises(CatalogBuildError, match=message):
        inspect_skill(root)


def test_openhands_validation_errors_are_reported(tmp_path: Path) -> None:
    root = _copy_skill(tmp_path)
    (root / "SKILL.md").write_text("---\nname: [\n---\n", encoding="utf-8")

    with pytest.raises(CatalogBuildError, match="OpenHands rejected"):
        inspect_skill(root)


@pytest.mark.parametrize(
    ("limit", "value", "message"),
    [
        ("_MAX_FILE_BYTES", 1, "file exceeds"),
        ("_MAX_TOTAL_BYTES", 1, "tree exceeds"),
        ("_MAX_FILES", 0, "files"),
    ],
)
def test_skill_tree_resource_limits_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    limit: str,
    value: int,
    message: str,
) -> None:
    root = _copy_skill(tmp_path)
    monkeypatch.setattr(catalog_module, limit, value)

    with pytest.raises(CatalogBuildError, match=message):
        inspect_skill(root)


def test_catalog_entry_enforces_complete_tree_limits(tmp_path: Path) -> None:
    entry, _ = _catalog_entry(tmp_path)
    file_template = entry.files[0]
    oversized_files = tuple(
        file_template.model_copy(
            update={
                "path": f"assets/{index}.bin",
                "size": catalog_module._MAX_FILE_BYTES,
            }
        )
        for index in range(9)
    )
    with pytest.raises(ValidationError, match="total-size limit"):
        CatalogEntry.model_validate({**entry.model_dump(mode="json"), "files": oversized_files})

    too_many_files = tuple(
        file_template.model_copy(update={"path": f"assets/{index}.txt"})
        for index in range(catalog_module._MAX_FILES + 1)
    )
    with pytest.raises(ValidationError, match="at most"):
        CatalogEntry.model_validate({**entry.model_dump(mode="json"), "files": too_many_files})


def test_non_utf8_revocation_register_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "revocations.toml"
    path.write_bytes(b"\xff\xfe")

    with pytest.raises(CatalogBuildError, match="revocation register is invalid"):
        load_revocations(path)


def test_skill_tree_rejects_git_metadata_and_tracks_other_resources(tmp_path: Path) -> None:
    root = _copy_skill(tmp_path / "git")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("not repository metadata", encoding="utf-8")
    with pytest.raises(CatalogBuildError, match="Git metadata"):
        inspect_skill(root)

    root = _copy_skill(tmp_path / "other")
    (root / "NOTICE.txt").write_text("Additional notice\n", encoding="utf-8")
    inspected = inspect_skill(root)
    assert next(item for item in inspected.files if item.path == "NOTICE.txt").role == "other"


def test_cli_reports_invalid_inputs_and_uses_the_checked_out_revision(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as invalid_root:
        main(["validate", str(tmp_path)])
    assert invalid_root.value.code == 2
    assert "does not contain any Skill directories" in capsys.readouterr().err

    with pytest.raises(SystemExit) as missing_root:
        main(["build", str(tmp_path / "missing"), "--output", str(tmp_path / "catalog")])
    assert missing_root.value.code == 2
    assert "does not exist" in capsys.readouterr().err

    repository, skills, checked_out_revision = _git_catalog_repository(tmp_path / "git")
    output = tmp_path / "from-git"
    assert (
        main(
            [
                "build",
                str(skills),
                "--output",
                str(output),
                "--revision",
                checked_out_revision,
                "--revocations",
                str(repository / "revocations.toml"),
            ]
        )
        == 0
    )
    payload = CatalogDocument.model_validate_json(
        (output / "catalog.json").read_text(encoding="utf-8")
    )
    assert {entry.source_revision for entry in payload.entries} == {checked_out_revision}


def test_cli_builds_from_one_immutable_git_snapshot(
    tmp_path: Path,
) -> None:
    repository, skills, checked_out_revision = _git_catalog_repository(tmp_path)
    output = tmp_path / "catalog"
    live_skill = skills / "aggregate-export/SKILL.md"
    live_revocations = repository / "revocations.toml"
    with _git_snapshot(skills, live_revocations) as (
        snapshot_skills,
        snapshot_revocations,
        source_revision,
    ):
        live_skill.write_text("mutated after snapshot\n", encoding="utf-8")
        live_revocations.write_text("invalid after snapshot\n", encoding="utf-8")
        assert snapshot_skills != skills
        document = build_catalog(
            snapshot_skills,
            output,
            source_repository=_REPOSITORY,
            source_revision=source_revision,
            revocations=load_revocations(snapshot_revocations),
        )
    assert {entry.source_revision for entry in document.entries} == {checked_out_revision}


def test_cli_rejects_dirty_revision_discovery(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository, skills, checked_out_revision = _git_catalog_repository(tmp_path)
    assert (
        main(
            [
                "build",
                str(skills),
                "--output",
                str(tmp_path / "clean-catalog"),
                "--revocations",
                str(repository / "revocations.toml"),
            ]
        )
        == 0
    )
    clean_document = CatalogDocument.model_validate_json(
        (tmp_path / "clean-catalog/catalog.json").read_text(encoding="utf-8")
    )
    assert {entry.source_revision for entry in clean_document.entries} == {checked_out_revision}
    with pytest.raises(SystemExit) as mismatched_revision:
        main(
            [
                "build",
                str(skills),
                "--output",
                str(tmp_path / "mismatched-catalog"),
                "--revision",
                "0" * 40,
                "--revocations",
                str(repository / "revocations.toml"),
            ]
        )
    assert mismatched_revision.value.code == 2
    assert "does not match the checked-out commit" in capsys.readouterr().err
    (skills / "aggregate-export/SKILL.md").write_text(
        (skills / "aggregate-export/SKILL.md").read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as dirty_tree:
        main(
            [
                "build",
                str(skills),
                "--output",
                str(repository / "dist"),
                "--revocations",
                str(repository / "revocations.toml"),
            ]
        )

    assert dirty_tree.value.code == 2
    assert "Git working tree is not clean" in capsys.readouterr().err

    with pytest.raises(SystemExit) as dirty_explicit_revision:
        main(
            [
                "build",
                str(skills),
                "--output",
                str(repository / "explicit-dist"),
                "--revision",
                checked_out_revision,
                "--revocations",
                str(repository / "revocations.toml"),
            ]
        )
    assert dirty_explicit_revision.value.code == 2
    assert "Git working tree is not clean" in capsys.readouterr().err
