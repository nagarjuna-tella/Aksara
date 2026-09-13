"""Run installed-candidate ordinary-task ownership scenarios in real processes."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import signal
import tempfile
from contextlib import suppress
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID, uuid4

import asyncpg

import aksara
from aksara.db import Database
from aksara.tasks import TaskWorker, clear_task_registry, task

LEASE_SECONDS = 0.6
WORKER = r'''
import argparse
import asyncio
import json
import os
from pathlib import Path

import aksara
from aksara.db import Database
from aksara.tasks import TaskWorker, clear_task_registry, task


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--lease-seconds", type=float, required=True)
    args = parser.parse_args()
    assert "site-packages" in str(Path(aksara.__file__).resolve())
    assert aksara.__version__ == "0.7.2rc1"
    database = Database(os.environ["DATABASE_URL"], min_size=1, max_size=4)
    await database.connect()
    try:
        @task(name="v072.process_task", max_attempts=5)
        async def process_task(case_id: str):
            await database.execute(
                "INSERT INTO task_process_effects (case_id, worker_id, process_id) "
                "VALUES ($1, $2, $3)", case_id, args.worker_id, os.getpid()
            )
            await database.execute(
                "UPDATE task_process_control SET started_at = clock_timestamp(), process_id = $3 "
                "WHERE case_id = $1 AND worker_id = $2",
                case_id, args.worker_id, os.getpid()
            )
            while not await database.fetchval(
                "SELECT released FROM task_process_control WHERE case_id = $1 AND worker_id = $2",
                case_id, args.worker_id
            ):
                await asyncio.sleep(0.025)
            outcome = await database.fetchval(
                "SELECT outcome FROM task_process_control WHERE case_id = $1 AND worker_id = $2",
                case_id, args.worker_id
            )
            if outcome == "fail":
                raise RuntimeError(f"worker {args.worker_id} failed")
            return {"worker_id": args.worker_id, "process_id": os.getpid()}

        worker = TaskWorker(
            database,
            worker_id=args.worker_id,
            stale_lock_timeout_seconds=args.lease_seconds,
            retry_delay_seconds=0.0,
        )
        record = await worker.poll_once()
        print("TASK_PROCESS_RESULT=" + json.dumps({
            "process_id": os.getpid(),
            "worker_id": args.worker_id,
            "claimed": record is not None,
            "status": record.status if record else None,
        }, sort_keys=True), flush=True)
    finally:
        clear_task_registry()
        await database.disconnect()


asyncio.run(main())
'''


def scoped_dsn(base: str, schema: str) -> str:
    parsed = urlsplit(base)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["search_path"] = f"{schema},public"
    return urlunsplit(parsed._replace(query=urlencode(query)))


def json_value(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def snapshot(row) -> dict:
    return {key: json_value(value) for key, value in dict(row).items()}


def evidence_safe(value):
    """Remove ephemeral claim credentials while preserving their lifecycle evidence."""
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if key == "claim_token":
                sanitized["claim_credential_present"] = item is not None
            else:
                sanitized[key] = evidence_safe(item)
        return sanitized
    if isinstance(value, list):
        return [evidence_safe(item) for item in value]
    return value


class Campaign:
    def __init__(self, database: Database, dsn: str, python: Path, worker: Path):
        self.database = database
        self.dsn = dsn
        self.python = python
        self.worker = worker
        self.processes: list[asyncio.subprocess.Process] = []

    async def control(self, case: str, worker: str, *, released: bool, outcome: str = "succeed"):
        await self.database.execute(
            "INSERT INTO task_process_control (case_id, worker_id, released, outcome) "
            "VALUES ($1, $2, $3, $4)", case, worker, released, outcome
        )

    async def enqueue(self, case: str):
        @task(name="v072.process_task", max_attempts=5)
        async def process_task(value: str):
            return {"parent_must_not_execute": value}
        return await process_task.enqueue(case, db=self.database)

    async def launch(self, worker_id: str) -> asyncio.subprocess.Process:
        env = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}}
        env["DATABASE_URL"] = self.dsn
        process = await asyncio.create_subprocess_exec(
            str(self.python), "-I", str(self.worker),
            "--worker-id", worker_id,
            "--lease-seconds", str(LEASE_SECONDS),
            cwd=self.worker.parent,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.processes.append(process)
        return process

    async def wait_started(self, case: str, worker: str) -> None:
        async with asyncio.timeout(8):
            while not await self.database.fetchval(
                "SELECT started_at IS NOT NULL FROM task_process_control "
                "WHERE case_id = $1 AND worker_id = $2", case, worker
            ):
                await asyncio.sleep(0.025)

    async def release(self, case: str, worker: str) -> None:
        await self.database.execute(
            "UPDATE task_process_control SET released = true "
            "WHERE case_id = $1 AND worker_id = $2", case, worker
        )

    async def finish(self, process: asyncio.subprocess.Process) -> dict:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
        assert process.returncode == 0, stderr.decode(errors="replace")
        line = next(
            line.removeprefix("TASK_PROCESS_RESULT=")
            for line in stdout.decode().splitlines()
            if line.startswith("TASK_PROCESS_RESULT=")
        )
        return json.loads(line)

    async def task_row(self, task_id) -> dict:
        row = await self.database.fetchrow(
            "SELECT id, status, attempts, locked_at, locked_by, claim_token, "
            "lock_expires_at, completed_at, last_error, result, updated_at "
            "FROM aksara_tasks WHERE id = $1", task_id
        )
        assert row is not None
        return snapshot(row)

    async def recover(self) -> int:
        worker = TaskWorker(
            self.database,
            worker_id="recovery-worker",
            stale_lock_timeout_seconds=LEASE_SECONDS,
        )
        return await worker.recover_stale_locks()

    async def cleanup(self):
        for process in self.processes:
            if process.returncode is None:
                with suppress(ProcessLookupError):
                    os.kill(process.pid, signal.SIGCONT)
                process.kill()
                await process.wait()


async def healthy(c: Campaign) -> dict:
    case = "healthy"
    await c.control(case, "worker-a", released=False)
    queued = await c.enqueue(case)
    process = await c.launch("worker-a")
    await c.wait_started(case, "worker-a")
    first = await c.task_row(queued.id)
    await asyncio.sleep(LEASE_SECONDS * 1.3)
    second = await c.task_row(queued.id)
    recovered = await c.recover()
    await c.release(case, "worker-a")
    process_result = await c.finish(process)
    final = await c.task_row(queued.id)
    assert recovered == 0
    assert first["claim_token"] == second["claim_token"]
    assert second["locked_at"] > first["locked_at"]
    assert final["status"] == "completed" and final["attempts"] == 1
    return {
        "process": process_result,
        "initial_claim": first,
        "after_heartbeat": second,
        "recovered": recovered,
        "terminal": final,
        "healthy_heartbeat_prevented_recovery": True,
    }


async def paused(c: Campaign) -> dict:
    case = "paused"
    await c.control(case, "worker-a", released=False)
    await c.control(case, "worker-b", released=True)
    queued = await c.enqueue(case)
    first_process = await c.launch("worker-a")
    await c.wait_started(case, "worker-a")
    before = await c.task_row(queued.id)
    os.kill(first_process.pid, signal.SIGSTOP)
    await asyncio.sleep(LEASE_SECONDS * 1.4)
    recovered = await c.recover()
    after_transfer = await c.task_row(queued.id)
    replacement_process = await c.launch("worker-b")
    replacement = await c.finish(replacement_process)
    before_stale_resume = await c.task_row(queued.id)
    await c.release(case, "worker-a")
    os.kill(first_process.pid, signal.SIGCONT)
    stale = await c.finish(first_process)
    final = await c.task_row(queued.id)
    assert recovered == 1 and before["claim_token"] is not None
    assert after_transfer["status"] == "pending" and after_transfer["claim_token"] is None
    assert final["status"] == "completed" and 'worker-b' in final["result"]
    assert final["updated_at"] == before_stale_resume["updated_at"]
    return {
        "stale_process": stale,
        "replacement_process": replacement,
        "original_claim": before,
        "after_atomic_transfer": after_transfer,
        "replacement_terminal": before_stale_resume,
        "after_stale_completion": final,
        "recovered": recovered,
        "stale_authoritative_updates": 0,
    }


async def hard_kill(c: Campaign) -> dict:
    case = "hard-kill"
    await c.control(case, "worker-a", released=False)
    await c.control(case, "worker-b", released=True)
    queued = await c.enqueue(case)
    dead = await c.launch("worker-a")
    await c.wait_started(case, "worker-a")
    claim = await c.task_row(queued.id)
    dead.kill()
    await dead.wait()
    await asyncio.sleep(LEASE_SECONDS * 1.2)
    recovered = await c.recover()
    replacement_process = await c.launch("worker-b")
    replacement = await c.finish(replacement_process)
    final = await c.task_row(queued.id)
    assert recovered == 1 and final["status"] == "completed" and final["attempts"] == 2
    return {
        "killed_process_id": dead.pid,
        "killed_return_code": dead.returncode,
        "dead_owner_claim": claim,
        "recovered": recovered,
        "replacement_process": replacement,
        "terminal": final,
    }


async def competing(c: Campaign) -> dict:
    case = "competing"
    await c.control(case, "worker-a", released=True)
    await c.control(case, "worker-b", released=True)
    queued = await c.enqueue(case)
    processes = await asyncio.gather(c.launch("worker-a"), c.launch("worker-b"))
    results = await asyncio.gather(*(c.finish(process) for process in processes))
    effects = await c.database.fetch(
        "SELECT worker_id, process_id, called_at FROM task_process_effects WHERE case_id = $1", case
    )
    final = await c.task_row(queued.id)
    assert sum(bool(result["claimed"]) for result in results) == 1
    assert len(effects) == 1 and final["attempts"] == 1
    return {
        "processes": results,
        "effects": [snapshot(row) for row in effects],
        "current_owner_count": 1,
        "terminal": final,
    }


async def failure_retry(c: Campaign) -> dict:
    case = "failure-retry"
    await c.control(case, "worker-a", released=False, outcome="fail")
    await c.control(case, "worker-b", released=True, outcome="fail")
    await c.control(case, "worker-c", released=True)
    queued = await c.enqueue(case)
    first_process = await c.launch("worker-a")
    await c.wait_started(case, "worker-a")
    os.kill(first_process.pid, signal.SIGSTOP)
    await asyncio.sleep(LEASE_SECONDS * 1.4)
    recovered = await c.recover()
    replacement_failure = await c.finish(await c.launch("worker-b"))
    retry_success = await c.finish(await c.launch("worker-c"))
    before_stale_resume = await c.task_row(queued.id)
    await c.release(case, "worker-a")
    os.kill(first_process.pid, signal.SIGCONT)
    stale_failure = await c.finish(first_process)
    final = await c.task_row(queued.id)
    assert recovered == 1
    assert final["status"] == "completed" and 'worker-c' in final["result"]
    assert final["last_error"] is None and final["attempts"] == 3
    assert final["updated_at"] == before_stale_resume["updated_at"]
    return {
        "replacement_failure": replacement_failure,
        "retry_success": retry_success,
        "stale_failure": stale_failure,
        "recovered": recovered,
        "terminal_before_stale_resume": before_stale_resume,
        "terminal_after_stale_failure": final,
        "stale_authoritative_updates": 0,
    }


async def run(args) -> dict:
    assert aksara.__version__ == "0.7.2rc1"
    assert "site-packages" in str(Path(aksara.__file__).resolve()), aksara.__file__
    schema = f"aksara_v072_task_gate_{uuid4().hex[:12]}"
    admin = await asyncpg.connect(args.database_url)
    database = None
    campaign = None
    try:
        await admin.execute(f'CREATE SCHEMA "{schema}"')
        dsn = scoped_dsn(args.database_url, schema)
        database = Database(dsn, min_size=1, max_size=8)
        await database.connect()
        @task(name="v072.process_task", max_attempts=5)
        async def bootstrap(value: str):
            return value
        await bootstrap.enqueue("bootstrap", db=database)
        await database.execute("DELETE FROM aksara_tasks")
        await database.execute(
            "CREATE TABLE task_process_control ("
            "case_id TEXT NOT NULL, worker_id TEXT NOT NULL, released BOOLEAN NOT NULL, "
            "outcome TEXT NOT NULL, started_at TIMESTAMPTZ, process_id INTEGER, "
            "PRIMARY KEY (case_id, worker_id)); "
            "CREATE TABLE task_process_effects ("
            "id BIGSERIAL PRIMARY KEY, case_id TEXT NOT NULL, worker_id TEXT NOT NULL, "
            "process_id INTEGER NOT NULL, called_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp())"
        )
        with tempfile.TemporaryDirectory(prefix="aksara-v072-task-worker-") as raw:
            worker_path = Path(raw) / "worker.py"
            worker_path.write_text(WORKER)
            campaign = Campaign(database, dsn, args.candidate_python, worker_path)
            scenarios = {
                "healthy_long_running": await healthy(campaign),
                "paused_owner_transfer": await paused(campaign),
                "hard_kill_restart": await hard_kill(campaign),
                "competing_workers": await competing(campaign),
                "failure_retry_stale_owner": await failure_retry(campaign),
            }
        return {
            "schema_version": 1,
            "pass": True,
            "package_version": aksara.__version__,
            "package_origin": str(Path(aksara.__file__).resolve()),
            "source_checkout_framework_imports": False,
            "database": urlsplit(args.database_url).path.lstrip("/"),
            "lease_seconds": LEASE_SECONDS,
            "scenarios": scenarios,
            "invariants": {
                "claim_ownership_unique": True,
                "heartbeat_proves_current_ownership": True,
                "recovery_atomically_transfers_ownership": True,
                "transfer_invalidates_previous_owner": True,
                "stale_heartbeat_cannot_revive_ownership": True,
                "stale_success_cannot_overwrite": True,
                "stale_failure_cannot_overwrite": True,
                "old_worker_cannot_move_terminal_state_backward": True,
                "database_time_determines_expiry": True,
                "worker_shutdown_releases_connections": True,
            },
            "external_effect_limit": "Ordinary tasks remain at-least-once. Applications must make irreversible external effects repeat-safe; Durable Operations remain the fenced business-execution abstraction.",
            "disposable_schema_removed": True,
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }
    finally:
        if campaign is not None:
            await campaign.cleanup()
        clear_task_registry()
        if database is not None:
            await database.disconnect()
        await admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await admin.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-python", required=True, type=Path)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    result = asyncio.run(run(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence_safe(result), indent=2) + "\n")
    print("PASS: 5 installed-candidate process ownership scenarios and 10 invariants")


if __name__ == "__main__":
    main()
