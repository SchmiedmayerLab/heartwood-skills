<!--

This source file is part of the Heartwood Skills open-source project

SPDX-FileCopyrightText: 2026 Stanford University and the project authors (see CONTRIBUTORS.md)

SPDX-License-Identifier: MIT

-->

# Contributing to Heartwood Skills

Heartwood Skills accepts focused additions and corrections to reusable biomedical-research workflows.
Public source, tests, examples, and logs must contain synthetic data only.

## Add or Update a Skill

- Follow the [Agent Skills specification](https://agentskills.io/specification).
- Keep `SKILL.md` concise and place supporting material in `scripts/`, `references/`, or `assets/`.
- Declare the complete Heartwood policy metadata used by the existing Skills.
- Do not embed credentials, participant-level data, model weights, generated results, or private platform evidence.
- Do not use OpenHands dynamic shell context or embedded MCP servers unless Heartwood first defines and tests a corresponding policy.
- Include deterministic tests for bundled scripts and failure paths.
- Distinguish repository review from controlled-data approval.

## Validate the Change

```bash
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run vulture
uv run heartwood-skill-catalog validate
uv run heartwood-skill-catalog build
uv run pytest
```

Generated catalog targets must be reproducible from the reviewed commit.
Publication and revocation use signed TUF metadata and never rely on a mutable branch reference.

## Open a Pull Request

Use the [Schmiedmayer Lab pull request template](https://github.com/SchmiedmayerLab/.github/blob/main/.github/pull_request_template.md).
Link the tracked Heartwood issue, summarize user-visible behavior, and report focused verification without development narration.

By contributing, you agree that your contribution is licensed under the repository's [MIT License](LICENSE).
