---
# This source file is part of the Heartwood Skills open-source project
#
# SPDX-FileCopyrightText: 2026 Stanford University and the project authors (see CONTRIBUTORS.md)
#
# SPDX-License-Identifier: MIT
name: baseline-model
description: Fit a deterministic age-only logistic baseline over an OMOP condition-history outcome. Use to establish a reproducible baseline before evaluating more complex models.
license: MIT
compatibility: Requires Python 3.12 or later. The included validation fixtures are synthetic.
allowed-tools: terminal
metadata:
  heartwood.id: "heartwood.research.baseline-model"
  heartwood.version: "1.0.0"
  heartwood.dataset-types: "omop-cdm"
  heartwood.platforms: "generic,terra"
  heartwood.phi-risk: "reads-phi"
  heartwood.requires-network: "false"
  heartwood.controlled-data: "not-approved"
  heartwood.approval-summary: "Reads OMOP-like CSV tables and writes aggregate training diagnostics without row-level values or predictions."
  heartwood.entrypoint: "scripts/run.py"
---

# Synthetic Baseline Model

Use this Skill only after inspecting the target-condition cohort and data-quality results. It fits a dependency-free age-only logistic model for recorded target-condition history and emits aggregate training diagnostics without row identifiers or predictions.

The model is deliberately a baseline. Its Brier score and ROC AUC are measured on the training fixture, no holdout evaluation is performed, and the result is not a clinical prediction model or capability claim. Compare future models against it only with a separately reviewed evaluation design.

Read [the evaluation notes](references/evaluation.md) before interpreting or extending the output.

Use the exact Skill directory reported by `invoke_skill` to run the entrypoint; do not resolve `scripts/run.py` from the project directory.

Example:

```bash
SKILL_DIR=/exact/directory/reported/by/invoke_skill
python "$SKILL_DIR/scripts/run.py" \
  --data-root data \
  --target-condition-concept-id 201826 \
  --as-of-year 2025 \
  --output baseline-model.json
```
