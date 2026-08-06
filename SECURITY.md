<!--

This source file is part of the Heartwood Skills open-source project

SPDX-FileCopyrightText: 2026 Stanford University and the project authors (see CONTRIBUTORS.md)

SPDX-License-Identifier: MIT

-->

# Security Policy

## Report a Vulnerability

Report suspected vulnerabilities through [GitHub private vulnerability reporting](https://github.com/SchmiedmayerLab/heartwood-skills/security/advisories/new).
Do not open a public issue or include credentials, protected health information, participant-level data, or private platform logs in a report.

Include the affected Skill, immutable catalog revision or digest, impact, and a minimal synthetic reproduction when possible.
The repository maintainers will assess the affected content and coordinate disclosure, revocation, and remediation through the private advisory.

## Trust Boundary

Repository review confirms that one revision passed the catalog's source, policy, and compatibility checks.
Immutable candidate builds and attestations establish source provenance.
Neither establishes institutional approval, HIPAA compliance, authorization to process controlled data, or permission to export results.
Heartwood deployment policy and platform controls remain authoritative.

See [Security and Controlled Data](https://schmiedmayerlab.github.io/heartwood/preview/operate/security/) and [Skill Trust and Distribution](https://schmiedmayerlab.github.io/heartwood/preview/architecture/skills/) in the Heartwood documentation.
Supported Heartwood releases pin exact Skill revisions and follow the project [Support and Compatibility](https://schmiedmayerlab.github.io/heartwood/preview/operate/support/) policy.
