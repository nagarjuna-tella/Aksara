"""Preserve the v0.7.1 HTTP pagination defect evidence."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_v071_pagination_evidence_remains_historical():
    evidence = json.loads((ROOT / 'audit-evidence/v071/pagination-doc-execution.json').read_text())
    assert evidence['pass'] and evidence['disposable_schema_removed']
    assert evidence['source_checkout_framework_imports'] is False
    assert evidence['runtime_custom_pagination_metadata_pass'] is False
    assert evidence['page_sha256']
    assert all(len(digest) == 64 for digest in evidence['page_sha256'].values())
    assert evidence['runner_sha256'] == hashlib.sha256(
        (ROOT / 'scripts/check_public_pagination.py').read_bytes()
    ).hexdigest()
    assert {'documented default pagination works',
            'PAGINATION-001 page metadata discarded',
            'PAGINATION-001 HTTP next cursor discarded',
            'direct view provides next cursor'} <= set(evidence['checks'])
