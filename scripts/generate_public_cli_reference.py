"""Generate the public command/parameter reference from an isolated installed wheel."""

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "audit-evidence/v071/cli-contract.json"
PAGE = ROOT / "docs/docs/reference/cli-reference.md"
PROBE = r'''
import json
import click
import aksara
from aksara.cli.main import cli

commands = []
def declared_default(param, ctx):
    value = param.get_default(ctx)
    if value is getattr(click.core, "UNSET", object()):
        return None
    return value

def visit(command, path):
    ctx = click.Context(command, info_name=path[-1])
    params = []
    for param in command.get_params(ctx):
        params.append({
            "name": param.name,
            "kind": "option" if isinstance(param, click.Option) else "argument",
            "spellings": param.opts + getattr(param, "secondary_opts", []),
            "type": param.type.name,
            "choices": list(param.type.choices) if isinstance(param.type, click.Choice) else None,
            "required": param.required,
            "nargs": param.nargs,
            "default": declared_default(param, ctx),
            "envvar": param.envvar,
        })
    commands.append({"path": path, "parameters": params,
                     "group": isinstance(command, click.Group),
                     "forwards_unknown_options": bool(command.context_settings.get("ignore_unknown_options"))})
    if isinstance(command, click.Group):
        for name in command.list_commands(ctx):
            visit(command.get_command(ctx, name), path + [name])
visit(cli, ["aksara"])
print(json.dumps({"schema_version": 1, "package_version": aksara.__version__,
                  "package_path": aksara.__file__, "commands": commands}))
'''


def render(contract):
    lines = ["# CLI Reference", "",
             f"Command and parameter declarations from installed Aksara **{contract['package_version']}**.", "",
             "This generated reference describes parser syntax, literal defaults, and environment",
             "bindings. It does not execute commands or prove their runtime effects. A `null`",
             "default means no literal parser default; the command may discover configuration",
             "or prompt later. Environment values and credentials are never captured.", "",
             "Start with [CLI workflows](../cli/commands.md) for migrations, serving, diagnostics,",
             "and worker guidance. See [configuration](settings-reference.md) for settings precedence.", "",
             "The `agent`, `ai`, `ai-hub`, `ai-provider`, and `studio` command families are",
             "**Experimental**. Their presence is not a stable backend guarantee.", "",
             "Durable workers use a separate Python module entry point; see",
             "[Durable Operations](../advanced/durable-operations.md). Ordinary `tasks` commands",
             "do not manage Durable Operations.", "",
             "Regenerate from an isolated wheel environment with",
             "`python scripts/generate_public_cli_reference.py --python /path/to/venv/bin/python`.", "",
             "<!-- Generated parser declarations; edit the generator, not the tables. -->", ""]
    for command in contract["commands"]:
        lines.extend(["## " + " ".join(command["path"]), ""])
        if command["group"]:
            lines.extend(["Command group; choose a subcommand below.", ""])
        if command["forwards_unknown_options"]:
            lines.extend(["Additional options are forwarded to the underlying tool (pytest for `aksara test`).",
                          "Its supported flags and installed plugins determine validity.", ""])
        lines.extend(["| Parameter | Kind / type | Required | Literal default | Environment |",
                      "|---|---|---|---|---|"])
        for param in command["parameters"]:
            name = ", ".join(param["spellings"])
            kind = param["kind"] + " / " + param["type"]
            if param["choices"]:
                kind += ": " + ", ".join(str(c) for c in param["choices"])
            if param["nargs"] == -1:
                kind += " (variadic)"
            default = json.dumps(param["default"])
            env = ", ".join(param["envvar"]) if isinstance(param["envvar"], list) else param["envvar"] or "—"
            lines.append(f"| `{name}` | {kind} | {'yes' if param['required'] else 'no'} | `{default}` | {env} |")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    env = {k: v for k, v in os.environ.items()
           if k not in {"PYTHONPATH", "DATABASE_URL"} and not k.startswith("AKSARA_")}
    with tempfile.TemporaryDirectory(prefix="aksara-cli-contract-") as directory:
        result = subprocess.run([str(args.python.absolute()), "-I", "-c", PROBE],
                                cwd=directory, env=env, capture_output=True, text=True,
                                timeout=60, check=True)
    contract = json.loads(result.stdout)
    assert not Path(contract.pop("package_path")).is_relative_to(ROOT)
    contract["source_checkout_framework_imports"] = False
    content = json.dumps(contract, indent=2) + "\n"
    page = render(contract)
    if args.check:
        assert EVIDENCE.read_text() == content, "Installed CLI declarations changed"
        assert PAGE.read_text() == page, "Generated reference is stale"
    else:
        EVIDENCE.write_text(content)
        PAGE.write_text(page)
    print(f"PASS: {len(contract['commands'])} command/group declarations")


if __name__ == "__main__":
    main()
