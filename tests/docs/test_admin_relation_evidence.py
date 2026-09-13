"""Preserve the v0.7.1 Admin relation evidence as historical evidence."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_v071_admin_relation_evidence_remains_historical():
    evidence = json.loads((ROOT / 'audit-evidence/v071/admin-relation-execution.json').read_text())
    assert evidence['pass'] and evidence['disposable_schema_removed']
    assert evidence['source_checkout_framework_imports'] is False
    assert 'docs/docs/orm/relations.md' in evidence['page_sha256']
    assert all(len(digest) == 64 for digest in evidence['page_sha256'].values())
    assert evidence['runner_sha256'] == hashlib.sha256((ROOT / 'scripts/check_public_admin_relations.py').read_bytes()).hexdigest()
    assert {'owner allowed with database lookup', 'other staff denied',
            'nullable missing author denied', 'eager accessor is synchronous model',
            'unloaded related access raises ValueError', 'reverse FK filter executes and returns rows',
            'relation example created the post', 'relation example M2M membership',
            'relation example reverse FK', 'relation example reverse O2O',
            'relation example self reference', 'relation example reverse M2M'} <= set(evidence['checks'])
