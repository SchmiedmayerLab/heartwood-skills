# This source file is part of the Heartwood open-source project
#
# SPDX-FileCopyrightText: 2026 Stanford University and the project authors (see CONTRIBUTORS.md)
#
# SPDX-License-Identifier: MIT

"""Command-line interface for curated Skill validation and packaging."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tarfile
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from heartwood_skill_catalog.catalog import (
    CatalogBuildError,
    build_catalog,
    inspect_skill,
    load_revocations,
)

_DEFAULT_REPOSITORY = "https://github.com/SchmiedmayerLab/heartwood-skills"


def build_parser() -> argparse.ArgumentParser:
    """Build the catalog-tooling argument parser."""
    parser = argparse.ArgumentParser(prog="heartwood-skill-catalog")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="Validate complete Agent Skill trees.")
    validate.add_argument("skills_root", nargs="?", type=Path, default=Path("skills/verified"))
    build = subparsers.add_parser("build", help="Build deterministic catalog targets.")
    build.add_argument("skills_root", nargs="?", type=Path, default=Path("skills/verified"))
    build.add_argument("--output", type=Path, default=Path("dist/catalog"))
    build.add_argument("--repository", default=_DEFAULT_REPOSITORY)
    build.add_argument("--revision")
    build.add_argument("--revocations", type=Path, default=Path("revocations.toml"))
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the catalog tooling."""
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            roots = tuple(path for path in sorted(args.skills_root.iterdir()) if path.is_dir())
            if not roots:
                parser.error("Skills root does not contain any Skill directories")
            for root in roots:
                inspected = inspect_skill(root)
                print(
                    json.dumps(
                        {
                            "files": len(inspected.files),
                            "name": inspected.name,
                            "tree_sha256": inspected.tree_sha256,
                            "version": inspected.policy.version,
                        },
                        sort_keys=True,
                    )
                )
            return 0
        if not args.skills_root.is_dir():
            raise CatalogBuildError(f"Skills root does not exist: {args.skills_root}")
        with _git_snapshot(
            args.skills_root,
            args.revocations,
            expected_revision=args.revision,
        ) as (skills_root, revocations_path, revision):
            document = build_catalog(
                skills_root,
                args.output,
                source_repository=args.repository,
                source_revision=revision,
                revocations=load_revocations(revocations_path),
            )
        print(f"Built {len(document.entries)} Skill targets in {args.output}")
        return 0
    except (CatalogBuildError, OSError, subprocess.SubprocessError) as error:
        parser.error(str(error))


@contextmanager
def _git_snapshot(
    source: Path,
    revocations: Path,
    *,
    expected_revision: str | None = None,
) -> Iterator[tuple[Path, Path, str]]:
    """Materialize catalog inputs from one verified immutable Git commit."""
    source = source.resolve()
    revocations = revocations.resolve()
    repository = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    repository_path = Path(repository).resolve()
    try:
        source_relative = source.relative_to(repository_path)
        revocations_relative = revocations.relative_to(repository_path)
    except ValueError as error:
        raise CatalogBuildError(
            "Skills and revocations must belong to the same Git repository"
        ) from error
    status = subprocess.run(
        [
            "git",
            "-C",
            str(repository_path),
            "status",
            "--porcelain",
            "--untracked-files=all",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if status:
        raise CatalogBuildError("Git working tree is not clean; commit the changes before building")
    revision = subprocess.run(
        ["git", "-C", str(repository_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if expected_revision is not None and expected_revision != revision:
        raise CatalogBuildError("Requested revision does not match the checked-out commit")
    with tempfile.TemporaryDirectory(prefix="heartwood-skill-catalog-") as temporary:
        staging = Path(temporary)
        archive = staging / "source.tar"
        subprocess.run(
            [
                "git",
                "-C",
                str(repository_path),
                "archive",
                "--format=tar",
                f"--output={archive}",
                revision,
                "--",
                source_relative.as_posix(),
                revocations_relative.as_posix(),
            ],
            check=True,
            capture_output=True,
        )
        snapshot = staging / "snapshot"
        snapshot.mkdir(mode=0o700)
        with tarfile.open(archive, mode="r:") as source_archive:
            source_archive.extractall(snapshot, filter="data")
        yield snapshot / source_relative, snapshot / revocations_relative, revision


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
