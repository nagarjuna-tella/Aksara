"""Verify SDK probe provenance without hiding the compiler failure it records."""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_sdk_probe_uses_current_documented_inputs():
    evidence = json.loads((ROOT / "audit-evidence/v071/typescript-sdk-probe.json").read_text())
    assert evidence["source_checkout_framework_imports"] is False
    runner = ROOT / "scripts/check_public_sdk.py"
    guide = ROOT / "docs/docs/how-to/typescript-client.md"
    assert evidence["runner_sha256"] == hashlib.sha256(runner.read_bytes()).hexdigest()
    assert evidence["documentation_sha256"] == hashlib.sha256(guide.read_bytes()).hexdigest()
    source = (ROOT / "docs/docs/getting-started/first-project.md").read_text()
    snippets = dict(re.findall(r'^```python title="([^\"]+)"\n(.*?)^```', source, re.MULTILINE | re.DOTALL))
    for file, digest in evidence["input_sha256"].items():
        assert hashlib.sha256(snippets[file].encode()).hexdigest() == digest
