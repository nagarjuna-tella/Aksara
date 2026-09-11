"""Keep the executed public tutorial and its recorded evidence in sync.

These are integrity checks, not a replacement for the PostgreSQL/wheel journey.
"""

import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "audit-evidence/v071/first-project-journey.json"
FENCES = re.compile(r'^```python title="([^\"]+)"\n(.*?)^```', re.MULTILINE | re.DOTALL)


def test_tutorial_evidence_matches_executed_sources():
    evidence = json.loads(EVIDENCE.read_text())
    assert evidence["pass"] is True
    assert evidence["source_checkout_imports"] is False
    runner = ROOT / "scripts/run_public_tutorial_gate.py"
    assert evidence["runner_sha256"] == hashlib.sha256(runner.read_bytes()).hexdigest()
    for stage in evidence["stages"]:
        guide = ROOT / stage["guide"]
        assert stage["guide_sha256"] == hashlib.sha256(guide.read_bytes()).hexdigest()
        snippets = dict(FENCES.findall(guide.read_text()))
        assert snippets.keys() == stage["files"].keys()
        for title, source in snippets.items():
            ast.parse(source, filename=f"{guide.name}:{title}")
            assert stage["files"][title] == hashlib.sha256(source.encode()).hexdigest()
    assert evidence["api_tests_passed"] == sum(stage["api_tests_passed"] for stage in evidence["stages"])


def test_tutorial_evidence_does_not_record_database_credentials():
    text = EVIDENCE.read_text()
    assert not re.search(r"postgres(?:ql)?://[^\s]+:[^\s]+@", text)
    # Ephemeral database passwords are 24 random bytes rendered as hex.
    assert not re.search(r"(?<![a-f0-9])[a-f0-9]{48}(?![a-f0-9])", text)
    assert not re.search(r'"(?:password|token|dsn|database_url)"\s*:', text)
