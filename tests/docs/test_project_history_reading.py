"""Keep project-history and roadmap review tied to current public truth."""

import hashlib
import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_project_history_reading_preserves_v071_review_inventory():
    evidence = json.loads(
        (ROOT / "audit-evidence/v071/project-history-reading-review.json").read_text()
    )

    assert evidence["candidate_acceptance"] is False
    assert len(evidence["page_sha256"]) == 10
    assert {review["page"] for review in evidence["reviews"]} == set(
        evidence["page_sha256"]
    )
    assert all(len(digest) == 64 for digest in evidence["page_sha256"].values())


def test_every_inventoried_public_page_has_a_reading_disposition():
    evidence_root = ROOT / "audit-evidence/v071"
    inventory = json.loads(
        (evidence_root / "public-page-review-inventory.json").read_text()
    )
    inventoried = {page["path"] for page in inventory["pages"]}
    reviewed = set()

    for path in evidence_root.glob("*reading*.json"):
        evidence = json.loads(path.read_text())
        page_hashes = evidence.get("page_sha256", {})
        if isinstance(page_hashes, dict):
            reviewed.update(page_hashes)
        for review in evidence.get("complete_page_reading", []):
            reviewed.add(review["page"])

    assert inventoried == reviewed


def test_manual_acceptance_summary_is_current_and_scoped():
    evidence = json.loads(
        (ROOT / "audit-evidence/v071/manual-acceptance-review.json").read_text()
    )

    assert evidence["status"] == "scoped_author_review_complete"
    assert evidence["candidate_acceptance"] is False
    assert evidence["inventory"]["public_pages"] == 163
    assert evidence["inventory"]["pages_with_explicit_reading_disposition"] == 163
    assert evidence["inventory"]["missing_pages"] == []
    assert evidence["contradictions"] == {"registered": 80, "latest": "PT-080"}
    assert evidence["functional_findings"]["registered"] == 22
    assert evidence["functional_findings"]["runtime_fixes_included"] is False
    for name, digest in evidence["source_sha256"].items():
        assert _digest(ROOT / name) == digest

    external = json.loads((ROOT / "audit-evidence/v071/external-links.json").read_text())
    rendered = json.loads((ROOT / "audit-evidence/v071/rendered-links.json").read_text())
    assert evidence["fresh_checks"]["external_links_reachable"] == external["counts"][
        "reachable"
    ]
    assert evidence["fresh_checks"]["rendered_local_links_assets"] == rendered[
        "local_links_checked"
    ]


def test_contradiction_register_is_complete_and_ordered():
    report = (ROOT / "AKSARA_V071_PUBLIC_TRUTH_AUDIT.md").read_text()
    identifiers = [
        int(value)
        for value in re.findall(r"^\| PT-(\d{3}) \|", report, re.MULTILINE)
    ]

    assert identifiers == list(range(1, 81))


def test_live_roadmap_and_release_links_use_the_public_repository():
    roadmap = (ROOT / "docs/docs/roadmap.md").read_text()
    changelog = (ROOT / "docs/docs/changelog.md").read_text()

    assert "blob/codex/v071-public-truth-and-roadmap/" not in roadmap
    assert "blob/main/AKSARA_POST_V07_MARKET_AND_ROADMAP_REVIEW.md" in roadmap
    assert "github.com/aksara/aksara/releases" not in changelog
    assert "github.com/nagarjuna-tella/Aksara/releases" in changelog


def test_v06_contract_names_the_actual_experimental_runtime_surfaces():
    contract = (ROOT / "docs/docs/roadmap/v0-6-stability-contract.md").read_text()

    assert "- `AgentRuntime`," not in contract
    assert "`run_prompt_pack`" in contract
    assert "`AgentRuntimeLimits`" in contract
    assert "`AgentRuntimeBudget`" in contract


def test_gap_analysis_version_defect_evidence_preserves_v071_history():
    evidence_path = ROOT / "audit-evidence/v071/gap-analysis-version-contract.json"
    evidence = json.loads(evidence_path.read_text())

    assert evidence["pass"] is True
    assert evidence["source_checkout_framework_imports"] is False
    assert evidence["package_version"] == "0.7.1"
    assert evidence["installed_requires_python"] == ">=3.11"
    observations = evidence["observations"]
    assert observations["python_3_9"]["too_old_issue_present"] is True
    assert observations["python_3_10"]["too_old_issue_present"] is False
    assert observations["python_3_11"]["too_old_issue_present"] is False

    page = (ROOT / "docs/docs/gapanalysis.md").read_text()
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert metadata["requires-python"] == ">=3.11,<3.15"
    assert "same Python 3.11–3.14 release range" in page
