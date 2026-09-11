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
