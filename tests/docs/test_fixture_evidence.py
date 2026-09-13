"""Preserve the v0.7.1 fixture observations as historical evidence."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_v071_fixture_evidence_remains_historical():
    data = json.loads((ROOT / 'audit-evidence/v071/fixture-execution.json').read_text())
    assert data['pass'] and data['disposable_schema_removed']
    assert data['source_checkout_framework_imports'] is False
    assert data['runtime_export_restore_roundtrip'] is False
    assert len(data['checks']) == 13
    assert set(data['page_sha256']) == {'docs/docs/orm/fixtures.md'}
    assert all(len(digest) == 64 for digest in data['page_sha256'].values())
    assert data['runner_sha256'] == hashlib.sha256(
        (ROOT / 'scripts/check_public_fixtures.py').read_bytes()
    ).hexdigest()
