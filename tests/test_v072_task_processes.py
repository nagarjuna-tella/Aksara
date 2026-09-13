"""Real-process campaign for ordinary task claim ownership and recovery."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio

from aksara.db import Database
from aksara.tasks import TaskWorker, clear_task_registry, get_task_record, task

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"), reason="DATABASE_URL is required"
)

ROOT = Path(__file__).resolve().parents[1]
WORKER_SCRIPT = ROOT / "tests/prototypes/v072_task_process_worker.py"
LEASE_SECONDS = 0.4


def _scoped_dsn(database_url: str, schema: str) -> str:
    parsed = urlsplit(database_url)
    query = dict(parse_qsl(parsed.query))
    query["search_path"] = f"{schema},public"
    return urlunsplit(parsed._replace(query=urlencode(query)))


@dataclass
class ProcessCampaign:
    database: Database
    dsn: str
    processes: list[asyncio.subprocess.Process] = field(default_factory=list)

    async def launch(self, worker_id: str) -> asyncio.subprocess.Process:
        env = os.environ.copy()
        env["DATABASE_URL"] = self.dsn
        env["PYTHONPATH"] = str(ROOT)
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(WORKER_SCRIPT),
            "--worker-id",
            worker_id,
            "--lease-seconds",
            str(LEASE_SECONDS),
            cwd=ROOT,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.processes.append(process)
        return process

    async def control(
        self,
        case_id: str,
        worker_id: str,
        *,
        released: bool,
        outcome: str = "succeed",
    ) -> None:
        await self.database.execute(
            """
            INSERT INTO task_process_control (
                case_id, worker_id, released, outcome
            ) VALUES ($1, $2, $3, $4)
            """,
            case_id,
            worker_id,
            released,
            outcome,
        )

    async def release(self, case_id: str, worker_id: str) -> None:
        await self.database.execute(
            """
            UPDATE task_process_control SET released = TRUE
            WHERE case_id = $1 AND worker_id = $2
            """,
            case_id,
            worker_id,
        )

    async def wait_started(self, case_id: str, worker_id: str) -> None:
        async with asyncio.timeout(5):
            while not await self.database.fetchval(
                """
                SELECT started_at IS NOT NULL FROM task_process_control
                WHERE case_id = $1 AND worker_id = $2
                """,
                case_id,
                worker_id,
            ):
                await asyncio.sleep(0.025)

    async def finish(self, process: asyncio.subprocess.Process) -> dict[str, object]:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=8)
        assert process.returncode == 0, stderr.decode()
        prefix = "TASK_PROCESS_RESULT="
        line = next(
            item.removeprefix(prefix)
            for item in stdout.decode().splitlines()
            if item.startswith(prefix)
        )
        return json.loads(line)


@pytest_asyncio.fixture
async def campaign() -> AsyncIterator[ProcessCampaign]:
    database_url = os.environ["DATABASE_URL"]
    schema = f"aksara_v072_task_process_{uuid4().hex[:12]}"
    admin = await asyncpg.connect(database_url)
    database: Database | None = None
    state: ProcessCampaign | None = None
    try:
        await admin.execute(f'CREATE SCHEMA "{schema}"')
        scoped = _scoped_dsn(database_url, schema)
        database = Database(scoped, min_size=1, max_size=8)
        await database.connect()

        @task(name="tests.v072.process_task", max_attempts=5)
        async def process_task(case_id: str) -> dict[str, str]:
            return {"parent_must_not_execute": case_id}

        await process_task.enqueue("schema-bootstrap", db=database)
        await database.execute("DELETE FROM aksara_tasks")
        await database.execute(
            """
            CREATE TABLE task_process_control (
                case_id TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                released BOOLEAN NOT NULL,
                outcome TEXT NOT NULL,
                started_at TIMESTAMPTZ,
                PRIMARY KEY (case_id, worker_id)
            );
            CREATE TABLE task_process_effects (
                id BIGSERIAL PRIMARY KEY,
                case_id TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                called_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
            );
            """
        )
        state = ProcessCampaign(database=database, dsn=scoped)
        yield state
    finally:
        if state is not None:
            for process in state.processes:
                if process.returncode is None:
                    try:
                        os.kill(process.pid, signal.SIGCONT)
                    except ProcessLookupError:
                        pass
                    process.kill()
                    await process.wait()
        clear_task_registry()
        if database is not None:
            await database.disconnect()
        await admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await admin.close()


async def _enqueue(campaign: ProcessCampaign, case_id: str):
    @task(name="tests.v072.process_task", max_attempts=5)
    async def process_task(value: str) -> dict[str, str]:
        return {"parent_must_not_execute": value}

    return await process_task.enqueue(case_id, db=campaign.database)


@pytest.mark.asyncio
async def test_healthy_process_heartbeats_past_stale_timeout(campaign):
    case_id = "healthy"
    await campaign.control(case_id, "worker-a", released=False)
    queued = await _enqueue(campaign, case_id)
    process_a = await campaign.launch("worker-a")
    await campaign.wait_started(case_id, "worker-a")

    await asyncio.sleep(LEASE_SECONDS * 2.25)
    recovery = TaskWorker(
        campaign.database,
        worker_id="recovery-worker",
        stale_lock_timeout_seconds=LEASE_SECONDS,
    )
    assert await recovery.recover_stale_locks() == 0
    await campaign.release(case_id, "worker-a")
    result_a = await campaign.finish(process_a)

    final = await get_task_record(queued.id, db=campaign.database)
    assert result_a["status"] == "completed"
    assert final is not None and final.result == {"worker_id": "worker-a"}
    assert final.attempts == 1


@pytest.mark.asyncio
async def test_paused_process_is_recovered_and_stale_completion_is_rejected(campaign):
    case_id = "paused"
    await campaign.control(case_id, "worker-a", released=False)
    await campaign.control(case_id, "worker-b", released=True)
    queued = await _enqueue(campaign, case_id)
    process_a = await campaign.launch("worker-a")
    await campaign.wait_started(case_id, "worker-a")

    os.kill(process_a.pid, signal.SIGSTOP)
    await asyncio.sleep(LEASE_SECONDS * 1.4)
    recovery = TaskWorker(
        campaign.database,
        worker_id="recovery-worker",
        stale_lock_timeout_seconds=LEASE_SECONDS,
    )
    assert await recovery.recover_stale_locks() == 1
    process_b = await campaign.launch("worker-b")
    result_b = await campaign.finish(process_b)
    assert result_b["status"] == "completed"

    await campaign.release(case_id, "worker-a")
    os.kill(process_a.pid, signal.SIGCONT)
    await campaign.finish(process_a)
    final = await get_task_record(queued.id, db=campaign.database)
    assert final is not None and final.status == "completed"
    assert final.result == {"worker_id": "worker-b"}
    assert final.attempts == 2


@pytest.mark.asyncio
async def test_hard_killed_process_is_recovered_after_restart(campaign):
    case_id = "hard-kill"
    await campaign.control(case_id, "worker-a", released=False)
    await campaign.control(case_id, "worker-b", released=True)
    queued = await _enqueue(campaign, case_id)
    process_a = await campaign.launch("worker-a")
    await campaign.wait_started(case_id, "worker-a")

    process_a.kill()
    await process_a.wait()
    await asyncio.sleep(LEASE_SECONDS * 1.2)
    recovery = TaskWorker(
        campaign.database,
        worker_id="recovery-worker",
        stale_lock_timeout_seconds=LEASE_SECONDS,
    )
    assert await recovery.recover_stale_locks() == 1
    process_b = await campaign.launch("worker-b")
    await campaign.finish(process_b)

    final = await get_task_record(queued.id, db=campaign.database)
    assert final is not None and final.status == "completed"
    assert final.result == {"worker_id": "worker-b"}
    assert final.attempts == 2


@pytest.mark.asyncio
async def test_competing_processes_create_one_current_owner(campaign):
    case_id = "competing"
    await campaign.control(case_id, "worker-a", released=True)
    await campaign.control(case_id, "worker-b", released=True)
    queued = await _enqueue(campaign, case_id)

    process_a, process_b = await asyncio.gather(
        campaign.launch("worker-a"),
        campaign.launch("worker-b"),
    )
    results = await asyncio.gather(
        campaign.finish(process_a), campaign.finish(process_b)
    )

    final = await get_task_record(queued.id, db=campaign.database)
    effects = await campaign.database.fetch(
        "SELECT worker_id FROM task_process_effects WHERE case_id = $1", case_id
    )
    assert sum(bool(result["claimed"]) for result in results) == 1
    assert len(effects) == 1
    assert final is not None and final.status == "completed"
    assert final.attempts == 1
    assert final.result == {"worker_id": effects[0]["worker_id"]}


@pytest.mark.asyncio
async def test_stale_failure_cannot_overwrite_later_retry_success(campaign):
    case_id = "stale-failure"
    await campaign.control(case_id, "worker-a", released=False, outcome="fail")
    await campaign.control(case_id, "worker-b", released=True, outcome="fail")
    await campaign.control(case_id, "worker-c", released=True)
    queued = await _enqueue(campaign, case_id)
    process_a = await campaign.launch("worker-a")
    await campaign.wait_started(case_id, "worker-a")

    os.kill(process_a.pid, signal.SIGSTOP)
    await asyncio.sleep(LEASE_SECONDS * 1.4)
    recovery = TaskWorker(
        campaign.database,
        worker_id="recovery-worker",
        stale_lock_timeout_seconds=LEASE_SECONDS,
    )
    assert await recovery.recover_stale_locks() == 1
    process_b = await campaign.launch("worker-b")
    result_b = await campaign.finish(process_b)
    assert result_b["status"] == "pending"
    process_c = await campaign.launch("worker-c")
    await campaign.finish(process_c)

    await campaign.release(case_id, "worker-a")
    os.kill(process_a.pid, signal.SIGCONT)
    await campaign.finish(process_a)
    final = await get_task_record(queued.id, db=campaign.database)
    assert final is not None and final.status == "completed"
    assert final.result == {"worker_id": "worker-c"}
    assert final.last_error is None
    assert final.attempts == 3
