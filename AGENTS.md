<!--

This source file is part of the Heartwood Skills open-source project

SPDX-FileCopyrightText: 2026 Schmiedmayer Lab at Stanford University

SPDX-License-Identifier: MIT

-->

# AGENTS Instructions

## Purpose

This repository owns curated Agent Skill content, deterministic qualification, and generated catalog targets for Heartwood.
Heartwood owns acquisition, installation, runtime policy, interface behavior, and audit records.

## Working Rules

- Keep every published Skill compatible with the Agent Skills specification and the public OpenHands loader.
- Keep standard metadata in `SKILL.md`; do not add a second hand-maintained metadata copy.
- Keep generated digests, source revisions, archive sizes, and review provenance in catalog output rather than authored Skill files.
- Treat scripts and executable extensions as active content requiring focused tests and explicit declarations.
- Use synthetic fixtures only.
- Do not claim controlled-data readiness without deployment-specific approval evidence.
- Add tests for success, malformed input, boundary enforcement, and aggregate-output behavior when changing scripts.
- Keep catalog builds deterministic and immutable.
- Attribute the project only to the Schmiedmayer Lab at Stanford University.

## Pull Requests

Use the [Schmiedmayer Lab pull request template](https://github.com/SchmiedmayerLab/.github/blob/main/.github/pull_request_template.md).
Keep titles, descriptions, and commit messages compact and natural.
Do not merge or enable auto-merge without explicit approval for that pull request.
