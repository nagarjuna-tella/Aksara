"""Preserve the v0.7.1 pattern, how-to, and terminology review."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_v071_patterns_howto_glossary_review_remains_historical():
    evidence = json.loads(
        (
            ROOT
            / "audit-evidence/v071/patterns-howto-glossary-reading-review.json"
        ).read_text()
    )

    assert evidence["candidate_acceptance"] is False
    assert len(evidence["page_sha256"]) == 10
    assert {review["page"] for review in evidence["reviews"]} == set(
        evidence["page_sha256"]
    )
    assert all(len(digest) == 64 for digest in evidence["page_sha256"].values())


def test_agent_glossary_does_not_promise_an_autonomous_runtime():
    glossary = (ROOT / "docs/docs/glossary.md").read_text()
    agent = glossary.split("### Agent\n", 1)[1].split("\n### ", 1)[0]

    assert "server-owned Principal" in agent
    assert "does not provide\nan autonomous multi-step agent runtime" in agent
