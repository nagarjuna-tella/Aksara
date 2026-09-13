"""Regression coverage for ordinary-task lease ownership and stale fencing."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio

from aksara.db import Database
from aksara.tasks import (
    TASKS_TABLE,
    TaskRecord,
    TaskWorker,
    clear_task_registry,
    get_task_record,
    task,
)

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"), reason="DATABASE_URL is required"
)


def _scoped_dsn(database_url: str, schema: str) -> str:
    parsed = urlsplit(database_url)
    query = dict(parse_qsl(parsed.query))
    query["search_path"] = f"{schema},public"
    return urlunsplit(parsed._replace(query=urlencode(query)))


@pytest_asyncio.fixture
async def task_db() -> AsyncIterator[Database]:
    database_url = os.environ["DATABASE_URL"]
    schema = f"aksara_v072_task_{uuid4().hex[:12]}"
    admin = await asyncpg.connect(database_url)
    database: Database | None = None
    try:
        await admin.execute(f'CREATE SCHEMA "{schema}"')
        database = Database(_scoped_dsn(database_url, schema), min_size=1, max_size=8)
        await database.connect()
        yield database
    finally:
        clear_task_registry()
        if database is not None:
            await database.disconnect()
        await admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await admin.close()


@pytest.mark.asyncio
async def test_claim_records_database_time_lease_and_unique_owner(task_db):
    @task(name="tests.v072.unique_claim")
    async def unique_claim() -> dict[str, bool]:
        return {"ok": True}

    queued = await unique_claim.enqueue(db=task_db)
    workers = [
        TaskWorker(task_db, worker_id="worker-a"),
        TaskWorker(task_db, worker_id="worker-b"),
    ]

    claims = await asyncio.gather(*(worker._claim_task() for worker in workers))
    claimed = [claim for claim in claims if claim is not None]

    assert len(claimed) == 1
    assert claimed[0].id == queued.id
    assert claimed[0].locked_by in {"worker-a", "worker-b"}
    assert claimed[0].claim_token is not None
    assert claimed[0].locked_at is not None
    assert claimed[0].lock_expires_at is not None
    assert claimed[0].lock_expires_at > claimed[0].locked_at


@pytest.mark.asyncio
async def test_heartbeat_prevents_recovery_of_healthy_long_running_task(task_db):
    started = asyncio.Event()
    release = asyncio.Event()

    @task(name="tests.v072.healthy_long_runner")
    async def healthy_long_runner() -> dict[str, str]:
        started.set()
        await release.wait()
        return {"owner": "worker-a"}

    queued = await healthy_long_runner.enqueue(db=task_db)
    worker_a = TaskWorker(
        task_db,
        worker_id="worker-a",
        stale_lock_timeout_seconds=0.3,
    )
    worker_b = TaskWorker(
        task_db,
        worker_id="worker-b",
        stale_lock_timeout_seconds=0.3,
    )

    running = asyncio.create_task(worker_a.poll_once())
    await asyncio.wait_for(started.wait(), timeout=2)
    initial = await get_task_record(queued.id, db=task_db)
    assert initial is not None and initial.lock_expires_at is not None

    await asyncio.sleep(0.65)
    active = await get_task_record(queued.id, db=task_db)
    assert active is not None and active.lock_expires_at is not None
    assert active.lock_expires_at > initial.lock_expires_at
    assert await worker_b.recover_stale_locks() == 0
    assert await worker_b._claim_task() is None

    release.set()
    completed = await asyncio.wait_for(running, timeout=2)
    assert completed is not None
    assert completed.status == "completed"
    assert completed.result == {"owner": "worker-a"}


@pytest.mark.asyncio
async def test_recovery_transfers_ownership_and_fences_stale_completion(task_db):
    calls = 0

    @task(name="tests.v072.stale_completion")
    async def stale_completion() -> dict[str, str]:
        nonlocal calls
        calls += 1
        return {"completion": "new-owner" if calls == 1 else "stale-owner"}

    queued = await stale_completion.enqueue(db=task_db)
    worker_a = TaskWorker(task_db, worker_id="worker-a", stale_lock_timeout_seconds=30)
    worker_b = TaskWorker(task_db, worker_id="worker-b", stale_lock_timeout_seconds=30)
    stale_claim = await worker_a._claim_task()
    assert stale_claim is not None

    await task_db.execute(
        f'''
        UPDATE "{TASKS_TABLE}"
        SET lock_expires_at = clock_timestamp() - INTERVAL '1 second'
        WHERE id = $1
        ''',
        queued.id,
    )
    assert await worker_b.recover_stale_locks() == 1
    current = await worker_b.poll_once()
    assert current is not None and current.result == {"completion": "new-owner"}

    await worker_a._process_task(stale_claim)
    final = await get_task_record(queued.id, db=task_db)
    assert final is not None
    assert final.status == "completed"
    assert final.result == {"completion": "new-owner"}
    assert final.attempts == 2
    assert calls == 2


@pytest.mark.asyncio
async def test_stale_heartbeat_and_failure_cannot_regress_terminal_state(task_db):
    calls = 0

    @task(name="tests.v072.stale_failure", max_attempts=3)
    async def stale_failure() -> dict[str, str]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("late stale failure")
        return {"completion": "new-owner"}

    queued = await stale_failure.enqueue(db=task_db)
    worker_a = TaskWorker(task_db, worker_id="worker-a", stale_lock_timeout_seconds=30)
    worker_b = TaskWorker(task_db, worker_id="worker-b", stale_lock_timeout_seconds=30)
    stale_claim = await worker_a._claim_task()
    assert stale_claim is not None

    await task_db.execute(
        f'''
        UPDATE "{TASKS_TABLE}"
        SET lock_expires_at = clock_timestamp() - INTERVAL '1 second'
        WHERE id = $1
        ''',
        queued.id,
    )
    assert await worker_b.recover_stale_locks() == 1
    completed = await worker_b.poll_once()
    assert completed is not None and completed.status == "completed"
    assert not await worker_a._renew_task_lease(stale_claim)

    await worker_a._process_task(stale_claim)
    final = await get_task_record(queued.id, db=task_db)
    assert final is not None
    assert final.status == "completed"
    assert final.result == {"completion": "new-owner"}
    assert final.last_error is None
    assert calls == 2


@pytest.mark.asyncio
async def test_graceful_stop_drains_task_and_heartbeat(task_db):
    started = asyncio.Event()
    release = asyncio.Event()

    @task(name="tests.v072.graceful_stop")
    async def graceful_stop() -> dict[str, bool]:
        started.set()
        await release.wait()
        return {"done": True}

    queued = await graceful_stop.enqueue(db=task_db)
    worker = TaskWorker(
        task_db,
        worker_id="worker-a",
        poll_interval=0.01,
        stale_lock_timeout_seconds=0.3,
    )
    await worker.start()
    await asyncio.wait_for(started.wait(), timeout=2)

    stopping = asyncio.create_task(worker.stop())
    await asyncio.sleep(0.4)
    assert not stopping.done()
    running = await get_task_record(queued.id, db=task_db)
    assert running is not None and running.status == "running"
    assert running.lock_expires_at is not None
    assert running.lock_expires_at > await task_db.fetchval("SELECT clock_timestamp()")

    release.set()
    await asyncio.wait_for(stopping, timeout=2)
    final = await get_task_record(queued.id, db=task_db)
    assert final is not None and final.status == "completed"
    heartbeat_names = {
        pending.get_name()
        for pending in asyncio.all_tasks()
        if not pending.done()
    }
    assert f"aksara-task-heartbeat-{queued.id}" not in heartbeat_names


def test_task_record_defaults_allow_pre_claim_records():
    record = TaskRecord(
        id=uuid4(),
        task_name="tests.v072.pending",
        payload={},
        status="pending",
        attempts=0,
        max_attempts=1,
    )
    assert record.locked_by is None
    assert record.claim_token is None
    assert record.lock_expires_at is None
