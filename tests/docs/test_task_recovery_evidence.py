"""Preserve v0.7.1 task evidence and verify the current recovery contract."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_v071_task_stale_recovery_evidence_remains_historical():
    path = ROOT / "audit-evidence/v071/task-stale-recovery.json"
    evidence = json.loads(path.read_text())

    assert evidence["pass"] and evidence["disposable_schema_removed"]
    assert evidence["source_checkout_framework_imports"] is False
    assert evidence["duplicate_calls_observed"] == 2
    assert evidence["recovered_while_first_callable_active"] is True
    assert evidence["ordinary_task_stale_fence_pass"] is False
    assert evidence["reclaimed_result_before_stale_completion"] == "reclaimed_second"
    assert evidence["final_result_after_stale_completion"] == "stale_first"
    assert set(evidence["source_sha256"]) == {"aksara/tasks.py"}
    assert set(evidence["page_sha256"]) == {
        "docs/docs/advanced/background-tasks.md"
    }
    assert all(len(digest) == 64 for digest in evidence["source_sha256"].values())
    assert all(len(digest) == 64 for digest in evidence["page_sha256"].values())
    assert len(evidence["runner_sha256"]) == 64


def test_task_guide_states_the_recovery_and_lifecycle_boundaries():
    guide = (ROOT / "docs/docs/advanced/background-tasks.md").read_text()

    assert "a unique claim token" in guide
    assert "previous claim token can no longer renew the lease or write" in guide
    assert "external effects inside ordinary\ntask code must remain safe to repeat" in guide
    assert "await worker.stop()" in guide
    assert "await db.disconnect()" in guide


def test_public_truth_summary_tracks_task_recovery_defect():
    summary = json.loads(
        (ROOT / "audit-evidence/v071/public-docs-truth.json").read_text()
    )
    findings = {finding["id"]: finding for finding in summary["known_defects"]}

    assert len(findings) == 22
    assert findings["TASK-001"]["evidence"] == "task-stale-recovery.json"
    assert findings["GAP001"]["evidence"] == "gap-analysis-version-contract.json"
    assert findings["AIFLOW001"]["evidence"] == "installed-doc-imports.json"
    assert findings["AIFLOW002"]["evidence"] == "snippet-coverage-review.json"
