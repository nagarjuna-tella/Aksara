"""Keep the field extension example tied to real installed conversion/persistence evidence."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_custom_field_evidence_is_current():
    evidence = json.loads((ROOT / 'audit-evidence/v071/custom-field-execution.json').read_text())
    assert evidence['pass'] and evidence['disposable_schema_removed']
    assert evidence['source_checkout_framework_imports'] is False
    for path, digest in evidence['page_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    assert evidence['runner_sha256'] == hashlib.sha256(
        (ROOT / 'scripts/check_public_custom_field.py').read_bytes()
    ).hexdigest()
    assert {'autodetected schema uses VARCHAR24',
            'generated unique constraint rejects normalized duplicate',
            'save preparation updates instance',
            'bulk create prepares and reloads',
            'upsert normalized conflict returns existing'} <= set(evidence['checks'])
