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


def test_v071_cli_syntax_evidence_remains_historical():
    evidence = json.loads((ROOT / "audit-evidence/v071/cli-docs-syntax.json").read_text())
    assert evidence["pass"] and not evidence["errors"]
    assert evidence["checked_commands"] == 295
    assert len(evidence["skipped"]) == 7
    assert all(len(digest) == 64 for digest in evidence["page_sha256"].values())
    assert len(evidence["runner_sha256"]) == 64


def test_current_documented_cli_forms_parse():
    import os
    import subprocess
    import sys

    module = runpy.run_path(str(ROOT / "scripts/check_public_cli_docs.py"))
    commands, _skipped, _hashes = module["collect"]()
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "DATABASE_URL"} and not key.startswith("AKSARA_")
    }
    result = subprocess.run(
        [sys.executable, "-c", module["PROBE"]],
        cwd=ROOT,
        env=env,
        input=json.dumps(commands),
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(result.stdout)["errors"] == []


def test_cli_syntax_probe_rejects_unknown_commands_and_options():
    import subprocess
    import sys

    module = runpy.run_path(str(ROOT / "scripts/check_public_cli_docs.py"))
    examples = [
        ["aksara", "migrate", "--check"],
        ["aksara", "ai", "chat", "hello"],
        ["aksara", "ai", "missing-command", "--help"],
        ["aksara", "ai-hub", "configure"],
        ["aksara", "ai", "flows", "chat", "hello", "--format", "invalid"],
        ["aksara", "--plain", "ai", "flows", "chat", "--help"],
        ["aksara", "test", "-x", "--tb=short"],
    ]
    result = subprocess.run([sys.executable, "-c", module["PROBE"]], cwd=ROOT,
                            input=json.dumps([{"args": args} for args in examples]),
                            text=True, capture_output=True, check=True)
    assert [entry["args"] for entry in json.loads(result.stdout)["errors"]] == examples[:5]


def test_v071_installed_import_evidence_remains_historical():
    evidence = json.loads((ROOT / "audit-evidence/v071/installed-doc-imports.json").read_text())
    assert evidence["pass"] and evidence["source_checkout_framework_imports"] is False
    assert evidence["python_blocks"] == 348
    assert all(len(digest) == 64 for digest in evidence["page_sha256"].values())
    assert evidence["viewset_route_and_default_checks"] == "passed"
    assert len(evidence["ai_debug_contract_sha256"]) == 64
    assert evidence["ai_debug_local_advisor_checks"] == "passed"
    assert len(evidence["exception_contract_sha256"]) == 64
    assert evidence["exception_types_and_http_checks"] == "passed"
    assert len(evidence["localization_contract_sha256"]) == 64
    assert evidence["localization_http_and_conversion_checks"] == "passed"
    assert len(evidence["viewset_contract_sha256"]) == 64
    assert len(evidence["contract_sha256"]) == 64
    assert len(evidence["runner_sha256"]) == 64
