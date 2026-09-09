#!/usr/bin/env python3
"""Fail when repository-wide Ruff or mypy debt exceeds the reviewed baseline."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = REPO_ROOT / "static-analysis-baseline.json"
MYPY_CODE = re.compile(r"\[([^]]+)]$")


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _installed_version(distribution: str) -> str:
    try:
        return version(distribution)
    except PackageNotFoundError as exc:
        raise RuntimeError(
            f"{distribution} is not installed; install the dev dependencies first"
        ) from exc


def collect_ruff() -> tuple[int, dict[str, int]]:
    result = _run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "aksara",
            "tests",
            "--output-format",
            "json",
        ]
    )
    if result.returncode not in {0, 1}:
        raise RuntimeError(f"Ruff failed to run:\n{result.stderr or result.stdout}")
    findings: list[dict[str, Any]] = json.loads(result.stdout or "[]")
    by_code = Counter(finding["code"] for finding in findings)
    return len(findings), dict(sorted(by_code.items()))


def collect_mypy() -> tuple[int, dict[str, int]]:
    result = _run(
        [
            sys.executable,
            "-m",
            "mypy",
            "aksara",
            "--no-error-summary",
            "--no-pretty",
            "--cache-dir=/tmp/aksara-static-baseline-mypy-cache",
        ]
    )
    if result.returncode not in {0, 1}:
        raise RuntimeError(f"mypy failed to run:\n{result.stderr or result.stdout}")

    errors = [line for line in result.stdout.splitlines() if ": error:" in line]
    by_code: Counter[str] = Counter()
    for error in errors:
        match = MYPY_CODE.search(error)
        by_code[match.group(1) if match else "unclassified"] += 1
    return len(errors), dict(sorted(by_code.items()))


def _compare_tool(
    tool: str,
    actual_total: int,
    actual_by_code: dict[str, int],
    expected: dict[str, Any],
) -> list[str]:
    problems = []
    expected_total = int(expected["total"])
    if actual_total > expected_total:
        problems.append(f"{tool} total increased: {actual_total} > {expected_total}")

    expected_by_code = expected["by_code"]
    for code, actual_count in actual_by_code.items():
        expected_count = int(expected_by_code.get(code, 0))
        if actual_count > expected_count:
            problems.append(
                f"{tool} {code} increased: {actual_count} > {expected_count}"
            )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    args = parser.parse_args()

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    expected_versions = baseline["tool_versions"]
    actual_versions = {
        "ruff": _installed_version("ruff"),
        "mypy": _installed_version("mypy"),
    }
    version_problems = [
        f"{tool} version is {actual_versions[tool]}, expected {expected}"
        for tool, expected in expected_versions.items()
        if actual_versions.get(tool) != expected
    ]
    if version_problems:
        print("Static baseline tool version mismatch:")
        for problem in version_problems:
            print(f"  - {problem}")
        return 2

    ruff_total, ruff_by_code = collect_ruff()
    mypy_total, mypy_by_code = collect_mypy()
    problems = [
        *_compare_tool("Ruff", ruff_total, ruff_by_code, baseline["ruff"]),
        *_compare_tool("mypy", mypy_total, mypy_by_code, baseline["mypy"]),
    ]

    print(
        f"Ruff: {ruff_total}/{baseline['ruff']['total']} allowed; "
        f"mypy: {mypy_total}/{baseline['mypy']['total']} allowed"
    )
    if problems:
        print("Static-analysis debt increased:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("Static-analysis debt is at or below the reviewed baseline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
