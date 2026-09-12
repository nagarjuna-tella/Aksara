"""Keep the reference/tooling reading record tied to current pages."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_reference_tooling_reading_hashes_are_current():
    evidence = json.loads(
        (ROOT / "audit-evidence/v071/reference-tooling-reading-review.json").read_text()
    )

    assert evidence["candidate_acceptance"] is False
    assert evidence["validation"] == {
        "isolated_cli_declaration_check": "117 command/group declarations passed",
        "focused_tests": "237 passed",
        "new_contradictions": 0,
    }
    assert len(evidence["page_sha256"]) == 19
    assert {review["page"] for review in evidence["reviews"]} == set(
        evidence["page_sha256"]
    )
    for name, digest in evidence["page_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
