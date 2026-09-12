"""Keep the durable approval how-to bound to installed execution evidence."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_approval_execution_evidence_is_current():
    evidence = json.loads((ROOT / 'audit-evidence/v071/approval-execution.json').read_text())
    assert evidence['pass'] and evidence['disposable_schema_removed']
    assert evidence['source_checkout_framework_imports'] is False
    for path, digest in evidence['page_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    assert evidence['runner_sha256'] == hashlib.sha256((ROOT / 'scripts/check_public_approvals.py').read_bytes()).hexdigest()
    assert {'reviewer role required', 'action scopes still required',
            'provenance must match', 'other tenant cannot select operation',
            'approval returns ready', 'second decision conflicts',
            'rejection returns cancelled', 'expired approval returns expired'} <= set(evidence['checks'])
