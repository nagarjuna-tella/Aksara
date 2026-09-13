"""Keep executed PostgreSQL query evidence bound to its source guide and runner."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_query_execution_evidence_preserves_v071_results():
    evidence = json.loads((ROOT / "audit-evidence/v071/query-execution.json").read_text())
    assert evidence["pass"] and evidence["disposable_schema_removed"]
    assert evidence["source_checkout_framework_imports"] is False
    assert "docs/docs/orm/models.md" in evidence["page_sha256"]
    assert evidence["runtime_first_populates_requested_relation"] is False
    assert all(len(digest) == 64 for digest in evidence["page_sha256"].values())
    assert len(evidence["runner_sha256"]) == 64
    assert {"all guide blocks covered", "OR and negation", "missing get handled",
            "offset beyond results", "count existence aggregate", "bounded public projection",
            "insert lifecycle payloads", "update lifecycle payloads",
            "outer rollback removes row but not local callback observation",
            "caught inner failure preserves outer commit", "documented signal disconnection",
            "complete model example persisted both records", "model example decimal and stock values",
            "model example array and JSON values", "model example forward relation is an ID",
            "model example eager relation is available",
            "first does not populate requested eager relation"} <= set(evidence["checks"])
