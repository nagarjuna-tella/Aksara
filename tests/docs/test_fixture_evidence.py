"""Bind the fixture guide to its installed PostgreSQL observations."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_fixture_evidence_is_current():
    data = json.loads((ROOT / 'audit-evidence/v071/fixture-execution.json').read_text())
    assert data['pass'] and data['disposable_schema_removed']
    assert data['source_checkout_framework_imports'] is False
    assert data['runtime_export_restore_roundtrip'] is False
    assert len(data['checks']) == 13
    for name, digest in data['page_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    assert data['runner_sha256'] == hashlib.sha256(
        (ROOT / 'scripts/check_public_fixtures.py').read_bytes()
    ).hexdigest()
