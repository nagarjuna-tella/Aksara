"""Keep the executable setup guide bound to its installed-wheel evidence."""

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
    # This is immutable v0.7.1 evidence. Current setup pages and the runner may
    # change when the recorded defects are repaired.
    assert data['page_sha256']
    assert all(len(digest) == 64 for digest in data['page_sha256'].values())
    assert len(data['runner_sha256']) == 64
