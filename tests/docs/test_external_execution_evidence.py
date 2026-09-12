"""Bind external-effect guidance to its installed PostgreSQL probe."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_external_execution_evidence_is_current():
    evidence = json.loads((ROOT / 'audit-evidence/v071/external-execution.json').read_text())
    assert evidence['pass'] and evidence['disposable_schema_removed']
    assert evidence['source_checkout_framework_imports'] is False
    for path, digest in evidence['page_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    assert evidence['runner_sha256'] == hashlib.sha256((ROOT / 'scripts/check_public_external_effects.py').read_bytes()).hexdigest()
    assert {'retry supplies identical downstream key', 'simulated provider deduplicates',
            'public helper result persisted', 'unsafe recovery fails explicitly',
            'unknown does not imply unsent', 'revoked scope prevents provider call'} <= set(evidence['checks'])
