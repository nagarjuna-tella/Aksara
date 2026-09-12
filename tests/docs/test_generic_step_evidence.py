"""Keep exact generic-relation/step execution evidence tied to its source."""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_generic_step_evidence_is_current():
    path = ROOT / 'audit-evidence/v071/generic-step-execution.json'
    evidence = json.loads(path.read_text())
    assert evidence['pass'] and evidence['disposable_schema_removed']
    assert evidence['source_checkout_framework_imports'] is False
    for name, digest in evidence['page_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    assert evidence['runner_sha256'] == hashlib.sha256(
        (ROOT / 'scripts/check_public_generic_steps.py').read_bytes()
    ).hexdigest()
    assert {
        'exact generic example persists and resolves',
        'fresh dangling target lookup raises DoesNotExist',
        'instance accessor retains resolved cache',
        'exact step example reuses completed result',
        'exact Decimal codec first and cached result',
        'normal competing claim rejected',
        'force bypasses running claim',
        'original completion can overwrite forced result',
        'task cancellation leaves running state',
    } <= set(evidence['checks'])
    assert not re.search(r'postgres(?:ql)?://[^\s]+:[^\s]+@', path.read_text())
