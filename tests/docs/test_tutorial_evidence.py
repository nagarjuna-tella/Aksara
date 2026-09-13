"""Keep the executed public tutorial and its recorded evidence in sync.

These are integrity checks, not a replacement for the PostgreSQL/wheel journey.
"""

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "audit-evidence/v071/first-project-journey.json"
FENCES = re.compile(r'^```python title="([^\"]+)"\n(.*?)^```', re.MULTILINE | re.DOTALL)


def test_tutorial_evidence_preserves_v071_results_and_current_snippets_parse():
    evidence = json.loads(EVIDENCE.read_text())
    assert evidence["pass"] is True
    assert evidence["source_checkout_imports"] is False
    assert len(evidence["runner_sha256"]) == 64
    for stage in evidence["stages"]:
        guide = ROOT / stage["guide"]
        assert len(stage["guide_sha256"]) == 64
        assert all(len(digest) == 64 for digest in stage["files"].values())
        snippets = dict(FENCES.findall(guide.read_text()))
        for title, source in snippets.items():
            ast.parse(source, filename=f"{guide.name}:{title}")
    assert evidence["api_tests_passed"] == sum(stage["api_tests_passed"] for stage in evidence["stages"])


def test_tutorial_evidence_does_not_record_database_credentials():
    text = EVIDENCE.read_text()
    assert not re.search(r"postgres(?:ql)?://[^\s]+:[^\s]+@", text)
    # Ephemeral database passwords are 24 random bytes rendered as hex.
    assert not re.search(r"(?<![a-f0-9])[a-f0-9]{48}(?![a-f0-9])", text)
    assert not re.search(r'"(?:password|token|dsn|database_url)"\s*:', text)
