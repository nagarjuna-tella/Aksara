"""Prove that v0.7.2 finalization changes release identity, not runtime logic."""

from __future__ import annotations

import argparse
import json
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MERGED_IMPLEMENTATION_SHA = "e56cd56b7c247f38a10d6eb51ef688f7e79c9cfe"
VERSION_SURFACES = {
    "aksara/_version.py",
    "aksara/cli/scaffold.py",
    "examples/support_desk/main.py",
    "pyproject.toml",
}


def git(*args: str, text: bool = True) -> str | bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=text)


def normalized_version(data: bytes) -> bytes:
    for spelling in (b"0.7.2-rc1", b"0.7.2rc1", b"0.7.2"):
        data = data.replace(spelling, b"[RELEASE_VERSION]")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=MERGED_IMPLEMENTATION_SHA)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    changed = set(
        filter(
            None,
            git(
                "diff",
                "--name-only",
                args.base,
                "--",
                "aksara",
                "examples/support_desk/main.py",
                "pyproject.toml",
            ).splitlines(),
        )
    )
    if changed != VERSION_SURFACES:
        raise SystemExit(
            f"unexpected production/package finalization paths: {sorted(changed)}"
        )

    normalized_matches: dict[str, bool] = {}
    for name in sorted(VERSION_SURFACES):
        before = git("show", f"{args.base}:{name}", text=False)
        after = (ROOT / name).read_bytes()
        normalized_matches[name] = normalized_version(before) == normalized_version(after)
    if not all(normalized_matches.values()):
        raise SystemExit(f"non-version production diff: {normalized_matches}")

    before_project = tomllib.loads(
        git("show", f"{args.base}:pyproject.toml")
    )["project"]
    after_project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    before_project["version"] = "[RELEASE_VERSION]"
    after_project["version"] = "[RELEASE_VERSION]"
    dependencies_changed = before_project != after_project
    if dependencies_changed:
        raise SystemExit("project metadata other than version changed")

    migration_changes = list(
        filter(
            None,
            git(
                "diff",
                "--name-only",
                args.base,
                "--",
                "aksara/**/migrations/*.py",
            ).splitlines(),
        )
    )
    if migration_changes:
        raise SystemExit(f"finalization changed migrations: {migration_changes}")

    result = {
        "schema_version": 1,
        "pass": True,
        "merged_implementation_sha": args.base,
        "evaluated_head_sha": git("rev-parse", "HEAD").strip(),
        "changed_production_package_files": sorted(changed),
        "normalized_version_only": normalized_matches,
        "runtime_logic_changed": False,
        "dependencies_changed": False,
        "schema_migrations_changed": False,
        "existing_task_migration": "aksara/core/migrations/0003_task_claim_ownership.py",
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        "PASS: finalization changes four version surfaces; runtime logic, "
        "dependencies, and migrations are unchanged"
    )


if __name__ == "__main__":
    main()
