"""Keep the standalone public testing example tied to installed execution evidence."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_testing_guide_evidence_is_current():
    evidence = json.loads((ROOT / 'audit-evidence/v071/testing-execution.json').read_text())
    assert evidence['pass'] and evidence['tests_passed'] == 3
    assert evidence['source_checkout_framework_imports'] is False
    for path, digest in evidence['page_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    assert evidence['runner_sha256'] == hashlib.sha256(
        (ROOT / 'scripts/check_public_testing.py').read_bytes()
    ).hexdigest()
