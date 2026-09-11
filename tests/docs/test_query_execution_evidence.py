"""Keep executed PostgreSQL query evidence bound to its source guide and runner."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_query_execution_evidence_is_current():
    evidence = json.loads((ROOT / "audit-evidence/v071/query-execution.json").read_text())
    assert evidence["pass"] and evidence["disposable_schema_removed"]
    assert evidence["source_checkout_framework_imports"] is False
    for path, digest in evidence["page_sha256"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    assert evidence["runner_sha256"] == hashlib.sha256((ROOT / "scripts/check_public_queries.py").read_bytes()).hexdigest()
    assert {"all guide blocks covered", "OR and negation", "missing get handled",
            "offset beyond results", "count existence aggregate", "bounded public projection",
            "insert lifecycle payloads", "update lifecycle payloads",
            "outer rollback removes row but not local callback observation",
            "caught inner failure preserves outer commit", "documented signal disconnection"} <= set(evidence["checks"])
