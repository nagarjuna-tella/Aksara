"""Bind bulk documentation evidence without turning an expected defect into runtime approval."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_bulk_evidence_matches_documented_scope():
    evidence = json.loads((ROOT / 'audit-evidence/v071/bulk-execution.json').read_text())
    assert evidence['pass'] and evidence['disposable_schema_removed']
    assert evidence['source_checkout_framework_imports'] is False
    assert evidence['runtime_boolean_timestamp_bulk_update_pass'] is False
    for path, digest in evidence['page_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    assert evidence['runner_sha256'] == hashlib.sha256(
        (ROOT / 'scripts/check_public_bulk.py').read_bytes()
    ).hexdigest()
    assert {'exact atomic helper rolls back earlier batch',
            'unwrapped bulk call can retain earlier batch',
            'BULK-001 reproduced: resolved CASE inferred as text',
            'BULK-001 reproduced: updated_at CASE inferred as text'} <= set(evidence['checks'])
