"""Verify v0.7.1 source changes are confined to the scaffold README template."""

import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "b7ac75f4b1bd4b262824e828601168336b4ecf7f"
SCAFFOLD = "aksara/cli/scaffold.py"


def normalized(source):
    tree = ast.parse(source)
    matches = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "get_readme_template"]
    assert len(matches) == 1
    returns = [n for n in ast.walk(matches[0]) if isinstance(n, ast.Return)]
    assert len(returns) == 1 and isinstance(returns[0].value, ast.JoinedStr)
    returns[0].value = ast.Constant(value="DOCUMENTATION_TEMPLATE")
    return ast.dump(tree, include_attributes=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    names = subprocess.check_output(
        ["git", "diff", "--name-only", BASELINE, "--", "aksara", "pyproject.toml"],
        cwd=ROOT, text=True,
    ).splitlines()
    assert names == [SCAFFOLD], names
    untracked = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "aksara"], cwd=ROOT, text=True,
    ).splitlines()
    assert not untracked, untracked
    before = subprocess.check_output(["git", "show", f"{BASELINE}:{SCAFFOLD}"], cwd=ROOT, text=True)
    after = (ROOT / SCAFFOLD).read_text()
    assert normalized(before) == normalized(after)
    result = {
        "schema_version": 1, "pass": True, "baseline": BASELINE,
        "reviewed_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "changed_production_files": names,
        "classification": "Scaffold README return template only; AST outside that return value is identical",
        "dependencies_changed": False,
        "scope": "aksara source tree and pyproject.toml; does not prove candidate startup, generated-file equivalence or full runtime regression",
        "source_sha256": hashlib.sha256(after.encode()).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("PASS: production AST unchanged outside scaffold README template; dependencies unchanged")


if __name__ == "__main__":
    main()
