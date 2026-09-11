"""Check documented Doctor commands using an isolated installed package.

Help checks prove command/flag availability, not deployment readiness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs/docs/diagnostics.md"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    python = args.python.absolute()
    cli = python.parent / "aksara"
    commands = sorted(set(re.findall(r"aksara doctor [a-z-]+(?: --[a-z-]+(?: json)?)*", PAGE.read_text())))
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("AKSARA_") and key not in {"PYTHONPATH", "DATABASE_URL"}}
    checks = []
    with tempfile.TemporaryDirectory(prefix="aksara-operator-docs-") as directory:
        def run(command):
            return subprocess.run(command, cwd=directory, env=environment,
                                  capture_output=True, text=True, timeout=30, check=True)

        probe = run([str(python), "-I", "-c",
                     "import aksara,json; print(json.dumps({'version':aksara.__version__, 'path':aksara.__file__}))"])
        package = json.loads(probe.stdout)
        assert not Path(package["path"]).is_relative_to(ROOT), "Source checkout import"
        for command in commands:
            arguments = shlex.split(command)[1:]
            result = run([str(cli), *arguments, "--help"])
            # Click's eager help can skip normal invocation validation. Check
            # every documented option explicitly against the command's help.
            for option in arguments:
                if option.startswith("--"):
                    assert option in result.stdout, (command, option)
            assert "Usage:" in result.stdout
            checks.append({"command": command, "help_exit": result.returncode})
    evidence = {
        "schema_version": 1,
        "scope": "Installed command and flag availability; not live deployment validation",
        "package_version": package["version"],
        "source_checkout_imports": False,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "page": str(PAGE.relative_to(ROOT)),
        "page_sha256": hashlib.sha256(PAGE.read_bytes()).hexdigest(),
        "commands": checks,
        "pass": True,
    }
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(checks)} documented Doctor command forms; package {package['version']}")


if __name__ == "__main__":
    main()
