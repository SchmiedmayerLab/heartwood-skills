<!--

This source file is part of the Heartwood Skills open-source project

SPDX-FileCopyrightText: 2026 Stanford University and the project authors (see CONTRIBUTORS.md)

SPDX-License-Identifier: MIT

-->

# Heartwood Skills

Heartwood Skills is the curated source for reusable biomedical-research workflows used by [Heartwood](https://github.com/SchmiedmayerLab/heartwood).
Each directory follows the [Agent Skills specification](https://agentskills.io/specification) and loads through the public OpenHands Skill interface.

The repository contains complete Skill packages, including instructions, executable scripts, references, and static assets.
It does not grant filesystem, network, model, credential, or controlled-data access.
Heartwood applies those permissions and records installation approval at runtime.

## Available Skills

| Skill | Purpose |
|---|---|
| `aggregate-export` | Apply a participant-count floor before producing aggregate output. |
| `baseline-model` | Produce a deterministic baseline with explicit evaluation limitations. |
| `omop-cohort-summary` | Define and inspect a bounded OMOP-like cohort using aggregate checks. |

The checked-in fixtures are synthetic.
Repository review does not constitute institutional approval for controlled data.

## Validate the Catalog

Install [uv](https://docs.astral.sh/uv/), then run:

```bash
uv sync --locked
uv run heartwood-skill-catalog validate
uv run pytest
```

Build the deterministic catalog targets with:

```bash
uv run heartwood-skill-catalog build
```

The manual **Build Catalog Candidate** workflow accepts only a full commit already merged into `main`, rebuilds and tests the complete catalog, records a GitHub artifact attestation, and retains the candidate for a TUF signing event.
An operator must establish the TUF root and signing roles before publishing a candidate as a trusted source; an attestation or mutable Git branch is not a substitute for signed TUF metadata.
See [Distribution](DISTRIBUTION.md) for the signing boundary and [Contributing](CONTRIBUTING.md) for review and testing requirements.

## License

Heartwood Skills is released under the [MIT License](LICENSE).
