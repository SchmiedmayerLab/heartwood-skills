<!--

This source file is part of the Heartwood Skills open-source project

SPDX-FileCopyrightText: 2026 Stanford University and the project authors (see CONTRIBUTORS.md)

SPDX-License-Identifier: MIT

-->

# AGENTS Instructions

## Purpose

This repository owns curated Agent Skill content, deterministic qualification, and generated catalog targets for Heartwood.
Heartwood owns acquisition, installation, runtime policy, interface behavior, and audit records.

## Canonical Documentation

| Need | Source |
|---|---|
| Repository summary | [README.md](README.md) |
| Local contribution workflow | [CONTRIBUTING.md](CONTRIBUTING.md) |
| User-facing Skill workflow | [Heartwood Research Skills](https://schmiedmayerlab.github.io/heartwood/preview/use/skills/) |
| Skill trust, publication, and revocation | [Heartwood Skill Trust and Distribution](https://schmiedmayerlab.github.io/heartwood/preview/architecture/skills/) |
| Heartwood development boundaries | [Heartwood Development Guide](https://schmiedmayerlab.github.io/heartwood/preview/contribute/development/) |
| Planned work and acceptance criteria | [Heartwood Issues](https://github.com/SchmiedmayerLab/heartwood/issues) |

## Working Rules

- Keep every published Skill compatible with the Agent Skills specification and the public OpenHands loader.
- Keep standard metadata in `SKILL.md`; do not add a second hand-maintained metadata copy.
- Keep generated digests, source revisions, archive sizes, and review provenance in catalog output rather than authored Skill files.
- Treat scripts and executable extensions as active content requiring focused tests and explicit declarations.
- Use synthetic fixtures only.
- Do not claim controlled-data readiness without deployment-specific approval evidence.
- Add tests for success, malformed input, boundary enforcement, and aggregate-output behavior when changing scripts.
- Keep catalog builds deterministic and immutable.
- Keep durable user, deployment, and architecture documentation in the Heartwood repository rather than creating a second documentation tree here.
- Attribute Heartwood Skills only to the Schmiedmayer Lab at Stanford University.

## Pull Requests

Use this repository's Skill-specific pull-request template.
Keep titles, descriptions, and commit messages compact and natural.
Do not merge or enable auto-merge without explicit approval for that pull request.
