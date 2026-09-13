"""Keep the field extension example tied to real installed conversion/persistence evidence."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_v071_custom_field_evidence_remains_historical():
    evidence = json.loads((ROOT / 'audit-evidence/v071/custom-field-execution.json').read_text())
    assert evidence['pass'] and evidence['disposable_schema_removed']
    assert evidence['source_checkout_framework_imports'] is False
    assert evidence['page_sha256']
    assert all(len(digest) == 64 for digest in evidence['page_sha256'].values())
    assert len(evidence['runner_sha256']) == 64
    assert {'autodetected schema uses VARCHAR24',
            'generated unique constraint rejects normalized duplicate',
            'save preparation updates instance',
            'bulk create prepares and reloads',
            'upsert normalized conflict returns existing'} <= set(evidence['checks'])
