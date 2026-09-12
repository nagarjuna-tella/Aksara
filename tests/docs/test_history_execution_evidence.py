"""Bind the durable history helper to its installed execution evidence."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_history_execution_evidence_is_current():
    evidence = json.loads((ROOT / 'audit-evidence/v071/history-execution.json').read_text())
    assert evidence['pass'] and evidence['disposable_schema_removed']
    assert evidence['source_checkout_framework_imports'] is False
    for path, digest in evidence['page_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    assert evidence['runner_sha256'] == hashlib.sha256((ROOT / 'scripts/check_public_history.py').read_bytes()).hexdigest()
    assert {'history is newest first', 'limit truncates recent list',
            'registered action scope checked', 'different namespace cannot select operation',
            'above maximum limit rejected',
            'retired terminal action permits same tenant read without removed scope'} <= set(evidence['checks'])
