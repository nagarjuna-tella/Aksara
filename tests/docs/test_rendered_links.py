"""The rendered-site gate must catch fragments, assets, and absolute local links."""

import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = runpy.run_path(str(ROOT / "scripts/check_rendered_docs_links.py"))


def test_missing_assets_and_fragments_are_reported(tmp_path):
    (tmp_path / "index.html").write_text(
        '<link href="missing.css"><a href="/Aksara/other/#missing">bad</a>'
        '<a href="https://example.com/outside">external</a>'
        '<a href="other/#present">valid</a>'
    )
    (tmp_path / "other").mkdir()
    (tmp_path / "other/index.html").write_text('<h1 id="present">OK</h1>')
    report = MODULE["check"](tmp_path, "https://docs.example/Aksara/")
    assert report["pass"] is False
    assert {item["error"] for item in report["errors"]} == {"missing local target", "missing fragment"}
    assert report["external_links_not_fetched"] == 1


def test_v071_link_evidence_remains_historical():
    evidence = json.loads((ROOT / "audit-evidence/v071/rendered-links.json").read_text())
    assert evidence["pass"] and not evidence["errors"]
    assert evidence["source_sha256"]
    assert all(len(digest) == 64 for digest in evidence["source_sha256"].values())
    assert len(evidence["runner_sha256"]) == 64
