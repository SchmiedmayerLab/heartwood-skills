---
# This source file is part of the Heartwood Skills open-source project
#
# SPDX-FileCopyrightText: 2026 Stanford University and the project authors (see CONTRIBUTORS.md)
#
# SPDX-License-Identifier: MIT
name: workload-prediction
description: Predict resource use for a bounded exploration, batch, or inference workload and revise the prediction using project evidence.
license: MIT
metadata:
  heartwood.id: "heartwood.research.workload-prediction"
  heartwood.version: "1.0.0"
  heartwood.dataset-types: "workload-metadata"
  heartwood.platforms: "generic,terra"
  heartwood.phi-risk: "none"
  heartwood.requires-network: "false"
  heartwood.controlled-data: "not-approved"
  heartwood.approval-summary: "Uses project-local aggregate workload measurements and researcher assumptions to prepare a prediction, and records it and requests platform estimates only through gateway tools the researcher reviews."
---

# Workload prediction

Call `planning_overview` first, before relying on a budget or an estimate.
It reports budgets and estimates each as available, not-offered, unavailable or refused, or unchecked before the first discovery.
It also gives the project_context_id of this launch context; a prediction's project_context_id must equal it.
Without that tool, tell the researcher plainly that no platform estimate or budget is available here.
When the overview reports budgets or estimates as anything but available, say plainly which one is missing and its status.
Never invent, assume or compute a price, budget or balance.

Ask the researcher for the input size, authorized runtime profile and stopping condition.
Use aggregate measurements from the current project.
For exploration, bound session duration and resources.
For a batch, record task count, resources per task, observed or assumed duration, parallelism and retry allowance.
For inference, identify the model and route, request count and expected input and output tokens.
Give units, ranges where supported and the assumptions behind each quantity.
Leave missing measurements unknown.

Prepare a workload prediction for the existing research plan, and record it with `record_plan_prediction` when that tool is available.
Give each evidence item an ID and cite it from the elements it supports.
For example, a ten-task sample taking 20 seconds per task supports a duration assumption on the sampled profile.
A different profile requires a new assumption or measurement.
Record the project-relative sample report or its experiment run ID.
A proposed benchmark needs normal action review and platform authorization before execution.

When the overview reports estimates as available, request one for the recorded revision with `request_plan_estimate` and compare coverage, validity and exclusions.
After a run, compare observed quantities with the assumptions in the same units.
Check changes to rates, coverage and runtime profile separately before attributing a difference to prediction error.
Record researcher corrections in a new revision, naming the previous prediction and linking the observed run.
For example, cite prediction:cohort-prediction@1 and experiment-run:00000000-0000-4000-8000-000000000001 after verifying both records in the project.
For a platform execution, copy the observation:SHA256 reference for the relevant operation, status and observation time from the planning overview.
An operation can have several status reports.
Cite the one that supports the correction.
Reuse measurements only through explicitly selected project evidence.
Recording a revision does not train a model, reserve funds or authorize execution.
