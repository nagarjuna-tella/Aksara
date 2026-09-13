"""Verify clean-process import and packaged-example boundaries from a candidate wheel."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


def run_clean(python: Path, code: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="aksara-v072-boundary-") as directory:
        run = subprocess.run(
            [str(python), "-I", "-c", code],
            cwd=directory,
            capture_output=True,
            text=True,
            check=False,
        )
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    commands = {
        "workflow_first": """
import json
import aksara.ai.workflows as workflows
from aksara.ai.workflows import build_agent_workflow
print(json.dumps({"module": workflows.__name__, "callable": callable(build_agent_workflow)}))
""",
        "studio_first": """
import json
import aksara.studio
import aksara.ai.workflows as workflows
print(json.dumps({"studio": aksara.studio.__name__, "workflow": workflows.__name__}))
""",
        "workflow_then_studio": """
import json
import aksara.ai.workflows as workflows
import aksara.studio
import aksara.ai.workflows as workflows_again
print(json.dumps({"same_module": workflows is workflows_again, "studio": aksara.studio.__name__}))
""",
        "studio_then_workflow": """
import json
import aksara.studio
from aksara.ai.workflows import build_agent_workflow
import aksara.studio as studio_again
print(json.dumps({"callable": callable(build_agent_workflow), "same_module": aksara.studio is studio_again}))
""",
    }
    imports = {name: run_clean(args.python, code) for name, code in commands.items()}

    example = run_clean(
        args.python,
        """
import importlib
import json
import sys
from aksara.cli.templates import get_examples_path

examples = get_examples_path().resolve()
sys.path.insert(0, str(examples.parent))
module = importlib.import_module(f"{examples.name}.multitenant.middleware")
middleware = module.TenantMiddleware.__new__(module.TenantMiddleware)
cases = {
    "/": middleware._is_exempt_path("/"),
    "/health": middleware._is_exempt_path("/health"),
    "/health/child": middleware._is_exempt_path("/health/child"),
    "/docs/child": middleware._is_exempt_path("/docs/child"),
    "/api/projects/": middleware._is_exempt_path("/api/projects/"),
}
print(json.dumps({"examples_path": str(examples), "packaged": "site-packages" in str(examples), "cases": cases}))
""",
    )
    assert example["packaged"] is True, example
    assert example["cases"] == {
        "/": True,
        "/health": True,
        "/health/child": False,
        "/docs/child": True,
        "/api/projects/": False,
    }, example

    version = run_clean(
        args.python,
        "import json, aksara; print(json.dumps({'version': aksara.__version__, 'origin': aksara.__file__}))",
    )
    assert version["version"] == "0.7.2rc1", version
    assert "site-packages" in str(version["origin"]), version

    result = {
        "schema_version": 1,
        "pass": True,
        "package": version,
        "workflow_imports": imports,
        "packaged_multitenant_example": example,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": "Fresh installed-wheel processes for workflow import order and the packaged EX-001 path matcher.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("PASS: clean installed workflow imports and packaged multitenant path matching")


if __name__ == "__main__":
    main()
