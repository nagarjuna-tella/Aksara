"""Keep the executable setup guide bound to its installed-wheel evidence."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_setup_execution_evidence_is_current():
    data = json.loads((ROOT / 'audit-evidence/v071/setup-doc-execution.json').read_text())
    assert data['pass'] and data['source_checkout_framework_imports'] is False
    assert data['temporary_files_removed'] and data['existing_database_recreated'] is False
    assert len(data['checks']) == 5
    assert len(data['basic_file_inventory']) == 18
    assert len(data['startapp_file_inventory']) == 5
    assert 'urls.py' not in data['startapp_file_inventory']
    for name, digest in data['page_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    assert data['runner_sha256'] == hashlib.sha256(
        (ROOT / 'scripts/check_setup_docs.py').read_bytes()
    ).hexdigest()
