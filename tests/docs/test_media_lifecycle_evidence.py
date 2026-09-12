"""Keep local persisted-media evidence current and bounded."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_persisted_media_evidence_is_current():
    evidence = json.loads((ROOT / 'audit-evidence/v071/media-lifecycle.json').read_text())
    assert evidence['pass'] and evidence['disposable_schema_removed']
    assert evidence['source_checkout_framework_imports'] is False
    for path, digest in evidence['page_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    assert evidence['runner_sha256'] == hashlib.sha256(
        (ROOT / 'scripts/check_public_media_lifecycle.py').read_bytes()
    ).hexdigest()
    assert {'replacement preserves old stored file',
            'wrapper deletion does not persist database clearing',
            'rollback leaves externally stored bytes',
            'model deletion leaves stored bytes',
            'explicit orphan cleanup removes files'} <= set(evidence['checks'])
