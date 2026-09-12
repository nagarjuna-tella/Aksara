"""Reproduce the ordinary-task stale-recovery ownership limitation."""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
PROBE = r'''
import asyncio
import json
import os

import aksara
from aksara.db import Database
from aksara.tasks import TaskWorker, clear_task_registry, get_task_record, task


async def main():
    database = Database(os.environ["DATABASE_URL"], min_size=1, max_size=4)
    await database.connect()
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    calls = []
    try:
        @task(name="evidence.long_running_task", max_attempts=3)
        async def long_running_task():
            call_number = len(calls) + 1
            calls.append(call_number)
            if call_number == 1:
                first_started.set()
                await release_first.wait()
                return {"completion": "stale_first"}
            return {"completion": "reclaimed_second"}

        queued = await long_running_task.enqueue(db=database)
        first_worker = TaskWorker(database, stale_lock_timeout_seconds=1.0)
        second_worker = TaskWorker(database, stale_lock_timeout_seconds=1.0)

        first_poll = asyncio.create_task(first_worker.poll_once())
        await asyncio.wait_for(first_started.wait(), timeout=10)
        await database.execute(
            """
            UPDATE aksara_tasks
            SET locked_at = clock_timestamp() - INTERVAL '2 seconds'
            WHERE id = $1
            """,
            queued.id,
        )
        recovered = await second_worker.recover_stale_locks()
        assert recovered == 1
        reclaimed = await second_worker.poll_once()
        assert reclaimed is not None and reclaimed.status == "completed"
        before_release = await get_task_record(queued.id, db=database)
        assert before_release is not None
        assert before_release.result == {"completion": "reclaimed_second"}

        release_first.set()
        await asyncio.wait_for(first_poll, timeout=10)
        final = await get_task_record(queued.id, db=database)
        assert final is not None
        assert final.result == {"completion": "stale_first"}
        assert calls == [1, 2]

        print("TASK_STALE_RECOVERY_EVIDENCE=" + json.dumps({
            "package_version": aksara.__version__,
            "package_path": aksara.__file__,
            "duplicate_calls_observed": len(calls),
            "recovered_while_first_callable_active": True,
            "reclaimed_result_before_stale_completion": "reclaimed_second",
            "final_result_after_stale_completion": "stale_first",
            "ordinary_task_stale_fence_pass": False,
        }))
    finally:
        release_first.set()
        clear_task_registry()
        await database.disconnect()


asyncio.run(main())
'''


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    dsn = os.environ.get("AKSARA_DATABASE_URL") or os.environ["DATABASE_URL"]
    schema = "aksara_v071_task_recovery_" + uuid4().hex[:12]
    connection = await asyncpg.connect(dsn)
    try:
        await connection.execute(f'CREATE SCHEMA "{schema}"')
        try:
            url = urlsplit(dsn)
            query = dict(parse_qsl(url.query))
            query["search_path"] = schema
            scoped = urlunsplit(url._replace(query=urlencode(query)))
            env = {
                key: value
                for key, value in os.environ.items()
                if key not in {"PYTHONPATH", "DATABASE_URL"}
                and not key.startswith("AKSARA_")
            }
            env["DATABASE_URL"] = scoped
            with tempfile.TemporaryDirectory(prefix="aksara-task-recovery-") as directory:
                run = await asyncio.to_thread(
                    subprocess.run,
                    [str(args.python.absolute()), "-I", "-c", PROBE],
                    cwd=directory,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                if run.returncode:
                    message = (run.stderr or run.stdout).replace(
                        scoped, "[REDACTED]"
                    ).replace(dsn, "[REDACTED]")
                    raise RuntimeError(message)
                prefix = "TASK_STALE_RECOVERY_EVIDENCE="
                evidence = json.loads(
                    next(
                        line.removeprefix(prefix)
                        for line in run.stdout.splitlines()
                        if line.startswith(prefix)
                    )
                )
                package_path = Path(evidence.pop("package_path"))
                assert not package_path.is_relative_to(ROOT)
        finally:
            await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
        assert not await connection.fetchval(
            "SELECT 1 FROM pg_namespace WHERE nspname = $1", schema
        )
    finally:
        await connection.close()

    evidence.update(
        {
            "schema_version": 1,
            "pass": True,
            "source_checkout_framework_imports": False,
            "disposable_schema_removed": True,
            "scope": (
                "Negative installed-wheel probe for one ordinary unlinked task: "
                "recovery is forced while its first callable is active, a second "
                "call executes, and the unfenced first completion overwrites the "
                "stored second result. Admin role and owned schema; not a durable "
                "Operation, process-death, tenant/RLS, or external-effect test."
            ),
            "source_sha256": {
                "aksara/tasks.py": hashlib.sha256(
                    (ROOT / "aksara/tasks.py").read_bytes()
                ).hexdigest()
            },
            "page_sha256": {
                "docs/docs/advanced/background-tasks.md": hashlib.sha256(
                    (ROOT / "docs/docs/advanced/background-tasks.md").read_bytes()
                ).hexdigest()
            },
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }
    )
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print("PASS: ordinary-task stale recovery reproduced; disposable schema removed")


if __name__ == "__main__":
    asyncio.run(main())
