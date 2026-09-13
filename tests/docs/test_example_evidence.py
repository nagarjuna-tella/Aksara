"""Evidence freshness for example startup and documented limitations."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "audit-evidence/v071"


def test_v071_example_execution_evidence_remains_historical():
    evidence = json.loads((EVIDENCE / "example-execution.json").read_text())
    assert evidence["pass"] is True
    assert evidence["source_checkout_framework_imports"] is False
    assert len(evidence["runner_sha256"]) == 64
    assert {entry["example"] for entry in evidence["observations"]} == {
        "basic_app", "blog", "crm", "multitenant", "ai_providers"
    }
    for entry in evidence["observations"]:
        assert entry["startup"] == "completed"
        assert entry["files"]
        assert all(len(digest) == 64 for digest in entry["files"].values())


def test_every_example_has_a_current_review():
    review = json.loads((EVIDENCE / "example-review.json").read_text())
    examples = {p.name for p in (ROOT / "examples").iterdir() if (p / "README.md").exists()}
    assert {row["example"] for row in review["examples"]} == examples
    for row in review["examples"]:
        assert row["classification"] in {"KEEP", "REWRITE", "MERGE", "REMOVE", "REPLACE"}
        readme = ROOT / "examples" / row["example"] / "README.md"
        assert hashlib.sha256(readme.read_bytes()).hexdigest() == row["readme_sha256"]
        assert (EVIDENCE / row["execution_evidence"]).is_file()
