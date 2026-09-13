"""Integrity checks for the finite v0.7.2 audit-closure release ledger."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "audit-evidence/v072"
EXPECTED = {
    "CFG-001", "SDK-001", "STORAGE-001", "ACTION-001", "TASK-001",
    "AIPROVIDER001", "GAP001", "AIFLOW001", "AIFLOW002", "EX-001",
    "SCAFFOLD-001", "SOFTDELETE001", "FIXTURE001", "FIXTURE002",
    "FIXTURE003", "INSPECTOR001", "ADMINWIDGET001", "MIGRATION-001",
    "RELATION001", "BULK-001", "PAGINATION-001", "TESTING-001",
}


def test_findings_closure_is_exact_complete_and_linked():
    ledger = json.loads((EVIDENCE / "findings-closure.json").read_text())
    findings = ledger["findings"]
    ids = [item["id"] for item in findings]
    assert len(ids) == len(set(ids)) == 22
    assert set(ids) == EXPECTED
    assert ledger["summary"] == {
        "total": 22,
        "fixed": 22,
        "disproved": 0,
        "already_resolved": 0,
        "unresolved": 0,
    }
    assert {item["final_disposition"] for item in findings} == {"FIXED"}
    for item in findings:
        assert item["baseline_reproduced"] is True
        assert (ROOT / item["baseline_artifact"]).is_file()
        assert (ROOT / item["candidate_artifact"]).is_file()
        assert item["production_files"]
        assert all((ROOT / path).is_file() for path in item["production_files"])
        assert item["tests"] and all((ROOT / path).is_file() for path in item["tests"])


def test_change_map_has_no_unmapped_production_or_dependency_change():
    change_map = json.loads((EVIDENCE / "change-map.json").read_text())
    assert change_map["pass"] is True
    assert change_map["runtime_changes_limited_to_22_findings"] is True
    assert change_map["dependencies_changed"] is False
    assert change_map["unmapped_production_files"] == []
    assert change_map["schema_migrations_changed"] == [
        "aksara/core/migrations/0003_task_claim_ownership.py"
    ]
    mapped = {
        issue
        for item in change_map["changed_production_files"].values()
        for issue in item["issue_ids"]
    }
    assert mapped == EXPECTED
