"""Bind executable migration reference files to installed executor evidence."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_migration_documentation_evidence_is_current():
    evidence = json.loads((ROOT / 'audit-evidence/v071/migration-doc-execution.json').read_text())
    assert evidence['pass'] and evidence['disposable_schema_removed']
    assert evidence['source_checkout_framework_imports'] is False
    for path, digest in evidence['page_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    assert evidence['runner_sha256'] == hashlib.sha256(
        (ROOT / 'scripts/check_public_migrations.py').read_bytes()
    ).hexdigest()
    assert {'exact initial migration applies', 'exact upgrade migration applies',
            'upgrade preserves and backfills existing row', 'repeat run has no pending work',
            'failed schema change rolled back', 'failed migration not recorded',
            'edited applied file rejected'} <= set(evidence['checks'])
