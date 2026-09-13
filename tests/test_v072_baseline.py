"""Integrity checks for the immutable v0.7.2 audit-closure baseline."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "audit-evidence" / "v072-baseline"
EXPECTED_FINDINGS = {
    "CFG-001",
    "SDK-001",
    "STORAGE-001",
    "ACTION-001",
    "TASK-001",
    "AIPROVIDER001",
    "GAP001",
    "AIFLOW001",
    "AIFLOW002",
    "EX-001",
    "SCAFFOLD-001",
    "SOFTDELETE001",
    "FIXTURE001",
    "FIXTURE002",
    "FIXTURE003",
    "INSPECTOR001",
    "ADMINWIDGET001",
    "MIGRATION-001",
    "RELATION001",
    "BULK-001",
    "PAGINATION-001",
    "TESTING-001",
}


def _load(name: str) -> dict[str, object]:
    return json.loads((BASELINE / name).read_text())


def test_public_v071_baseline_is_exact_and_external() -> None:
    source = _load("source.json")
    wheel = _load("public-wheel.json")
    publication = _load("publication.json")

    assert source["package_version"] == "0.7.1"
    assert source["released_main_and_tag_trees_equal"] is True
    assert wheel["version"] == "0.7.1"
    assert wheel["source_checkout_framework_imports"] is False
    assert wheel["matches_pypi_digest"] is True
    assert publication["pypi"]["version"] == "0.7.1"
    assert publication["github_release"]["tag_name"] == "v0.7.1"


def test_baseline_ledger_contains_exactly_22_reproduced_findings() -> None:
    ledger = _load("findings.json")
    findings = ledger["findings"]
    ids = [finding["id"] for finding in findings]

    assert len(ids) == 22
    assert len(ids) == len(set(ids))
    assert set(ids) == EXPECTED_FINDINGS
    assert ledger["reproduced"] == 22
    assert ledger["not_reproducible"] == 0
    assert all(
        finding["baseline_classification"] == "reproduced_defect"
        and finding["actual_v071_behavior"]
        and finding["expected_correct_behavior"]
        and (BASELINE / finding["evidence_artifact"]).is_file()
        for finding in findings
    )


def test_protected_untracked_directories_are_inventory_only() -> None:
    protected = _load("protected-untracked.json")
    assert protected["preservation_required"] is True
    assert {entry["path"] for entry in protected["directories"]} == {
        "audit-evidence/current-state/",
        "audit-evidence/v055/",
        "benchmarks/results/",
    }
