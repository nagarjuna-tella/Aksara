"""Bind advanced-field documentation to real PostgreSQL/pgvector evidence."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_advanced_field_evidence_is_current():
    evidence = json.loads((ROOT / 'audit-evidence/v071/advanced-field-execution.json').read_text())
    assert evidence['pass'] and evidence['disposable_schema_removed']
    assert evidence['source_checkout_framework_imports'] is False
    assert evidence['pgvector_version']
    for path, digest in evidence['page_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    assert evidence['runner_sha256'] == hashlib.sha256(
        (ROOT / 'scripts/check_public_advanced_fields.py').read_bytes()
    ).hexdigest()
    assert {'all JSON guide blocks execute', 'all Array guide blocks execute',
            'all Vector guide blocks execute', 'nested JSON query returns created row',
            'array append persists through save', 'explicit vector CASE cast persists',
            'vector dimension bool nonfinite and empty values rejected',
            'validation fragment catches both field errors',
            'catalog model decimal and enum persist',
            'catalog model defaults and nullable fields',
            'catalog model foreign key persists'} <= set(evidence['checks'])
