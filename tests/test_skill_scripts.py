# This source file is part of the Heartwood Skills open-source project
#
# SPDX-FileCopyrightText: 2026 Schmiedmayer Lab at Stanford University
#
# SPDX-License-Identifier: MIT

"""Tests for the verified prototype skill scripts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from heartwood_skill_catalog import SkillPolicy, inspect_skill

_DATA_ROOT = Path("fixtures/synthetic/omop-like")
_SKILLS_ROOT = Path("skills/verified")
_AGGREGATE_EXPORT_SCHEMA = _SKILLS_ROOT / "aggregate-export/assets/output-schema.json"


def _policy(name: str) -> tuple[Path, SkillPolicy]:
    inspected = inspect_skill(_SKILLS_ROOT / name)
    assert inspected.policy.entrypoint is not None
    return inspected.root / inspected.policy.entrypoint, inspected.policy


def _run(
    name: str,
    *args: str,
) -> subprocess.CompletedProcess[str]:
    entrypoint, _ = _policy(name)
    return subprocess.run(
        [sys.executable, str(entrypoint), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _assert_aggregate_export_schema(payload: dict[str, object]) -> None:
    schema = json.loads(_AGGREGATE_EXPORT_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)


def test_omop_cohort_summary_script_emits_qc_and_export_guard(tmp_path: Path) -> None:
    output = tmp_path / "cohort-summary.json"
    completed = _run(
        "omop-cohort-summary",
        "--data-root",
        str(_DATA_ROOT),
        "--output",
        str(output),
    )

    assert completed.stdout == "Wrote aggregate cohort summary to cohort-summary.json.\n"
    payload = _load_json(output)
    summary = payload["summary"]
    quality_checks = payload["quality_checks"]
    export_guard = payload["export_guard"]
    assert isinstance(summary, dict)
    assert isinstance(quality_checks, dict)
    assert isinstance(export_guard, dict)
    assert summary["source_participant_count"] == 24
    assert summary["source_condition_occurrence_count"] == 39
    assert summary["participant_count"] == 20
    assert summary["target_condition_occurrence_count"] == 20
    assert summary["condition_occurrence_count"] == 35
    assert summary["age_at_index"] == {"minimum": 35, "median": 53.5, "maximum": 70}
    assert quality_checks["condition_references_known_persons"] is True
    assert quality_checks["person_ids_unique"] is True
    assert quality_checks["condition_occurrence_ids_unique"] is True
    assert quality_checks["condition_years_not_before_birth"] is True
    assert quality_checks["aggregate_only_output"] is True
    assert export_guard["aggregate_count_floor"] == 20
    assert export_guard["exportable"] is True


def test_omop_cohort_summary_script_rejects_negative_floor(tmp_path: Path) -> None:
    output = tmp_path / "cohort-summary.json"
    with pytest.raises(subprocess.CalledProcessError) as error:
        _run(
            "omop-cohort-summary",
            "--data-root",
            str(_DATA_ROOT),
            "--output",
            str(output),
            "--aggregate-count-floor",
            "-1",
        )
    assert "value must be non-negative" in error.value.stderr


def test_omop_cohort_summary_reports_malformed_input_quality_checks(tmp_path: Path) -> None:
    data_root = tmp_path / "malformed"
    data_root.mkdir()
    (data_root / "person.csv").write_text(
        "person_id,year_of_birth\n1,1980\n1,1981\n",
        encoding="utf-8",
    )
    (data_root / "condition_occurrence.csv").write_text(
        "condition_occurrence_id,person_id,condition_concept_id,condition_start_year\n"
        "10,1,201826,1970\n"
        "10,1,316866,2020\n"
        "11,99,201826,2020\n"
        "12,1,invalid,2020\n"
        "13,,201826,2020\n",
        encoding="utf-8",
    )
    output = tmp_path / "cohort-summary.json"

    completed = _run(
        "omop-cohort-summary",
        "--data-root",
        str(data_root),
        "--output",
        str(output),
    )

    assert completed.stdout == "Wrote aggregate cohort summary to cohort-summary.json.\n"
    payload = _load_json(output)
    quality_checks = payload["quality_checks"]
    assert isinstance(quality_checks, dict)
    assert quality_checks["person_ids_unique"] is False
    assert quality_checks["condition_occurrence_ids_unique"] is False
    assert quality_checks["condition_years_parseable"] is False
    assert quality_checks["condition_years_not_before_birth"] is False
    assert quality_checks["condition_references_known_persons"] is False
    assert quality_checks["aggregate_only_output"] is True


def test_reference_cohort_exports_only_aggregate_counts(tmp_path: Path) -> None:
    summary_path = tmp_path / "cohort-summary.json"
    export_path = tmp_path / "aggregate-export.json"
    _run("omop-cohort-summary", "--data-root", str(_DATA_ROOT), "--output", str(summary_path))
    _run("aggregate-export", "--summary", str(summary_path), "--output", str(export_path))

    payload = _load_json(export_path)
    _assert_aggregate_export_schema(payload)
    assert payload["exported"] is True
    assert payload["suppressed"] is False
    assert payload["aggregates"] == {
        "participant_count": 20,
        "condition_occurrence_count": 35,
        "target_condition_occurrence_count": 20,
    }
    assert "person_id" not in json.dumps(payload)


def test_aggregate_export_script_suppresses_low_counts(tmp_path: Path) -> None:
    summary_path = tmp_path / "small-summary.json"
    output_path = tmp_path / "aggregate-export.json"
    summary_path.write_text(
        json.dumps(
            {
                "summary": {
                    "participant_count": 3,
                    "condition_occurrence_count": 5,
                    "target_condition_occurrence_count": 3,
                }
            }
        ),
        encoding="utf-8",
    )
    _run(
        "aggregate-export",
        "--summary",
        str(summary_path),
        "--output",
        str(output_path),
    )
    payload = _load_json(output_path)
    _assert_aggregate_export_schema(payload)
    assert payload["exported"] is False
    assert payload["suppressed"] is True
    assert payload["aggregates"] == {}
    assert "participant_count" not in json.dumps(payload["aggregates"])


def test_aggregate_export_script_rejects_negative_floor(tmp_path: Path) -> None:
    summary_path = tmp_path / "cohort-summary.json"
    output_path = tmp_path / "aggregate-export.json"
    summary_path.write_text(json.dumps({"summary": {"participant_count": 3}}), encoding="utf-8")
    with pytest.raises(subprocess.CalledProcessError) as error:
        _run(
            "aggregate-export",
            "--summary",
            str(summary_path),
            "--output",
            str(output_path),
            "--aggregate-count-floor",
            "-1",
        )
    assert "aggregate count floor must be non-negative" in error.value.stderr
    assert not output_path.exists()


@pytest.mark.parametrize(
    "content",
    [
        "{",
        "[]",
        "{}",
        '{"summary": []}',
    ],
)
def test_aggregate_export_script_rejects_malformed_summaries(
    tmp_path: Path,
    content: str,
) -> None:
    summary_path = tmp_path / "invalid-summary.json"
    output_path = tmp_path / "aggregate-export.json"
    summary_path.write_text(content, encoding="utf-8")

    with pytest.raises(subprocess.CalledProcessError):
        _run(
            "aggregate-export",
            "--summary",
            str(summary_path),
            "--output",
            str(output_path),
        )

    assert not output_path.exists()


def test_aggregate_export_script_exports_when_floor_is_satisfied(tmp_path: Path) -> None:
    summary_path = tmp_path / "large-summary.json"
    output_path = tmp_path / "large-export.json"
    summary_path.write_text(
        json.dumps(
            {
                "summary": {
                    "participant_count": 21,
                    "condition_occurrence_count": 34,
                }
            }
        ),
        encoding="utf-8",
    )
    _run(
        "aggregate-export",
        "--summary",
        str(summary_path),
        "--output",
        str(output_path),
        "--aggregate-count-floor",
        "0",
    )
    payload = _load_json(output_path)
    _assert_aggregate_export_schema(payload)
    assert payload["exported"] is True
    assert payload["aggregate_count_floor"] == 0
    assert payload["aggregates"] == {
        "participant_count": 21,
        "condition_occurrence_count": 34,
    }


def test_baseline_model_script_omits_row_values(tmp_path: Path) -> None:
    output = tmp_path / "baseline-model.json"
    _run(
        "baseline-model",
        "--data-root",
        str(_DATA_ROOT),
        "--output",
        str(output),
    )
    payload = _load_json(output)
    model = payload["model"]
    training_summary = payload["training_summary"]
    quality_checks = payload["quality_checks"]
    assert isinstance(model, dict)
    assert isinstance(training_summary, dict)
    assert isinstance(quality_checks, dict)
    assert model["model_type"] == "synthetic-logistic-condition-history"
    assert model["target_condition_concept_id"] == 201826
    coefficients = model["coefficients"]
    assert isinstance(coefficients, dict)
    assert float(coefficients["age_per_10_years"]) > 0
    assert training_summary["participant_count"] == 24
    assert training_summary["positive_count"] == 20
    assert float(training_summary["brier_score"]) < 0.2
    assert 0.5 < float(training_summary["roc_auc"]) < 1.0
    assert quality_checks["holdout_evaluation_performed"] is False
    assert quality_checks["aggregate_only_output"] is True
    assert "person_id" not in json.dumps(payload)


def test_baseline_model_respects_the_as_of_year_boundary(tmp_path: Path) -> None:
    data_root = tmp_path / "boundary"
    data_root.mkdir()
    (data_root / "person.csv").write_text(
        "person_id,year_of_birth\n1,1980\n2,1985\n3,1990\n",
        encoding="utf-8",
    )
    (data_root / "condition_occurrence.csv").write_text(
        "condition_occurrence_id,person_id,condition_concept_id,condition_start_year\n"
        "10,1,201826,2020\n"
        "11,2,201826,2021\n"
        "12,3,316866,2019\n",
        encoding="utf-8",
    )
    output = tmp_path / "baseline-model.json"

    _run(
        "baseline-model",
        "--data-root",
        str(data_root),
        "--output",
        str(output),
        "--as-of-year",
        "2020",
    )

    payload = _load_json(output)
    training_summary = payload["training_summary"]
    assert isinstance(training_summary, dict)
    assert training_summary["positive_count"] == 1
    assert "person_id" not in json.dumps(payload)


@pytest.mark.parametrize(
    ("condition_header", "condition_row", "message"),
    [
        (
            "condition_occurrence_id,person_id,condition_concept_id,condition_start_year",
            "10,1,invalid,2020",
            "condition concept identifiers must be integers",
        ),
        (
            "condition_occurrence_id,person_id,condition_concept_id,condition_start_year",
            "10,1,201826,invalid",
            "target condition start years must be integers",
        ),
        (
            "condition_occurrence_id,person_id,condition_concept_id",
            "10,1,201826",
            "missing required columns: condition_start_year",
        ),
    ],
)
def test_baseline_model_rejects_malformed_condition_values(
    tmp_path: Path,
    condition_header: str,
    condition_row: str,
    message: str,
) -> None:
    data_root = tmp_path / "malformed-model"
    data_root.mkdir()
    (data_root / "person.csv").write_text(
        "person_id,year_of_birth\n1,1980\n2,1985\n",
        encoding="utf-8",
    )
    (data_root / "condition_occurrence.csv").write_text(
        f"{condition_header}\n{condition_row}\n",
        encoding="utf-8",
    )
    output = tmp_path / "baseline-model.json"

    with pytest.raises(subprocess.CalledProcessError) as error:
        _run(
            "baseline-model",
            "--data-root",
            str(data_root),
            "--output",
            str(output),
        )

    assert message in error.value.stderr
    assert not output.exists()


def test_baseline_model_rejects_invalid_as_of_year(tmp_path: Path) -> None:
    output = tmp_path / "baseline-model.json"
    with pytest.raises(subprocess.CalledProcessError) as error:
        _run(
            "baseline-model",
            "--data-root",
            str(_DATA_ROOT),
            "--output",
            str(output),
            "--as-of-year",
            "0",
        )

    assert "value must be positive" in error.value.stderr
    assert not output.exists()


def test_reference_workflow_keeps_cohort_model_and_export_consistent(tmp_path: Path) -> None:
    summary_path = tmp_path / "cohort-summary.json"
    model_path = tmp_path / "baseline-model.json"
    export_path = tmp_path / "aggregate-export.json"

    _run("omop-cohort-summary", "--data-root", str(_DATA_ROOT), "--output", str(summary_path))
    _run("baseline-model", "--data-root", str(_DATA_ROOT), "--output", str(model_path))
    _run("aggregate-export", "--summary", str(summary_path), "--output", str(export_path))

    summary = _load_json(summary_path)
    model = _load_json(model_path)
    exported = _load_json(export_path)
    cohort_definition = summary["cohort_definition"]
    model_payload = model["model"]
    assert isinstance(cohort_definition, dict)
    assert isinstance(model_payload, dict)
    assert (
        cohort_definition["target_condition_concept_id"]
        == model_payload["target_condition_concept_id"]
        == 201826
    )
    assert exported["aggregates"] == {
        "participant_count": 20,
        "condition_occurrence_count": 35,
        "target_condition_occurrence_count": 20,
    }
