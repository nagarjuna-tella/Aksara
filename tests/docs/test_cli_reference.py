"""Keep the installed CLI parser reference reproducible and scoped honestly."""

import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_generated_cli_reference_matches_recorded_contract():
    module = runpy.run_path(str(ROOT / "scripts/generate_public_cli_reference.py"))
    contract = json.loads(module["EVIDENCE"].read_text())
    assert module["PAGE"].read_text() == module["render"](contract)
    assert contract["source_checkout_framework_imports"] is False
    commands = {tuple(command["path"]): command for command in contract["commands"]}
    assert ("aksara", "migrate") in commands
    assert ("aksara", "doctor", "production-check") in commands
    assert ("aksara", "routes") not in commands
    assert commands[("aksara", "test")]["forwards_unknown_options"] is True


def test_provider_free_cli_evidence_matches_examples():
    import hashlib

    module = runpy.run_path(str(ROOT / "scripts/check_public_ai_cli.py"))
    evidence = json.loads((ROOT / "audit-evidence/v071/ai-cli-execution.json").read_text())
    assert evidence["pass"] is True
    assert [item["command"] for item in evidence["results"]] == module["commands"]()
    assert all(item["exit_code"] == 0 for item in evidence["results"])
    for path, digest in evidence["page_sha256"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    assert hashlib.sha256((ROOT / "scripts/check_public_ai_cli.py").read_bytes()).hexdigest() == evidence["runner_sha256"]
