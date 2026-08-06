---
# This source file is part of the Heartwood Skills open-source project
#
# SPDX-FileCopyrightText: 2026 Stanford University and the project authors (see CONTRIBUTORS.md)
#
# SPDX-License-Identifier: MIT
name: aggregate-export
description: Apply a configured participant-count floor before exporting an aggregate cohort summary. Use when preparing bounded cohort results for review or export.
license: MIT
compatibility: Requires Python 3.12 or later. The included validation fixtures are synthetic.
allowed-tools: terminal
metadata:
  heartwood.id: "heartwood.research.aggregate-export"
  heartwood.version: "1.0.0"
  heartwood.dataset-types: "omop-cdm"
  heartwood.platforms: "generic,terra"
  heartwood.phi-risk: "none"
  heartwood.requires-network: "false"
  heartwood.controlled-data: "not-approved"
  heartwood.approval-summary: "Reads one cohort-summary artifact and writes aggregate output only when the configured participant-count floor is met."
  heartwood.entrypoint: "scripts/run.py"
---

# Synthetic Aggregate Export

Use this Skill only on a reviewed cohort-summary artifact. It applies the configured participant-count floor and writes either aggregate counts or a suppression decision. A successful script result is not permission to move the file out of the workspace; platform and institutional export authorization remain separate.

See [the output contract](assets/output-schema.json) before integrating the result with another workflow.

Use the exact Skill directory reported by `invoke_skill` to run the entrypoint; do not resolve `scripts/run.py` from the project directory.

Example:

```bash
SKILL_DIR=/exact/directory/reported/by/invoke_skill
python "$SKILL_DIR/scripts/run.py" \
  --summary cohort-summary.json \
  --aggregate-count-floor 20 \
  --output aggregate-export.json
```
