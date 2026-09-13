"""Preserve the v0.7.1 bulk evidence and its expected defect observations."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_v071_bulk_evidence_remains_historical():
    evidence = json.loads((ROOT / 'audit-evidence/v071/bulk-execution.json').read_text())
    assert evidence['pass'] and evidence['disposable_schema_removed']
    assert evidence['source_checkout_framework_imports'] is False
    assert evidence['runtime_boolean_timestamp_bulk_update_pass'] is False
    assert evidence['page_sha256']
    assert all(len(digest) == 64 for digest in evidence['page_sha256'].values())
    assert evidence['runner_sha256'] == hashlib.sha256(
        (ROOT / 'scripts/check_public_bulk.py').read_bytes()
    ).hexdigest()
    assert {'exact atomic helper rolls back earlier batch',
            'unwrapped bulk call can retain earlier batch',
            'BULK-001 reproduced: resolved CASE inferred as text',
            'BULK-001 reproduced: updated_at CASE inferred as text'} <= set(evidence['checks'])
