"""Ensure the Admin relation policy is tested with a real installed database path."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_admin_relation_evidence_is_current():
    evidence = json.loads((ROOT / 'audit-evidence/v071/admin-relation-execution.json').read_text())
    assert evidence['pass'] and evidence['disposable_schema_removed']
    assert evidence['source_checkout_framework_imports'] is False
    for path, digest in evidence['page_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    assert evidence['runner_sha256'] == hashlib.sha256((ROOT / 'scripts/check_public_admin_relations.py').read_bytes()).hexdigest()
    assert {'owner allowed with database lookup', 'other staff denied',
            'nullable missing author denied', 'eager accessor is synchronous model',
            'unloaded related access raises ValueError', 'reverse FK filter executes and returns rows'} <= set(evidence['checks'])
