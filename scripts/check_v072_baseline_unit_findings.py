"""Reproduce isolated v0.7.1 audit findings against an installed wheel."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROBE = r'''
import asyncio
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import aksara


async def main():
    results = {}

    from aksara.conf import Settings
    with patch.dict(
        os.environ,
        {"AKSARA_MCP_ALLOWED_ORIGINS": "https://example.com"},
        clear=False,
    ):
        configured = Settings().mcp_allowed_origins
    results["CFG-001"] = {
        "input": "https://example.com",
        "observed": configured,
        "url_round_trip": configured == ["https://example.com"],
    }

    from aksara.storage import FileSystemStorage
    with tempfile.TemporaryDirectory(prefix="aksara-v072-storage-") as directory:
        parent = Path(directory)
        root = parent / "media"
        outside = parent / "media-private" / "probe.txt"
        storage = FileSystemStorage(location=str(root))
        returned_name = await storage.save("../media-private/probe.txt", b"baseline")
        results["STORAGE-001"] = {
            "operation": "save",
            "input": "../media-private/probe.txt",
            "returned_name": returned_name,
            "outside_root_created": outside.read_bytes() == b"baseline",
            "root": "disposable/media",
            "resolved_target": "disposable/media-private/probe.txt",
        }

    import aksara.studio
    from aksara.ai import workflows
    from aksara.diagnostics import DiagnosticAction, DiagnosticIssue, DiagnosticReport

    async def diagnostic_report():
        return DiagnosticReport(
            issues=[
                DiagnosticIssue(
                    kind="database_connectivity",
                    severity="error",
                    title="No database URL configured",
                    message="DATABASE_URL is not set",
                    actions=[
                        DiagnosticAction(
                            kind="set_env",
                            target="DATABASE_URL",
                            title="Set DATABASE_URL",
                            example='export DATABASE_URL="postgresql://example.invalid/app"',
                        )
                    ],
                )
            ]
        )

    workflows._get_run_all_checks = lambda: diagnostic_report
    commands = (
        await asyncio.to_thread(
            workflows._build_diagnostic_steps, "configure database"
        )
    )[0].commands
    results["AIFLOW002"] = {
        "commands": commands,
        "duplicated_export_prefix": any(
            command.startswith("export DATABASE_URL=export DATABASE_URL=")
            for command in commands
        ),
    }

    from aksara.inspectors.queries import explain_query
    synthetic = explain_query("SELECT * FROM definitely_missing", analyze=True)
    results["INSPECTOR001"] = {
        "plan_type": synthetic.plan_type,
        "plan": synthetic.plan,
        "warnings": synthetic.warnings,
        "synthetic_provenance_present": any(
            "synthetic" in warning.lower() for warning in synthetic.warnings
        ),
    }

    from aksara.contrib.admin.widgets.array import ArrayAdminWidget
    value = ["one"]
    before = list(value)
    ArrayAdminWidget(min_rows=3).render(
        "tags", value, SimpleNamespace(nullable=True)
    )
    results["ADMINWIDGET001"] = {
        "before": before,
        "after": value,
        "input_preserved": value == before,
    }

    print("V072_BASELINE_UNIT=" + json.dumps({
        "package_version": aksara.__version__,
        "package_path": aksara.__file__,
        "findings": results,
    }))


asyncio.run(main())
'''

EXAMPLE_PROBE = r'''
import asyncio
import importlib.util
import json
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse

spec = importlib.util.spec_from_file_location("released_multitenant_middleware", "middleware.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


async def main():
    calls = {"resolver": 0, "downstream": 0}

    async def resolver(request):
        calls["resolver"] += 1
        return None

    async def app(scope, receive, send):
        return None

    middleware = module.TenantMiddleware(app)
    middleware._resolve_tenant = resolver
    request = Request({"type": "http", "method": "GET", "path": "/api/projects/", "headers": []})

    async def call_next(request):
        calls["downstream"] += 1
        return JSONResponse({"ok": True})

    response = await middleware.dispatch(request, call_next)
    print("V072_BASELINE_EXAMPLE=" + json.dumps({
        "path": "/api/projects/",
        "status": response.status_code,
        "resolver_calls": calls["resolver"],
        "downstream_calls": calls["downstream"],
        "root_exemption_bypasses_tenant_resolution": (
            response.status_code == 200
            and calls["resolver"] == 0
            and calls["downstream"] == 1
        ),
    }))


asyncio.run(main())
'''


def clean_environment() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "DATABASE_URL"}
        and not key.startswith("AKSARA_")
    }


def parse_prefixed_json(output: str, prefix: str) -> dict[str, object]:
    return json.loads(
        next(
            line.removeprefix(prefix)
            for line in output.splitlines()
            if line.startswith(prefix)
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    environment = clean_environment()
    with tempfile.TemporaryDirectory(prefix="aksara-v072-baseline-") as directory:
        workdir = Path(directory)
        unit = subprocess.run(
            [str(args.python.absolute()), "-I", "-c", PROBE],
            cwd=workdir,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        if unit.returncode:
            raise RuntimeError(unit.stderr or unit.stdout)
        evidence = parse_prefixed_json(unit.stdout, "V072_BASELINE_UNIT=")
        package_path = Path(str(evidence.pop("package_path"))).resolve()
        assert not package_path.is_relative_to(ROOT)

        direct_import = subprocess.run(
            [
                str(args.python.absolute()),
                "-I",
                "-c",
                "from aksara.ai.workflows import build_agent_workflow",
            ],
            cwd=workdir,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        evidence["findings"]["AIFLOW001"] = {
            "direct_import_exit": direct_import.returncode,
            "error_tail": (direct_import.stderr or direct_import.stdout).splitlines()[-1],
        }

        example_source = (ROOT / "examples/multitenant/middleware.py").read_bytes()
        (workdir / "middleware.py").write_bytes(example_source)
        example = subprocess.run(
            [str(args.python.absolute()), "-I", "-c", EXAMPLE_PROBE],
            cwd=workdir,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        if example.returncode:
            raise RuntimeError(example.stderr or example.stdout)
        evidence["findings"]["EX-001"] = parse_prefixed_json(
            example.stdout, "V072_BASELINE_EXAMPLE="
        )

    evidence.update(
        {
            "schema_version": 1,
            "source_checkout_framework_imports": False,
            "released_example_sha256": hashlib.sha256(example_source).hexdigest(),
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "scope": (
                "Independent provider-free reproductions against the public v0.7.1 "
                "wheel, plus EX-001 executed from the exact released repository example. "
                "All filesystem writes use disposable temporary directories."
            ),
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(evidence['findings'])} isolated baseline findings reproduced")


if __name__ == "__main__":
    main()
