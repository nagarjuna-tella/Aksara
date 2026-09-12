"""Keep the final public-sample audit tied to current executable evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "audit-evidence" / "v071"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_snippet_coverage_review_is_current_and_scoped() -> None:
    review = json.loads((EVIDENCE / "snippet-coverage-review.json").read_text())

    assert review["pass"] is True
    assert review["candidate_acceptance"] is False
    assert review["source_checkout_framework_imports"] is False
    assert review["inventory"] == {
        "public_markdown_files": 169,
        "current_sample_files": 165,
        "historical_files_excluded": [
            "docs/docs/changelog.md",
            "docs/docs/notes/index.md",
            "docs/docs/notes/v0-5-49-announcement.md",
            "docs/docs/notes/v0-5-49-security-architecture.md",
        ],
        "all_fences": 600,
        "historical_fences": 5,
        "current_fences": 595,
        "current_fences_by_language": {
            "bash": 184,
            "css": 1,
            "dotenv": 12,
            "http": 1,
            "json": 15,
            "python": 348,
            "sql": 1,
            "text": 14,
            "typescript": 1,
            "unlabeled": 18,
        },
    }
    assert review["automated_coverage"]["python"] == {
        "blocks": 348,
        "all_compile": True,
        "all_aksara_imports_resolve": True,
        "fresh_workflow_example_executes": True,
    }
    assert review["automated_coverage"]["json"] == {
        "blocks": 15,
        "all_parse": True,
        "selected_installed_response_models": 5,
    }

    referenced = {
        name
        for names in review["execution_evidence"].values()
        for name in names
    }
    assert referenced == set(review["evidence_sha256"])
    assert len(referenced) == 31
    for name, digest in review["evidence_sha256"].items():
        assert _digest(EVIDENCE / name) == digest
    for name, result in review["evidence_results"].items():
        assert name in referenced
        assert result is True or result == "passed"
    for name, digest in review["page_sha256"].items():
        assert _digest(ROOT / name) == digest
    assert review["runner_sha256"] == _digest(
        ROOT / "scripts" / "check_public_snippet_coverage.py"
    )


def test_workflow_import_defects_and_workaround_are_explicit() -> None:
    imports = json.loads((EVIDENCE / "installed-doc-imports.json").read_text())
    observation = imports["workflow_import_observation"]
    page = (ROOT / "docs" / "docs" / "ai-mode" / "workflows.md").read_text()

    assert observation["direct_import_exit"] == 1
    assert "partially initialized module 'aksara.ai.workflows'" in observation[
        "direct_import_error"
    ]
    assert observation["documented_snippet_exit"] == 0
    assert "with 3 steps (2 inspect, 1 run_test)" in observation[
        "documented_snippet_stdout"
    ]
    assert "AIFLOW001" in page
    assert "AIFLOW002" in page
    assert "from aksara.studio import" in page
    assert "from aksara.ai.workflows import" not in page
