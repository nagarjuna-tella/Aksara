"""Bind local media/email evidence to the exact public example."""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_media_example_evidence_is_current():
    evidence = json.loads((ROOT / "audit-evidence/v071/media-email.json").read_text())
    page = ROOT / "docs/docs/advanced/media-and-email.md"
    runner = ROOT / "scripts/check_public_media.py"
    source = re.search(r'```python title="check_media.py"\n(.*?)```', page.read_text(), re.DOTALL).group(1)
    assert evidence["pass"] is True
    assert evidence["source_checkout_framework_imports"] is False
    assert evidence["page_sha256"] == hashlib.sha256(page.read_bytes()).hexdigest()
    assert evidence["snippet_sha256"] == hashlib.sha256(source.encode()).hexdigest()
    assert evidence["runner_sha256"] == hashlib.sha256(runner.read_bytes()).hexdigest()
