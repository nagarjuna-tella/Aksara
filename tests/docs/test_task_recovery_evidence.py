"""Keep the ordinary-task recovery warning tied to installed evidence."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_task_stale_recovery_negative_evidence_is_current():
    path = ROOT / "audit-evidence/v071/task-stale-recovery.json"
    evidence = json.loads(path.read_text())

    assert evidence["pass"] and evidence["disposable_schema_removed"]
    assert evidence["source_checkout_framework_imports"] is False
    assert evidence["duplicate_calls_observed"] == 2
    assert evidence["recovered_while_first_callable_active"] is True
    assert evidence["ordinary_task_stale_fence_pass"] is False
    assert evidence["reclaimed_result_before_stale_completion"] == "reclaimed_second"
    assert evidence["final_result_after_stale_completion"] == "stale_first"
    for source, digest in evidence["source_sha256"].items():
        assert hashlib.sha256((ROOT / source).read_bytes()).hexdigest() == digest
    for page, digest in evidence["page_sha256"].items():
        assert hashlib.sha256((ROOT / page).read_bytes()).hexdigest() == digest
    assert evidence["runner_sha256"] == hashlib.sha256(
        (ROOT / "scripts/check_task_stale_recovery.py").read_bytes()
    ).hexdigest()


def test_task_guide_states_the_recovery_and_lifecycle_boundaries():
    guide = (ROOT / "docs/docs/advanced/background-tasks.md").read_text()

    assert "this age test is not a heartbeat or ownership\nfence" in guide
    assert "the older callable can later\noverwrite the stored result" in guide
    assert "await worker.stop()" in guide
    assert "await db.disconnect()" in guide


def test_public_truth_summary_tracks_task_recovery_defect():
    summary = json.loads(
        (ROOT / "audit-evidence/v071/public-docs-truth.json").read_text()
    )
    findings = {finding["id"]: finding for finding in summary["known_defects"]}

    assert len(findings) == 19
    assert findings["TASK-001"]["evidence"] == "task-stale-recovery.json"
