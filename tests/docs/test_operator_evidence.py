"""Keep operator command evidence and reading conclusions tied to reviewed pages."""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_operator_evidence_matches_reviewed_sources():
    evidence = ROOT / "audit-evidence/v071"
    cli = json.loads((evidence / "operator-cli.json").read_text())
    assert cli["pass"] is True and cli["source_checkout_imports"] is False
    runner = ROOT / "scripts/check_public_operator_docs.py"
    assert cli["runner_sha256"] == hashlib.sha256(runner.read_bytes()).hexdigest()
    page = ROOT / cli["page"]
    assert cli["page_sha256"] == hashlib.sha256(page.read_bytes()).hexdigest()
    commands = set(re.findall(r"aksara doctor [a-z-]+(?: --[a-z-]+(?: json)?)*", page.read_text()))
    assert commands == {entry["command"] for entry in cli["commands"]}
    assert all(entry["help_exit"] == 0 for entry in cli["commands"])
    reading = json.loads((evidence / "operator-reading.json").read_text())
    for answer in reading["answers"]:
        page = ROOT / answer["page"]
        assert answer["page_sha256"] == hashlib.sha256(page.read_bytes()).hexdigest()
        assert answer["heading"] in page.read_text()
