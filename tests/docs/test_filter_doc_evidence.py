"""Preserve the v0.7.1 filter HTTP/database evidence."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_v071_filter_documentation_evidence_remains_historical():
    evidence = json.loads((ROOT / 'audit-evidence/v071/filter-doc-execution.json').read_text())
    assert evidence['pass'] and evidence['disposable_schema_removed']
    assert evidence['source_checkout_framework_imports'] is False
    assert evidence['page_sha256']
    assert all(len(digest) == 64 for digest in evidence['page_sha256'].values())
    assert len(evidence['runner_sha256']) == 64
    assert {'anonymous generated list denied', 'combined documented filters',
            'router filter allowlist excludes subject', 'pagination bounds rejected',
            'relation search path rejected'} <= set(evidence['checks'])
