"""Verify v0.7.1 source changes are confined to instructional text and descriptions."""

import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "b7ac75f4b1bd4b262824e828601168336b4ecf7f"
SCAFFOLD = "aksara/cli/scaffold.py"
CLI = "aksara/cli/main.py"
TEMPLATES = "aksara/cli/templates/__init__.py"


def normalized(source):
    tree = ast.parse(source)
    matches = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "get_readme_template"]
    assert len(matches) == 1
    returns = [n for n in ast.walk(matches[0]) if isinstance(n, ast.Return)]
    assert len(returns) == 1 and isinstance(returns[0].value, ast.JoinedStr)
    returns[0].value = ast.Constant(value="DOCUMENTATION_TEMPLATE")
    return ast.dump(tree, include_attributes=False)


class HelpStrings(ast.NodeTransformer):
    """Normalize string literals only; calls and expressions stay visible."""

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            return ast.Constant(value="HELP_TEXT")
        return node


def normalized_cli(source):
    tree = ast.parse(source)
    matches = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "startproject"]
    assert len(matches) == 1
    function = matches[0]
    assert isinstance(function.body[0], ast.Expr) and isinstance(function.body[0].value, ast.Constant)
    assert isinstance(function.body[0].value.value, str)
    function.body[0].value.value = "COMMAND_HELP"
    for node in ast.walk(function):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "ui"
                and node.func.attr in {"text", "bullet", "next_steps"}):
            node.args = [HelpStrings().visit(arg) for arg in node.args]
    return ast.dump(tree, include_attributes=False)


def normalized_templates(source):
    tree = ast.parse(source)
    matches = [n.value for n in tree.body if isinstance(n, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == "TEMPLATES" for target in n.targets)]
    assert len(matches) == 1 and isinstance(matches[0], ast.Dict)
    templates = matches[0]
    assert {ast.literal_eval(key) for key in templates.keys} == {"basic", "blog", "crm", "multitenant"}
    for info in templates.values:
        assert isinstance(info, ast.Dict)
        descriptions = [value for key, value in zip(info.keys, info.values, strict=True)
                        if ast.literal_eval(key) == "description"]
        assert len(descriptions) == 1 and isinstance(descriptions[0], ast.Constant)
        assert isinstance(descriptions[0].value, str)
        descriptions[0].value = "TEMPLATE_DESCRIPTION"
    return ast.dump(tree, include_attributes=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    names = subprocess.check_output(
        ["git", "diff", "--name-only", BASELINE, "--", "aksara", "pyproject.toml"],
        cwd=ROOT, text=True,
    ).splitlines()
    assert names == sorted([SCAFFOLD, CLI, TEMPLATES]), names
    untracked = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "aksara"], cwd=ROOT, text=True,
    ).splitlines()
    assert not untracked, untracked
    hashes = {}
    for path, normalize in ((SCAFFOLD, normalized), (CLI, normalized_cli), (TEMPLATES, normalized_templates)):
        before = subprocess.check_output(["git", "show", f"{BASELINE}:{path}"], cwd=ROOT, text=True)
        after = (ROOT / path).read_text()
        assert normalize(before) == normalize(after), path
        hashes[path] = hashlib.sha256(after.encode()).hexdigest()
    result = {
        "schema_version": 1, "pass": True, "baseline": BASELINE,
        "reviewed_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "changed_production_files": names,
        "classification": {
            SCAFFOLD: "Scaffold README return template only",
            CLI: "startproject docstring and string literals in its existing UI text/bullet/next_steps calls only",
            TEMPLATES: "Four template description string values only; names, sources and copy logic unchanged",
        },
        "runtime_logic_changed": False,
        "dependencies_changed": False,
        "scope": "aksara source tree and pyproject.toml; does not prove candidate startup, generated-file equivalence or full runtime regression",
        "source_sha256": hashes,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("PASS: production AST unchanged outside reviewed instructional text; dependencies unchanged")


if __name__ == "__main__":
    main()
