"""Bind the public outbox helper to its installed PostgreSQL execution evidence."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_outbox_execution_evidence_is_current():
    evidence = json.loads((ROOT / "audit-evidence/v071/outbox-execution.json").read_text())
    assert evidence["pass"] and evidence["disposable_schema_removed"]
    assert evidence["source_checkout_framework_imports"] is False
    for path, digest in evidence["page_sha256"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    assert evidence["runner_sha256"] == hashlib.sha256((ROOT / "scripts/check_public_outbox.py").read_bytes()).hexdigest()
    assert {"documented defaults", "namespace selection", "none is not all tenants",
            "export failure leaves authoritative state ready",
            "duplicate payload after acceptance ambiguity"} <= set(evidence["checks"])
