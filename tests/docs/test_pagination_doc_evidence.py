"""Preserve HTTP pagination defect evidence without claiming runtime success."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pagination_evidence_is_current():
    evidence = json.loads((ROOT / 'audit-evidence/v071/pagination-doc-execution.json').read_text())
    assert evidence['pass'] and evidence['disposable_schema_removed']
    assert evidence['source_checkout_framework_imports'] is False
    assert evidence['runtime_custom_pagination_metadata_pass'] is False
    for path, digest in evidence['page_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    assert evidence['runner_sha256'] == hashlib.sha256(
        (ROOT / 'scripts/check_public_pagination.py').read_bytes()
    ).hexdigest()
    assert {'documented default pagination works',
            'PAGINATION-001 page metadata discarded',
            'PAGINATION-001 HTTP next cursor discarded',
            'direct view provides next cursor'} <= set(evidence['checks'])
