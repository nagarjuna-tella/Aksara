"""Execute documented provider-free AI CLI examples in an isolated wheel."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["docs/docs/cli/ai-commands.md", "docs/docs/ai-mode/console.md"]
PROBE = r'''
import json, shlex, socket, sys
from unittest.mock import patch
import aksara
from click.testing import CliRunner
from aksara.cli.main import cli
results = []
with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')):
    for command in json.load(sys.stdin):
        result = CliRunner().invoke(cli, shlex.split(command)[1:])
        assert result.exit_code == 0, (command, result.output)
        if '"hello"' in command:
            payload = json.loads(result.output)
            assert payload['ok'] is True
            assert payload['intent'] == 'greet'
            assert payload['execution']['mode'] == 'conversational'
        elif 'plan template' in command:
            payload = json.loads(result.output)
            assert payload['intent']['mode'] == 'read'
            assert payload['plan']['steps'][0]['type'] == 'analyze_context'
        else:
            assert '--help' in command and 'Usage:' in result.output
        results.append({'command': command, 'exit_code': result.exit_code})
print(json.dumps({'package_version': aksara.__version__, 'package_path': aksara.__file__,
                  'results': results}))
'''


def commands():
    selected = set()
    for name in PAGES:
        for block in re.findall(r"```bash\n(.*?)```", (ROOT / name).read_text(), re.DOTALL):
            for line in block.splitlines():
                if line.startswith("aksara ") and (
                    line.endswith("--help") or '"hello"' in line or "plan template" in line
                ):
                    selected.add(line)
    return sorted(selected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    env = {k: v for k, v in os.environ.items()
           if k not in {"PYTHONPATH", "DATABASE_URL"} and not k.startswith("AKSARA_")}
    with tempfile.TemporaryDirectory(prefix="aksara-ai-cli-") as directory:
        run = subprocess.run([str(args.python.absolute()), "-I", "-c", PROBE],
                             input=json.dumps(commands()), text=True, capture_output=True,
                             env=env, cwd=directory, timeout=60, check=True)
    evidence = json.loads(run.stdout)
    assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
    evidence.update({"schema_version": 1, "pass": True,
                     "source_checkout_framework_imports": False,
                     "scope": "Help, local greeting, and plan template only; socket connections forbidden",
                     "page_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in PAGES},
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(evidence['results'])} provider-free CLI checks")


if __name__ == "__main__":
    main()
