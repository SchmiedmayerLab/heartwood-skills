---
# This source file is part of the Heartwood Skills open-source project
# SPDX-FileCopyrightText: 2026 Schmiedmayer Lab at Stanford University
# SPDX-License-Identifier: MIT
name: omop-cohort-summary
description: Define a target-condition cohort and report aggregate quality checks from OMOP-like tables. Use for a bounded first-pass cohort characterization.
license: MIT
compatibility: Requires Python 3.12 or later. The included validation fixtures are synthetic.
allowed-tools: terminal
metadata:
  heartwood.id: "heartwood.research.omop-cohort-summary"
  heartwood.version: "1.0.0"
  heartwood.dataset-types: "omop-cdm"
  heartwood.platforms: "generic,terra"
  heartwood.phi-risk: "none"
  heartwood.requires-network: "false"
  heartwood.controlled-data: "not-approved"
  heartwood.approval-summary: "Reads OMOP-like person and condition-occurrence tables and writes aggregate counts and quality checks without row values."
  heartwood.entrypoint: "scripts/run.py"
---

# Synthetic OMOP Cohort Summary

Use this Skill when a researcher asks for a reproducible target-condition cohort over localized OMOP-like `person` and `condition_occurrence` tables.

Review [the cohort-definition checklist](references/cohort-definition.md) before running the workflow.

1. Confirm the local data root and target condition concept identifier. Do not infer a clinical label from an identifier.
2. Use the exact Skill directory reported by `invoke_skill` to run `scripts/run.py`; do not resolve the script from the project directory. Use explicit input and output paths. The default synthetic reference concept is `201826`, minimum age is 18 years at first target occurrence, and aggregate count floor is 20.
3. Report the cohort definition, inclusion and exclusion counts, age-at-index summary, and every data-quality check before interpreting the result.
4. Treat the output as an in-boundary aggregate artifact. Do not claim that it is clinically validated or representative of a complete OMOP Common Data Model cohort implementation.

Example:

```bash
SKILL_DIR=/exact/directory/reported/by/invoke_skill
python "$SKILL_DIR/scripts/run.py" \
  --data-root data \
  --target-condition-concept-id 201826 \
  --minimum-age 18 \
  --aggregate-count-floor 20 \
  --output cohort-summary.json
```
