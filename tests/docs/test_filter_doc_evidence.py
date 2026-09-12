"""Bind the documented filter ViewSet to installed HTTP/database evidence."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_filter_documentation_evidence_is_current():
    evidence = json.loads((ROOT / 'audit-evidence/v071/filter-doc-execution.json').read_text())
    assert evidence['pass'] and evidence['disposable_schema_removed']
    assert evidence['source_checkout_framework_imports'] is False
    for path, digest in evidence['page_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    assert evidence['runner_sha256'] == hashlib.sha256(
        (ROOT / 'scripts/check_public_filters.py').read_bytes()
    ).hexdigest()
    assert {'anonymous generated list denied', 'combined documented filters',
            'router filter allowlist excludes subject', 'pagination bounds rejected',
            'relation search path rejected'} <= set(evidence['checks'])
