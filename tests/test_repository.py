# This source file is part of the Heartwood Skills open-source project
#
# SPDX-FileCopyrightText: 2026 Stanford University and the project authors (see CONTRIBUTORS.md)
#
# SPDX-License-Identifier: MIT

"""Repository policy and contribution-surface tests."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_ISSUE_TEMPLATE_ROOT = Path(".github/ISSUE_TEMPLATE")
_FORM_TYPES = {"checkboxes", "dropdown", "input", "markdown", "textarea", "upload"}
_TOP_LEVEL_KEYS = {"assignees", "body", "description", "labels", "name", "title"}
_ELEMENT_KEYS = {"attributes", "id", "type", "validations"}
_FIELD_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def _load_yaml_mapping(path: Path) -> dict[str, object]:
    payload: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), f"{path} must contain a mapping"
    assert all(isinstance(key, str) for key in payload), f"{path} keys must be strings"
    return payload


def _load_workflow_mapping(path: Path) -> dict[str, object]:
    payload: object = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(payload, dict), f"{path} must contain a mapping"
    assert all(isinstance(key, str) for key in payload), f"{path} keys must be strings"
    return payload


def test_issue_forms_follow_the_github_form_contract() -> None:
    names: set[str] = set()

    for path in sorted(_ISSUE_TEMPLATE_ROOT.glob("*.yml")):
        if path.name == "config.yml":
            continue

        form = _load_yaml_mapping(path)
        assert not form.keys() - _TOP_LEVEL_KEYS, f"{path} has unsupported top-level keys"
        form_name = form.get("name")
        assert isinstance(form_name, str)
        assert form_name
        assert isinstance(form.get("description"), str)
        assert form["description"]
        assert isinstance(form.get("title", ""), str)
        assert form_name not in names, f"duplicate issue-form name: {form_name}"
        names.add(form_name)

        labels = form.get("labels", [])
        assert isinstance(labels, list)
        assert all(isinstance(label, str) for label in labels)
        body = form.get("body")
        assert isinstance(body, list)
        assert body, f"{path} must define at least one field"

        field_ids: set[str] = set()
        for element in body:
            assert isinstance(element, dict), f"{path} form elements must be mappings"
            assert not element.keys() - _ELEMENT_KEYS, f"{path} has unsupported element keys"
            field_type = element.get("type")
            assert field_type in _FORM_TYPES, f"{path} has unsupported field type {field_type!r}"
            attributes = element.get("attributes")
            assert isinstance(attributes, dict), f"{path} fields must define attributes"

            if field_type == "markdown":
                assert "id" not in element
                assert isinstance(attributes.get("value"), str)
                assert attributes["value"]
                continue

            field_id = element.get("id")
            assert isinstance(field_id, str)
            assert _FIELD_ID.fullmatch(field_id)
            assert field_id not in field_ids, f"{path} repeats field id {field_id}"
            field_ids.add(field_id)
            assert isinstance(attributes.get("label"), str)
            assert attributes["label"]

            validations = element.get("validations", {})
            assert isinstance(validations, dict)
            assert set(validations) <= {"required"}
            assert isinstance(validations.get("required", False), bool)

            if field_type in {"checkboxes", "dropdown"}:
                options = attributes.get("options")
                assert isinstance(options, list)
                assert options
                if field_type == "checkboxes":
                    assert all(
                        isinstance(option, dict)
                        and isinstance(option.get("label"), str)
                        and isinstance(option.get("required", False), bool)
                        for option in options
                    )
                else:
                    assert all(isinstance(option, str) for option in options)

    assert names, "at least one issue form must be defined"


def test_issue_template_chooser_configuration_is_valid() -> None:
    config = _load_yaml_mapping(_ISSUE_TEMPLATE_ROOT / "config.yml")
    assert set(config) == {"blank_issues_enabled", "contact_links"}
    assert isinstance(config["blank_issues_enabled"], bool)

    links = config["contact_links"]
    assert isinstance(links, list)
    assert links
    names: set[str] = set()
    for link in links:
        assert isinstance(link, dict)
        assert set(link) == {"about", "name", "url"}
        assert isinstance(link["name"], str)
        assert link["name"]
        assert link["name"] not in names
        names.add(link["name"])
        assert isinstance(link["about"], str)
        assert link["about"]
        assert isinstance(link["url"], str)
        assert link["url"].startswith("https://")


def test_identity_tokens_are_isolated_from_repository_code() -> None:
    python = _load_workflow_mapping(Path(".github/workflows/python.yml"))
    python_jobs = python.get("jobs")
    assert isinstance(python_jobs, dict)
    quality = python_jobs.get("quality")
    coverage = python_jobs.get("coverage")
    assert isinstance(quality, dict)
    assert isinstance(coverage, dict)
    assert quality.get("permissions") == {"contents": "read"}
    assert coverage.get("permissions") == {"contents": "read", "id-token": "write"}

    candidate = _load_workflow_mapping(Path(".github/workflows/catalog-candidate.yml"))
    assert candidate.get("permissions") == {"contents": "read"}
    candidate_jobs = candidate.get("jobs")
    assert isinstance(candidate_jobs, dict)
    validate = candidate_jobs.get("validate")
    attest = candidate_jobs.get("attest")
    assert isinstance(validate, dict)
    assert isinstance(attest, dict)
    assert validate.get("permissions") == {"contents": "read"}
    assert attest.get("permissions") == {
        "attestations": "write",
        "contents": "read",
        "id-token": "write",
    }
    attest_steps = attest.get("steps")
    assert isinstance(attest_steps, list)
    assert all(isinstance(step, dict) and "run" not in step for step in attest_steps)
    candidate_text = Path(".github/workflows/catalog-candidate.yml").read_text(encoding="utf-8")
    assert candidate_text.count('test "$(git rev-parse origin/main)" =') == 2
    assert "inputs.revision" not in candidate_text
