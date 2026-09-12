"""Run a source-suite compatibility checkpoint with required local PostgreSQL."""

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = {"minimum": ("0.136.1", "1.0.1"), "latest-supported": ("0.141.1", "1.6.0")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--web", choices=VERSIONS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    python = str(args.python.absolute())
    metadata = json.loads(subprocess.check_output(
        [python, "-c", "import json,platform,fastapi,starlette,asyncpg; print(json.dumps(dict(python=platform.python_version(),fastapi=fastapi.__version__,starlette=starlette.__version__,asyncpg=asyncpg.__version__)))"],
        cwd=ROOT, text=True,
    ))
    assert (metadata["fastapi"], metadata["starlette"]) == VERSIONS[args.web]
    dsn = os.environ["DATABASE_URL"]
    env = {k: v for k, v in os.environ.items() if not k.startswith("AKSARA_")}
    env.update(DATABASE_URL=dsn, AKSARA_REQUIRE_DATABASE_TESTS="1", AKSARA_REQUIRE_SECURITY_MATRIX="false")
    command = [python, "-m", "pytest", "--tb=short", "-q"]
    run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    log_text = (run.stdout + run.stderr).replace(dsn, "[REDACTED DATABASE_URL]")
    # Error paths can contain other connection URLs, so redact any URI credentials.
    import re

    log_text = re.sub(r"(postgres(?:ql)?://)[^\s/@]+(?::[^\s/@]*)?@", r"\1[REDACTED]@", log_text)
    from urllib.parse import unquote, urlsplit

    password = urlsplit(dsn).password
    if password:
        log_text = log_text.replace(unquote(password), "[REDACTED PASSWORD]")
    log_path = args.output.with_suffix(".log")
    log_path.write_text(log_text)
    summaries = [line for line in log_text.splitlines() if re.search(r"\d+ (?:passed|failed|error)", line)]
    evidence = {
        "schema_version": 1, "pass": run.returncode == 0, "exit_code": run.returncode,
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "command": command, "web_boundary": args.web, "versions": metadata,
        "database_tests_required": True, "security_matrix_required": False,
        "summary": summaries[-1] if summaries else "No pytest summary",
        "log": str(log_path), "log_sha256": hashlib.sha256(log_path.read_bytes()).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": "Local source suite checkpoint; not hosted PostgreSQL 16 or installed-wheel candidate evidence",
    }
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence))
    raise SystemExit(run.returncode)


if __name__ == "__main__":
    main()
