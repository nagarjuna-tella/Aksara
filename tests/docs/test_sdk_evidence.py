"""Preserve the historical v0.7.1 SDK probe and verify the current contract."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_sdk_probe_preserves_v071_compiler_failure():
    evidence = json.loads((ROOT / "audit-evidence/v071/typescript-sdk-probe.json").read_text())
    assert evidence["source_checkout_framework_imports"] is False
    assert evidence["package_version"] == "0.7.0"
    assert evidence["compile_exit"] == 2
    assert "TS2322" in evidence["compile_output"]
    assert all(len(digest) == 64 for digest in evidence["input_sha256"].values())


def test_current_sdk_guide_requires_strict_compile_and_runtime_exercise():
    guide = (ROOT / "docs/docs/how-to/typescript-client.md").read_text()
    runner = (ROOT / "scripts/run_v072_typescript_sdk_gate.py").read_text()

    assert "tsc --strict --noEmit --lib ES2022,DOM api.ts" in guide
    assert "The canonical Ticket Desk output passes this strict check" in guide
    assert "createTicket" in runner
    assert "getTicket" in runner
    assert "updateTicket" in runner
    assert "listTickets" in runner
    assert "resolved=true" in runner
