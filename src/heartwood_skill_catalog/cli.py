# This source file is part of the Heartwood Skills open-source project
#
# SPDX-FileCopyrightText: 2026 Schmiedmayer Lab at Stanford University
#
# SPDX-License-Identifier: MIT

"""Command-line interface for curated Skill validation and packaging."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
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
        revision = _git_revision(args.skills_root, expected=args.revision)
        document = build_catalog(
            args.skills_root,
            args.output,
            source_repository=args.repository,
            source_revision=revision,
            revocations=load_revocations(args.revocations),
        )
        print(f"Built {len(document.entries)} Skill targets in {args.output}")
        return 0
    except (CatalogBuildError, OSError, subprocess.SubprocessError) as error:
        parser.error(str(error))


def _git_revision(source: Path, *, expected: str | None = None) -> str:
    repository = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "-C", repository, "status", "--porcelain", "--untracked-files=all"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if status:
        raise CatalogBuildError("Git working tree is not clean; commit the changes before building")
    revision = subprocess.run(
        ["git", "-C", repository, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if expected is not None and expected != revision:
        raise CatalogBuildError("Requested revision does not match the checked-out commit")
    return revision


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
