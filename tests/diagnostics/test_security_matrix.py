"""
Tests for the Aksara security matrix loader and validator.

The public repository ships an example matrix and a framework release matrix.
Projects may maintain a private security_matrix.yml (git-ignored).
These tests validate matrix discovery, the example file, and validator logic.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from aksara.security.matrix import (
    VALID_EXPECTED,
    VALID_SEVERITIES,
    VALID_STATUSES,
    MatrixValidationIssue,
    _find_default_matrix_path,
    _find_example_matrix_path,
    load_security_matrix,
    validate_security_matrix,
)

# ---------------------------------------------------------------------------
# Helpers — minimal valid matrix and repo path
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLE_MATRIX_PATH = REPO_ROOT / "security" / "security_matrix.example.yml"


def _minimal_valid_matrix():
    """Return a minimal valid matrix dict for unit tests."""
    return {
        "version": 1,
        "metadata": {
            "name": "test-matrix",
            "description": "Test matrix",
            "owner": "test",
            "status": "active-hardening",
            "round": 1,
        },
        "surfaces": [
            {"id": "rest_create", "name": "REST Create", "category": "rest", "implemented": True, "description": "desc"},
            {"id": "rest_read", "name": "REST Read", "category": "rest", "implemented": True, "description": "desc"},
        ],
        "actors": [
            {"id": "unauthenticated", "description": "No auth"},
            {"id": "authenticated_user", "description": "Authed user"},
        ],
        "risks": [
            {"id": "missing_auth", "severity": "critical", "description": "No auth"},
            {"id": "sql_injection", "severity": "critical", "description": "SQL"},
        ],
        "scenarios": [
            {
                "id": "test_scenario",
                "surface": "rest_create",
                "actor": "unauthenticated",
                "risk": "missing_auth",
                "expected": "deny",
                "status": "planned",
                "description": "Test scenario",
            },
        ],
    }


# ---------------------------------------------------------------------------
# Example matrix file tests
# ---------------------------------------------------------------------------


class TestExampleSecurityMatrix:
    """Tests that verify the public security_matrix.example.yml is present and loadable."""

    def test_example_matrix_file_exists(self):
        assert EXAMPLE_MATRIX_PATH.exists(), (
            f"security_matrix.example.yml not found at {EXAMPLE_MATRIX_PATH}."
        )

    def test_find_example_matrix_path_finds_the_file(self):
        found = _find_example_matrix_path()
        assert found is not None, "_find_example_matrix_path() returned None"
        assert found.exists()

    def test_explicit_matrix_path_takes_precedence(self, tmp_path, monkeypatch):
        configured = tmp_path / "release-matrix.yml"
        configured.write_text("version: 1\n", encoding="utf-8")
        monkeypatch.setenv("AKSARA_SECURITY_MATRIX_PATH", str(configured))

        assert _find_default_matrix_path() == configured

    def test_example_matrix_loads_successfully(self):
        matrix = load_security_matrix(EXAMPLE_MATRIX_PATH)
        assert matrix is not None
        assert matrix.version == 1

    def test_example_matrix_has_required_top_level_sections(self):
        matrix = load_security_matrix(EXAMPLE_MATRIX_PATH)
        assert matrix.metadata is not None
        assert isinstance(matrix.surfaces, list)
        assert isinstance(matrix.actors, list)
        assert isinstance(matrix.risks, list)
        assert isinstance(matrix.scenarios, list)

    def test_example_matrix_has_at_least_one_surface(self):
        matrix = load_security_matrix(EXAMPLE_MATRIX_PATH)
        assert len(matrix.surfaces) >= 1

    def test_example_matrix_has_at_least_one_actor(self):
        matrix = load_security_matrix(EXAMPLE_MATRIX_PATH)
        assert len(matrix.actors) >= 1

    def test_example_matrix_has_at_least_one_risk(self):
        matrix = load_security_matrix(EXAMPLE_MATRIX_PATH)
        assert len(matrix.risks) >= 1

    def test_example_matrix_scenarios_reference_existing_surfaces_actors_and_risks(self):
        matrix = load_security_matrix(EXAMPLE_MATRIX_PATH)
        surface_ids = {s.id for s in matrix.surfaces}
        actor_ids = {a.id for a in matrix.actors}
        risk_ids = {r.id for r in matrix.risks}

        for sc in matrix.scenarios:
            assert sc.surface in surface_ids, (
                f"Scenario '{sc.id}' references unknown surface '{sc.surface}'"
            )
            assert sc.actor in actor_ids, (
                f"Scenario '{sc.id}' references unknown actor '{sc.actor}'"
            )
            assert sc.risk in risk_ids, (
                f"Scenario '{sc.id}' references unknown risk '{sc.risk}'"
            )

    def test_example_matrix_scenarios_have_valid_expected_values(self):
        matrix = load_security_matrix(EXAMPLE_MATRIX_PATH)
        for sc in matrix.scenarios:
            assert sc.expected in VALID_EXPECTED, (
                f"Scenario '{sc.id}' has invalid expected '{sc.expected}'"
            )

    def test_example_matrix_scenarios_have_valid_status_values(self):
        matrix = load_security_matrix(EXAMPLE_MATRIX_PATH)
        for sc in matrix.scenarios:
            assert sc.status in VALID_STATUSES, (
                f"Scenario '{sc.id}' has invalid status '{sc.status}'"
            )

    def test_example_matrix_risks_have_valid_severities(self):
        matrix = load_security_matrix(EXAMPLE_MATRIX_PATH)
        for risk in matrix.risks:
            assert risk.severity in VALID_SEVERITIES, (
                f"Risk '{risk.id}' has invalid severity '{risk.severity}'"
            )

    def test_example_matrix_surfaces_have_no_duplicate_ids(self):
        matrix = load_security_matrix(EXAMPLE_MATRIX_PATH)
        ids = [s.id for s in matrix.surfaces]
        assert len(ids) == len(set(ids)), "Duplicate surface IDs detected"

    def test_example_matrix_actors_have_no_duplicate_ids(self):
        matrix = load_security_matrix(EXAMPLE_MATRIX_PATH)
        ids = [a.id for a in matrix.actors]
        assert len(ids) == len(set(ids)), "Duplicate actor IDs detected"

    def test_example_matrix_risks_have_no_duplicate_ids(self):
        matrix = load_security_matrix(EXAMPLE_MATRIX_PATH)
        ids = [r.id for r in matrix.risks]
        assert len(ids) == len(set(ids)), "Duplicate risk IDs detected"

    def test_example_matrix_scenarios_have_no_duplicate_ids(self):
        matrix = load_security_matrix(EXAMPLE_MATRIX_PATH)
        ids = [sc.id for sc in matrix.scenarios]
        assert len(ids) == len(set(ids)), "Duplicate scenario IDs detected"

    def test_example_matrix_metadata_has_required_fields(self):
        matrix = load_security_matrix(EXAMPLE_MATRIX_PATH)
        assert matrix.metadata.name
        assert matrix.metadata.owner
        assert matrix.metadata.status


# ---------------------------------------------------------------------------
# Validator unit tests (against synthetic matrices)
# ---------------------------------------------------------------------------


class TestValidateSecurityMatrix:
    """Unit tests for validate_security_matrix() against minimal synthetic data."""

    def test_valid_matrix_produces_no_issues(self):
        m = _minimal_valid_matrix()
        issues = validate_security_matrix(m)
        errors = [i for i in issues if i.severity == "error"]
        assert errors == [], f"Unexpected errors: {errors}"

    def test_missing_version_reported(self):
        m = _minimal_valid_matrix()
        del m["version"]
        issues = validate_security_matrix(m)
        assert any(i.field == "version" for i in issues)

    def test_missing_metadata_reported(self):
        m = _minimal_valid_matrix()
        del m["metadata"]
        issues = validate_security_matrix(m)
        assert any(i.field == "metadata" for i in issues)

    def test_missing_surfaces_reported(self):
        m = _minimal_valid_matrix()
        del m["surfaces"]
        issues = validate_security_matrix(m)
        assert any(i.field == "surfaces" for i in issues)

    def test_missing_actors_reported(self):
        m = _minimal_valid_matrix()
        del m["actors"]
        issues = validate_security_matrix(m)
        assert any(i.field == "actors" for i in issues)

    def test_missing_risks_reported(self):
        m = _minimal_valid_matrix()
        del m["risks"]
        issues = validate_security_matrix(m)
        assert any(i.field == "risks" for i in issues)

    def test_missing_scenarios_reported(self):
        m = _minimal_valid_matrix()
        del m["scenarios"]
        issues = validate_security_matrix(m)
        assert any(i.field == "scenarios" for i in issues)

    def test_rejects_duplicate_surface_ids(self):
        m = _minimal_valid_matrix()
        m["surfaces"].append({
            "id": "rest_create",  # duplicate
            "name": "Duplicate", "category": "rest",
            "implemented": True, "description": "dup",
        })
        issues = validate_security_matrix(m)
        assert any("duplicate" in i.message.lower() and "rest_create" in i.message for i in issues)

    def test_rejects_invalid_risk_severity(self):
        m = _minimal_valid_matrix()
        m["risks"][0]["severity"] = "super_critical"  # not in valid set
        issues = validate_security_matrix(m)
        assert any(i.field and "severity" in i.field for i in issues)

    def test_rejects_invalid_scenario_expected_value(self):
        m = _minimal_valid_matrix()
        m["scenarios"][0]["expected"] = "maybe"  # not in valid set
        issues = validate_security_matrix(m)
        assert any(i.field and "expected" in i.field for i in issues)

    def test_rejects_invalid_scenario_status_value(self):
        m = _minimal_valid_matrix()
        m["scenarios"][0]["status"] = "unknown_status"  # not in valid set
        issues = validate_security_matrix(m)
        assert any(i.field and "status" in i.field for i in issues)

    def test_rejects_scenario_referencing_missing_surface(self):
        m = _minimal_valid_matrix()
        m["scenarios"][0]["surface"] = "nonexistent_surface"
        issues = validate_security_matrix(m)
        assert any("nonexistent_surface" in i.message for i in issues)

    def test_rejects_scenario_referencing_missing_actor(self):
        m = _minimal_valid_matrix()
        m["scenarios"][0]["actor"] = "ghost_actor"
        issues = validate_security_matrix(m)
        assert any("ghost_actor" in i.message for i in issues)

    def test_rejects_scenario_referencing_missing_risk(self):
        m = _minimal_valid_matrix()
        m["scenarios"][0]["risk"] = "nonexistent_risk"
        issues = validate_security_matrix(m)
        assert any("nonexistent_risk" in i.message for i in issues)

    def test_surface_missing_required_field_reported(self):
        m = _minimal_valid_matrix()
        del m["surfaces"][0]["category"]
        issues = validate_security_matrix(m)
        assert any("category" in i.field for i in issues)

    def test_actor_missing_description_reported(self):
        m = _minimal_valid_matrix()
        del m["actors"][0]["description"]
        issues = validate_security_matrix(m)
        assert any("description" in i.field for i in issues)

    def test_risk_missing_description_reported(self):
        m = _minimal_valid_matrix()
        del m["risks"][0]["description"]
        issues = validate_security_matrix(m)
        assert any("description" in i.field for i in issues)


class TestLoadSecurityMatrix:
    """Tests for load_security_matrix() file loading."""

    def test_load_with_explicit_path_succeeds(self):
        matrix = load_security_matrix(EXAMPLE_MATRIX_PATH)
        assert matrix.version == 1
        assert len(matrix.surfaces) > 0
        assert len(matrix.actors) > 0
        assert len(matrix.risks) > 0
        assert len(matrix.scenarios) > 0

    def test_load_nonexistent_path_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_security_matrix("/nonexistent/path/security_matrix.yml")

    def test_load_invalid_matrix_raises_value_error(self, tmp_path):
        bad_file = tmp_path / "security_matrix.yml"
        bad_file.write_text("version: 1\n# missing everything else\n", encoding="utf-8")
        with pytest.raises(ValueError, match="validation failed"):
            load_security_matrix(bad_file)

    def test_load_duplicate_surface_raises_value_error(self, tmp_path):
        import yaml
        m = _minimal_valid_matrix()
        m["surfaces"].append({
            "id": "rest_create",
            "name": "Dup", "category": "rest",
            "implemented": True, "description": "dup",
        })
        f = tmp_path / "security_matrix.yml"
        f.write_text(yaml.dump(m), encoding="utf-8")
        with pytest.raises(ValueError, match="validation failed"):
            load_security_matrix(f)
