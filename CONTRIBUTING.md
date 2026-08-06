<!--

This source file is part of the Heartwood Skills open-source project

SPDX-FileCopyrightText: 2026 Stanford University and the project authors (see CONTRIBUTORS.md)

SPDX-License-Identifier: MIT

-->

# Contributing to Heartwood Skills

Heartwood Skills accepts focused additions and corrections to reusable biomedical-research workflows.
Public source, tests, examples, and logs must contain synthetic data only.

The canonical Skill format, policy, review, publication, and revocation guidance is maintained in the [Heartwood Skill contribution documentation](https://schmiedmayerlab.github.io/heartwood/preview/contribute/skills/).
Read that guidance and [AGENTS.md](AGENTS.md) before changing a Skill or catalog tooling.

## Prepare the Repository

Heartwood Skills requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --locked
```

## Make a Change

- Follow the [Agent Skills specification](https://agentskills.io/specification).
- Keep the complete package in one Skill directory; add optional `scripts/`, `references/`, and `assets/` directories only when the workflow needs them.
- Declare the [Heartwood policy metadata and permissions](https://schmiedmayerlab.github.io/heartwood/preview/contribute/skills/#declare-heartwood-policy) accurately.
- Do not embed credentials, participant-level data, model weights, generated results, or private platform evidence.
- Reuse the Agent Skills and OpenHands contracts rather than introducing another Skill format or loader.
- Add deterministic tests for changed scripts, validation, policy, packaging, or revocation behavior.

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

`validate` and the tests can inspect working changes.
`build` intentionally packages the exact checked-out Git revision, so commit the complete change locally before running it.

## Open a Pull Request

Use this repository's Skill-specific pull-request template.
Link the tracked issue, summarize the workflow or catalog behavior, and report focused synthetic verification without development narration.

By contributing, you agree that your contribution is licensed under the repository's [MIT License](LICENSE).
