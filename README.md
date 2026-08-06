<!--

This source file is part of the Heartwood Skills open-source project

SPDX-FileCopyrightText: 2026 Stanford University and the project authors (see CONTRIBUTORS.md)

SPDX-License-Identifier: MIT

-->

# Heartwood Skills

[![Main Validation](https://github.com/SchmiedmayerLab/heartwood-skills/actions/workflows/main-validation.yml/badge.svg)](https://github.com/SchmiedmayerLab/heartwood-skills/actions/workflows/main-validation.yml)
![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)

[Stable Heartwood Documentation](https://schmiedmayerlab.github.io/heartwood/) · [Prerelease Heartwood Documentation](https://schmiedmayerlab.github.io/heartwood/preview/)

Heartwood Skills is the curated source for reusable biomedical-research workflows used by [Heartwood](https://github.com/SchmiedmayerLab/heartwood).
Each Skill directory follows the [Agent Skills specification](https://agentskills.io/specification) and loads through the public OpenHands Skill interface.
A Skill may include scripts, references, and static assets when its workflow needs them.

Repository review confirms that one revision passed the catalog's source, policy, and compatibility checks.
Immutable candidate builds and attestations establish source provenance; Heartwood deployment and project policy remain authoritative for installation and access.
See [Skill Trust and Distribution](https://schmiedmayerlab.github.io/heartwood/preview/architecture/skills/) for the complete trust and publication contract.

## Available Skills

| Skill | Purpose |
|---|---|
| `aggregate-export` | Apply a participant-count floor before producing aggregate output. |
| `baseline-model` | Produce a deterministic baseline with explicit evaluation limitations. |
| `omop-cohort-summary` | Define and inspect a bounded OMOP-like cohort using aggregate checks. |

The checked-in fixtures are synthetic.
Repository review does not constitute institutional approval for controlled data.

## Contribute a Skill

Start with the [Heartwood Skill contribution documentation](https://schmiedmayerlab.github.io/heartwood/preview/contribute/skills/) and the local [contribution guide](CONTRIBUTING.md).
Use synthetic fixtures only.

Install [uv](https://docs.astral.sh/uv/), then run:

```bash
uv sync --locked
uv run heartwood-skill-catalog validate
uv run pytest
```

Pull requests validate all Skill trees with OpenHands, execute the synthetic workflow tests, verify deterministic catalog output, and run repository security checks.
The manual **Build Catalog Candidate** workflow packages only a full commit already merged into `main`; signing and publication remain a separate deployment-owned operation described in the Heartwood documentation.

## Contributing

Contributions to this project are welcome.
Read the repository [contribution guide](CONTRIBUTING.md), the organization [contribution guide](https://github.com/SchmiedmayerLab/.github/blob/main/CONTRIBUTING.md), and the [Contributor Covenant Code of Conduct](https://github.com/SchmiedmayerLab/.github/blob/main/CODE_OF_CONDUCT.md) before opening a pull request.

## License

This project is licensed under the MIT License.
See [Licenses](LICENSES) and [Contributors](CONTRIBUTORS.md) for more information.

## Our Research

For more information, visit the [Schmiedmayer Lab GitHub organization](https://github.com/SchmiedmayerLab).

![Stanford and Stanford Medicine logos](https://raw.githubusercontent.com/SchmiedmayerLab/.github/main/assets/stanford-footer-light.png#gh-light-mode-only)
![Stanford and Stanford Medicine logos](https://raw.githubusercontent.com/SchmiedmayerLab/.github/main/assets/stanford-footer-dark.png#gh-dark-mode-only)
