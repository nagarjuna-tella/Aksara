"""Keep the complete Start/tutorial reading record tied to current pages."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_start_tutorial_reading_hashes_are_current():
    evidence = json.loads(
        (ROOT / "audit-evidence/v071/start-tutorial-reading-review.json").read_text()
    )

    assert evidence["candidate_acceptance"] is False
    assert len(evidence["page_sha256"]) == 25
    assert {review["page"] for review in evidence["reviews"]} == set(
        evidence["page_sha256"]
    )
    for name, digest in evidence["page_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest


def test_experimental_start_pages_reference_the_released_stable_contract():
    for name in (
        "docs/docs/getting-started/ai-quickstart.md",
        "docs/docs/tutorials/ai-integration.md",
    ):
        page = (ROOT / name).read_text()
        assert "stable v0.7" in page
        assert "stable v0.6" not in page
