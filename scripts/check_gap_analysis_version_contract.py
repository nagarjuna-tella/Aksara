"""Reproduce the installed gap-analysis Python-version contract mismatch."""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = r'''
import asyncio
import json
import os
import sys
from importlib.metadata import metadata
from unittest.mock import MagicMock, patch

import aksara
from aksara.gapanalysis import check_environment


async def check(version):
    settings = MagicMock()
    settings.database_url = "postgresql://example.invalid/aksara"
    settings.secret_key = "evidence-only-secret"
    settings.debug = False
    env = {
        "DATABASE_URL": settings.database_url,
        "SECRET_KEY": settings.secret_key,
        "AKSARA_ENV": "development",
    }
    with (
        patch.object(sys, "version_info", version),
        patch("aksara.gapanalysis._lazy_settings", return_value=settings),
        patch.dict(os.environ, env, clear=False),
    ):
        issues = await check_environment()
    matches = [
        issue.model_dump(mode="json")
        for issue in issues
        if issue.code == "ENV_PYTHON_VERSION_TOO_OLD"
    ]
    return {
        "version": ".".join(str(part) for part in version),
        "too_old_issue_present": bool(matches),
        "issues": matches,
    }


async def main():
    result = {
        "package_version": aksara.__version__,
        "package_path": aksara.__file__,
        "installed_requires_python": metadata("aksara-framework")["Requires-Python"],
        "observations": {
            "python_3_9": await check((3, 9, 0)),
            "python_3_10": await check((3, 10, 0)),
            "python_3_11": await check((3, 11, 0)),
        },
    }
    print("GAP_VERSION_EVIDENCE=" + json.dumps(result))


asyncio.run(main())
'''


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    env = {
        key: value
        for key, value in os.environ.items()
        if key != "PYTHONPATH" and not key.startswith("AKSARA_")
    }
    with tempfile.TemporaryDirectory(prefix="aksara-gap-version-") as directory:
        run = subprocess.run(
            [str(args.python.absolute()), "-I", "-c", PROBE],
            cwd=directory,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    if run.returncode:
        raise RuntimeError(run.stderr or run.stdout)

    prefix = "GAP_VERSION_EVIDENCE="
    evidence = json.loads(
        next(
            line.removeprefix(prefix)
            for line in run.stdout.splitlines()
            if line.startswith(prefix)
        )
    )
    package_path = Path(evidence.pop("package_path"))
    observations = evidence["observations"]
    expected_version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert evidence["package_version"] == expected_version
    assert evidence["installed_requires_python"] == ">=3.11"
    assert observations["python_3_9"]["too_old_issue_present"] is True
    assert observations["python_3_10"]["too_old_issue_present"] is False
    assert observations["python_3_11"]["too_old_issue_present"] is False
    assert not package_path.is_relative_to(ROOT)

    evidence.update(
        {
            "schema_version": 1,
            "pass": True,
            "source_checkout_framework_imports": False,
            "known_runtime_defect": (
                "GAP001: the environment checker accepts Python 3.10 while "
                "the installed package metadata requires Python 3.11 or newer"
            ),
            "scope": (
                "Negative provider-free installed-wheel probe. It patches the "
                "reported interpreter tuple in the environment checker and proves "
                "the 3.10 threshold mismatch; it does not run Aksara on Python 3.10, "
                "test deployment health, or change production behavior."
            ),
            "source_sha256": {
                "aksara/gapanalysis.py": digest(ROOT / "aksara/gapanalysis.py"),
                "pyproject.toml": digest(ROOT / "pyproject.toml"),
            },
            "page_sha256": {
                "docs/docs/gapanalysis.md": digest(ROOT / "docs/docs/gapanalysis.md"),
                "docs/docs/reference/runtime-compatibility.md": digest(
                    ROOT / "docs/docs/reference/runtime-compatibility.md"
                ),
            },
            "runner_sha256": digest(Path(__file__)),
        }
    )
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print("PASS: installed gap-analysis Python-version mismatch reproduced")


if __name__ == "__main__":
    main()
