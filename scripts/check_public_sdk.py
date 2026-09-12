"""Generate and type-check the documented SDK with installed Python/TypeScript.

Returns the compiler exit code after recording evidence; a known failure stays
visible rather than being converted into a passing SDK gate.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FENCES = re.compile(r'^```python title="([^\"]+)"\n(.*?)^```', re.MULTILINE | re.DOTALL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--tsc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    tutorial = ROOT / "docs/docs/getting-started/first-project.md"
    guide = ROOT / "docs/docs/how-to/typescript-client.md"
    files = dict(FENCES.findall(tutorial.read_text()))
    script = dict(FENCES.findall(guide.read_text()))["generate_client.py"]
    env = {k: v for k, v in os.environ.items()
           if k not in {"PYTHONPATH", "DATABASE_URL"} and not k.startswith("AKSARA_")}
    with tempfile.TemporaryDirectory(prefix="aksara-sdk-check-") as raw:
        root = Path(raw)
        (root / "app").mkdir()
        (root / "app/__init__.py").write_text("")
        inputs = {}
        for name in ["app/models.py", "app/views.py"]:
            (root / name).write_text(files[name])
            inputs[name] = hashlib.sha256(files[name].encode()).hexdigest()
        (root / "generate_client.py").write_text(script)

        def run(command):
            return subprocess.run([str(arg) for arg in command], cwd=root, env=env,
                                  capture_output=True, text=True, timeout=45, check=False)

        package = run([args.python.absolute(), "-I", "-c",
                       "import aksara,json; print(json.dumps({'version':aksara.__version__,'path':aksara.__file__}))"])
        package.check_returncode()
        package = json.loads(package.stdout)
        assert not Path(package["path"]).is_relative_to(ROOT)
        compiler = run([args.tsc.absolute(), "--version"])
        compiler.check_returncode()
        generated = run([args.python.absolute(), "generate_client.py"])
        generated.check_returncode()
        compiled = run([args.tsc.absolute(), "--strict", "--noEmit", "--lib", "ES2022,DOM", "api.ts"])
        evidence = {
            "schema_version": 1,
            "package_version": package["version"],
            "source_checkout_framework_imports": False,
            "typescript_version": compiler.stdout.strip(),
            "input_sha256": inputs,
            "documentation_sha256": hashlib.sha256(guide.read_bytes()).hexdigest(),
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "generation_exit": generated.returncode,
            "generated_sha256": hashlib.sha256((root / "api.ts").read_bytes()).hexdigest(),
            "compile_command": "tsc --strict --noEmit --lib ES2022,DOM api.ts",
            "compile_exit": compiled.returncode,
            "compile_output": compiled.stdout + compiled.stderr,
            "live_http_executed": False,
            "runtime_fix_performed": False,
        }
        args.output.write_text(json.dumps(evidence, indent=2) + "\n")
        print(compiled.stdout + compiled.stderr, end="")
        return compiled.returncode


if __name__ == "__main__":
    raise SystemExit(main())
