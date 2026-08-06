# This source file is part of the Heartwood Skills open-source project
#
# SPDX-FileCopyrightText: 2026 Stanford University and the project authors
#
# SPDX-License-Identifier: MIT

"""Command-line interface for curated Skill validation and packaging."""

from __future__ import annotations

import argparse
import json
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
        revision = args.revision or _git_revision()
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


def _git_revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
