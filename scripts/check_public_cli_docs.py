"""Check literal documented Aksara command syntax against an isolated wheel.

Parses with Click without invoking callbacks, commands, providers, or databases.
Checks required arguments and declared choices, but not file existence, application imports,
runtime effects, or forwarded pytest flags.
"""

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
PROBE = r'''
import json
import click
import aksara
from aksara.cli.main import cli

results = []
for item in json.load(__import__('sys').stdin):
    args = item['args'][1:]
    command = cli
    path = ['aksara']
    error = None
    try:
        while True:
            ctx = click.Context(command, info_name=path[-1], **command.context_settings)
            values, rest, _ = command.make_parser(ctx).parse_args(args)
            if isinstance(command, click.Group):
                if not rest:
                    break
                name = rest.pop(0)
                child = command.get_command(ctx, name)
                if child is None:
                    raise ValueError('Unknown command: ' + ' '.join(path + [name]))
                command = child
                path.append(name)
                args = rest
            else:
                help_requested = any(
                    isinstance(param, click.Option) and '--help' in param.opts
                    and values.get(param.name)
                    for param in command.get_params(ctx)
                )
                if not help_requested:
                    for param in command.params:
                        value = values.get(param.name)
                        missing = value is None or value is getattr(click.core, 'UNSET', object()) or value == () or value == []
                        if param.required and missing:
                            raise ValueError('Missing required parameter: ' + param.name)
                        if not missing and isinstance(param.type, click.Choice):
                            for choice in value if param.multiple else [value]:
                                param.type.convert(choice, param, ctx)
                if rest and not ctx.allow_extra_args:
                    raise ValueError('Unexpected arguments: ' + str(rest))
                break
    except (click.ClickException, ValueError) as exc:
        error = str(exc)
    if error:
        results.append({**item, 'error': error})
print(json.dumps({'package_version': aksara.__version__, 'package_path': aksara.__file__,
                  'errors': results}))
'''


def collect():
    commands, skipped, hashes = [], [], {}
    pages = [ROOT / "README.md", *(ROOT / "docs/docs").rglob("*.md"),
             *(ROOT / "examples").glob("*/README.md")]
    for page in sorted(pages):
        name = str(page.relative_to(ROOT))
        if "changelog" in name or "/notes/" in name:
            continue
        text = page.read_text()
        hashes[name] = hashlib.sha256(text.encode()).hexdigest()
        for match in re.finditer(r"```(?:bash|sh|shell|console)(?: [^\n]*)?\n(.*?)```", text, re.DOTALL):
            for line in match.group(1).replace("\\\n", " ").splitlines():
                line = line.strip().removeprefix("$ ")
                if not line.startswith("aksara "):
                    continue
                item = {"file": name, "command": line}
                try:
                    args = shlex.split(line, comments=True)
                except ValueError:
                    skipped.append({**item, "reason": "not a complete shell command"})
                    continue
                if any(token in {"|", "&&", "||", ";", ">", ">>", "2>"}
                       or re.match(r"\d*[<>]", token) for token in args):
                    skipped.append({**item, "reason": "shell pipeline, redirection, or placeholder"})
                    continue
                if any(token.startswith("[") and token.endswith("]") for token in args):
                    skipped.append({**item, "reason": "usage notation"})
                    continue
                commands.append({**item, "args": args})
    return commands, skipped, hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    commands, skipped, hashes = collect()
    env = {k: v for k, v in os.environ.items()
           if k not in {"PYTHONPATH", "DATABASE_URL"} and not k.startswith("AKSARA_")}
    with tempfile.TemporaryDirectory(prefix="aksara-cli-docs-") as directory:
        result = subprocess.run([str(args.python.absolute()), "-I", "-c", PROBE],
                                input=json.dumps(commands), capture_output=True, text=True,
                                env=env, cwd=directory, timeout=60, check=True)
    evidence = json.loads(result.stdout)
    assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
    evidence.update({"schema_version": 1, "source_checkout_framework_imports": False,
                     "scope": __doc__.strip(), "checked_commands": len(commands),
                     "pass": not evidence["errors"], "skipped": skipped,
                     "page_sha256": hashes,
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"{len(commands)} commands parsed; {len(evidence['errors'])} errors; {len(skipped)} excluded")
    for error in evidence["errors"]:
        print(error)
    raise SystemExit(bool(evidence["errors"]))


if __name__ == "__main__":
    main()
