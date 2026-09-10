"""
Tests for built-in background task processing.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from aksara import Aksara
from aksara.conf import settings
from aksara.db import Database
from aksara.tasks import (
    CRON_STATE_TABLE,
    TASKS_TABLE,
    TaskWorker,
    clear_task_registry,
    enqueue_task,
    ensure_cron_state_table,
    get_task_record,
    task,
)

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set",
)


@pytest.fixture(autouse=True)
def clear_tasks():
    """Reset registered tasks between tests."""
    clear_task_registry()
    yield
    clear_task_registry()


@pytest.fixture
async def db():
    """Create a database connection for task tests."""
    database = Database(os.environ["DATABASE_URL"])
    await database.connect()

    yield database

    for tbl in (TASKS_TABLE, CRON_STATE_TABLE):
        try:
            await database.execute(f'DROP TABLE IF EXISTS "{tbl}" CASCADE')
        except Exception:
            pass

    await database.disconnect()


class TestTaskWorker:
    """Integration tests for task enqueueing and worker execution."""

    @pytest.mark.asyncio
    async def test_executes_enqueued_task(self, db):
        seen: list[str] = []

        @task(name="tests.capture_value")
        async def capture_value(value: str) -> dict[str, str]:
            seen.append(value)
            return {"value": value}

        queued = await capture_value.enqueue("hello", db=db)
        worker = TaskWorker(db, retry_delay_seconds=0.0)

        processed = await worker.poll_once()
        stored = await get_task_record(queued.id, db=db)

        assert processed is not None
        assert processed.status == "completed"
        assert stored is not None
        assert stored.status == "completed"
        assert stored.result == {"value": "hello"}
        assert seen == ["hello"]

    @pytest.mark.asyncio
    async def test_retries_failed_task_then_completes(self, db):
        calls = {"count": 0}

        @task(name="tests.flaky_task", max_attempts=2)
        async def flaky_task() -> dict[str, str]:
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("boom")
            return {"status": "recovered"}

        queued = await flaky_task.enqueue(db=db)
        worker = TaskWorker(db, retry_delay_seconds=0.0)

        first_attempt = await worker.poll_once()
        after_first_attempt = await get_task_record(queued.id, db=db)
        second_attempt = await worker.poll_once()
        after_second_attempt = await get_task_record(queued.id, db=db)

        assert first_attempt is not None
        assert first_attempt.status == "pending"
        assert after_first_attempt is not None
        assert after_first_attempt.status == "pending"
        assert after_first_attempt.attempts == 1
        assert after_first_attempt.last_error == "boom"

        assert second_attempt is not None
        assert second_attempt.status == "completed"
        assert after_second_attempt is not None
        assert after_second_attempt.status == "completed"
        assert after_second_attempt.attempts == 2
        assert after_second_attempt.result == {"status": "recovered"}
        assert calls["count"] == 2


class TestStaleLockRecovery:
    """Integration tests for stale lock detection and recovery."""

    @pytest.mark.asyncio
    async def test_recovers_task_stuck_in_running(self, db):
        """A task whose locked_at is older than the timeout is reset to pending."""

        @task(name="tests.stale_task")
        async def stale_task() -> dict:
            return {}

        queued = await stale_task.enqueue(db=db)

        # Simulate a worker crash: mark task running with an old locked_at.
        await db.execute(
            f"""
            UPDATE "{TASKS_TABLE}"
            SET status = 'running',
                locked_at = CURRENT_TIMESTAMP - INTERVAL '10 minutes',
                attempts = 1
            WHERE id = $1
            """,
            queued.id,
        )

        worker = TaskWorker(db, stale_lock_timeout_seconds=300.0)
        recovered = await worker.recover_stale_locks()

        assert recovered == 1
        record = await get_task_record(queued.id, db=db)
        assert record is not None
        assert record.status == "pending"
        assert record.locked_at is None

    @pytest.mark.asyncio
    async def test_does_not_recover_recently_claimed_task(self, db):
        """A task claimed within the timeout window must not be reset."""

        @task(name="tests.fresh_task")
        async def fresh_task() -> dict:
            return {}

        queued = await fresh_task.enqueue(db=db)

        # Simulate an active worker: locked_at is right now.
        await db.execute(
            f"""
            UPDATE "{TASKS_TABLE}"
            SET status = 'running',
                locked_at = CURRENT_TIMESTAMP,
                attempts = 1
            WHERE id = $1
            """,
            queued.id,
        )

        worker = TaskWorker(db, stale_lock_timeout_seconds=300.0)
        recovered = await worker.recover_stale_locks()

        assert recovered == 0
        record = await get_task_record(queued.id, db=db)
        assert record is not None
        assert record.status == "running"

    @pytest.mark.asyncio
    async def test_recovered_task_can_be_re_executed(self, db):
        """After recovery the task is picked up and executed normally."""
        seen: list[str] = []

        @task(name="tests.recoverable_task")
        async def recoverable_task(value: str) -> dict:
            seen.append(value)
            return {"value": value}

        queued = await recoverable_task.enqueue("recovered", db=db)

        # Simulate a stuck worker.
        await db.execute(
            f"""
            UPDATE "{TASKS_TABLE}"
            SET status = 'running',
                locked_at = CURRENT_TIMESTAMP - INTERVAL '10 minutes',
                attempts = 1
            WHERE id = $1
            """,
            queued.id,
        )

        worker = TaskWorker(db, stale_lock_timeout_seconds=300.0)
        await worker.recover_stale_locks()
        processed = await worker.poll_once()

        assert processed is not None
        assert processed.status == "completed"
        assert seen == ["recovered"]


class TestTaskWorkerLifespan:
    """Unit tests for Aksara task worker startup and shutdown wiring."""

    def test_aksara_lifespan_starts_and_stops_worker(self, monkeypatch):
        monkeypatch.setattr(settings, "tasks_enabled", True)
        monkeypatch.setattr(settings, "installed_apps", [])

        connect = AsyncMock(return_value=None)
        disconnect = AsyncMock(return_value=None)
        start = AsyncMock(return_value=None)
        stop = AsyncMock(return_value=None)
        sync_content_types = AsyncMock(return_value=[])

        monkeypatch.setattr(Database, "connect", connect)
        monkeypatch.setattr(Database, "disconnect", disconnect)
        monkeypatch.setattr("aksara.model.base.finalize_relations", lambda: None)
        monkeypatch.setattr("aksara.contenttypes.clear_content_type_cache", lambda: None)
        monkeypatch.setattr("aksara.contenttypes.sync_content_types", sync_content_types)
        monkeypatch.setattr(TaskWorker, "start", start)
        monkeypatch.setattr(TaskWorker, "stop", stop)

        app = Aksara(
            database_url="postgresql://localhost/test",
            auto_discover_views=False,
            enable_admin=False,
        )
        app._print_startup = lambda: None
        app._print_shutdown = lambda: None

        with TestClient(app):
            assert app.task_worker is not None

        assert connect.await_count == 1
        assert disconnect.await_count == 1
        assert start.await_count == 1
        assert stop.await_count == 1
        assert sync_content_types.await_count == 1

    def test_user_lifespan_startup_failure_cleans_runtime(self, monkeypatch):
        """A user startup error stops the worker and returns the DB connection."""
        monkeypatch.setattr(settings, "tasks_enabled", True)
        monkeypatch.setattr(settings, "installed_apps", [])

        connect = AsyncMock(return_value=None)
        disconnect = AsyncMock(return_value=None)
        start = AsyncMock(return_value=None)
        stop = AsyncMock(return_value=None)
        sync_content_types = AsyncMock(return_value=[])

        monkeypatch.setattr(Database, "connect", connect)
        monkeypatch.setattr(Database, "disconnect", disconnect)
        monkeypatch.setattr("aksara.model.base.finalize_relations", lambda: None)
        monkeypatch.setattr("aksara.contenttypes.clear_content_type_cache", lambda: None)
        monkeypatch.setattr("aksara.contenttypes.sync_content_types", sync_content_types)
        monkeypatch.setattr(TaskWorker, "start", start)
        monkeypatch.setattr(TaskWorker, "stop", stop)

        @asynccontextmanager
        async def failing_lifespan(app):
            raise RuntimeError("unapplied migrations")
            yield

        app = Aksara(
            database_url="postgresql://localhost/test",
            auto_discover_views=False,
            enable_admin=False,
            lifespan=failing_lifespan,
        )
        app._print_startup = lambda: None
        app._print_shutdown = lambda: None

        with pytest.raises(RuntimeError, match="unapplied migrations"), TestClient(app):
            pass

        assert connect.await_count == 1
        assert start.await_count == 1
        assert stop.await_count == 1
        assert disconnect.await_count == 1
        assert app.task_worker is None
        assert app.db is None

    def test_partial_runtime_startup_failure_disconnects(self, monkeypatch):
        """Failure after connect releases the partial runtime state."""
        monkeypatch.setattr(settings, "tasks_enabled", True)
        monkeypatch.setattr(settings, "installed_apps", [])

        connect = AsyncMock(return_value=None)
        disconnect = AsyncMock(return_value=None)
        sync_content_types = AsyncMock(side_effect=RuntimeError("content sync failed"))

        monkeypatch.setattr(Database, "connect", connect)
        monkeypatch.setattr(Database, "disconnect", disconnect)
        monkeypatch.setattr("aksara.model.base.finalize_relations", lambda: None)
        monkeypatch.setattr("aksara.contenttypes.clear_content_type_cache", lambda: None)
        monkeypatch.setattr("aksara.contenttypes.sync_content_types", sync_content_types)

        app = Aksara(
            database_url="postgresql://localhost/test",
            auto_discover_views=False,
            enable_admin=False,
        )
        app._print_shutdown = lambda: None

        with pytest.raises(RuntimeError, match="content sync failed"), TestClient(app):
            pass

        assert connect.await_count == 1
        assert disconnect.await_count == 1
        assert app.task_worker is None
        assert app.db is None


class TestNamedQueues:
    """Tasks are routed to named queues; workers bind to specific queues."""

    @pytest.mark.asyncio
    async def test_worker_only_processes_its_queue(self, db):
        seen: list[str] = []

        @task(name="tests.email_task", queue="emails")
        async def email_task(msg: str) -> dict:
            seen.append(msg)
            return {"msg": msg}

        @task(name="tests.default_task", queue="default")
        async def default_task(msg: str) -> dict:
            seen.append(msg)
            return {"msg": msg}

        await email_task.enqueue("hello@email", db=db)
        await default_task.enqueue("hello@default", db=db)

        # Worker bound to "emails" queue only
        email_worker = TaskWorker(db, queues=["emails"])
        result = await email_worker.poll_once()

        assert result is not None
        assert result.status == "completed"
        assert seen == ["hello@email"]

        # Default queue task is still pending
        result2 = await email_worker.poll_once()
        assert result2 is None

    @pytest.mark.asyncio
    async def test_task_record_carries_queue_name(self, db):
        @task(name="tests.priority_task", queue="priority")
        async def priority_task() -> dict:
            return {}

        queued = await priority_task.enqueue(db=db)
        assert queued.queue == "priority"

        stored = await get_task_record(queued.id, db=db)
        assert stored is not None
        assert stored.queue == "priority"

    @pytest.mark.asyncio
    async def test_enqueue_overrides_queue(self, db):
        @task(name="tests.flexible_task", queue="default")
        async def flexible_task() -> dict:
            return {}

        queued = await flexible_task.enqueue(queue="urgent", db=db)
        assert queued.queue == "urgent"

    @pytest.mark.asyncio
    async def test_worker_with_no_queue_filter_processes_all(self, db):
        seen: list[str] = []

        @task(name="tests.any_queue_a", queue="a")
        async def task_a() -> dict:
            seen.append("a")
            return {}

        @task(name="tests.any_queue_b", queue="b")
        async def task_b() -> dict:
            seen.append("b")
            return {}

        await task_a.enqueue(db=db)
        await task_b.enqueue(db=db)

        worker = TaskWorker(db, queues=None)  # no queue filter
        await worker.poll_once()
        await worker.poll_once()

        assert sorted(seen) == ["a", "b"]


class TestConcurrentWorker:
    """TaskWorker with concurrency > 1 processes multiple tasks simultaneously."""

    @pytest.mark.asyncio
    async def test_concurrent_worker_processes_n_tasks(self, db):
        """A concurrency=3 worker claims 3 tasks before any finishes."""
        barrier = asyncio.Event()
        started = []
        finished = []

        @task(name="tests.barrier_task")
        async def barrier_task(idx: int) -> dict:
            started.append(idx)
            await barrier.wait()
            finished.append(idx)
            return {"idx": idx}

        for i in range(3):
            await barrier_task.enqueue(i, db=db)

        worker = TaskWorker(db, concurrency=3)
        await worker.start()

        # Wait until all 3 are started (they block on the barrier)
        for _ in range(50):
            if len(started) == 3:
                break
            await asyncio.sleep(0.05)

        assert len(started) == 3, f"Expected 3 started, got {started}"
        assert len(finished) == 0  # None have completed yet

        barrier.set()
        await worker.stop()

        assert sorted(finished) == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_concurrency_1_is_serial(self, db):
        """Default concurrency=1 processes tasks one after the other."""
        order: list[int] = []

        @task(name="tests.serial_task")
        async def serial_task(idx: int) -> dict:
            order.append(idx)
            return {}

        for i in range(3):
            await serial_task.enqueue(i, db=db)

        worker = TaskWorker(db, concurrency=1, poll_interval=0.05)
        await worker.start()

        for _ in range(60):
            if len(order) == 3:
                break
            await asyncio.sleep(0.05)

        await worker.stop()
        assert len(order) == 3


class TestExponentialBackoff:
    """Retry delays grow exponentially between failed attempts."""

    @pytest.mark.asyncio
    async def test_backoff_delay_increases_per_attempt(self, db):
        """The available_at gap doubles on each failure with base=2."""

        @task(name="tests.always_fails", max_attempts=3)
        async def always_fails() -> dict:
            raise RuntimeError("always fails")

        queued = await always_fails.enqueue(db=db)
        # base_delay=10, base=2 → attempt 1 delay=10, attempt 2 delay=20
        worker = TaskWorker(db, retry_delay_seconds=10.0, retry_backoff_base=2.0)

        # First failure
        await worker.poll_once()
        after_first = await get_task_record(queued.id, db=db)
        assert after_first is not None
        assert after_first.status == "pending"
        assert after_first.attempts == 1
        # available_at should be ~10s in the future
        from datetime import timezone
        delay_secs = (after_first.available_at - datetime.now(timezone.utc)).total_seconds()
        assert 5 < delay_secs <= 12, f"Expected ~10s delay, got {delay_secs:.1f}s"

        # Make the task available now so we can poll again
        await db.execute(
            f"UPDATE \"{TASKS_TABLE}\" SET available_at = CURRENT_TIMESTAMP WHERE id = $1",
            queued.id,
        )

        # Second failure
        await worker.poll_once()
        after_second = await get_task_record(queued.id, db=db)
        assert after_second is not None
        assert after_second.status == "pending"
        assert after_second.attempts == 2
        delay_secs2 = (after_second.available_at - datetime.now(timezone.utc)).total_seconds()
        assert 15 < delay_secs2 <= 22, f"Expected ~20s delay, got {delay_secs2:.1f}s"

    @pytest.mark.asyncio
    async def test_backoff_base_1_is_flat(self, db):
        """retry_backoff_base=1.0 produces a constant delay (no growth)."""

        @task(name="tests.flat_retry", max_attempts=3)
        async def flat_retry() -> dict:
            raise RuntimeError("fail")

        queued = await flat_retry.enqueue(db=db)
        worker = TaskWorker(db, retry_delay_seconds=5.0, retry_backoff_base=1.0)

        await worker.poll_once()
        after = await get_task_record(queued.id, db=db)
        assert after is not None
        from datetime import timezone
        delay = (after.available_at - datetime.now(timezone.utc)).total_seconds()
        assert 3 < delay <= 7, f"Expected ~5s flat delay, got {delay:.1f}s"

    @pytest.mark.asyncio
    async def test_backoff_capped_at_max_delay(self, db):
        """Retry delay is capped at retry_max_delay_seconds."""

        @task(name="tests.capped_retry", max_attempts=5)
        async def capped_retry() -> dict:
            raise RuntimeError("fail")

        queued = await capped_retry.enqueue(db=db)
        # With base=10, base_delay=100, max=50 → delay never exceeds 50s
        worker = TaskWorker(
            db,
            retry_delay_seconds=100.0,
            retry_backoff_base=10.0,
            retry_max_delay_seconds=50.0,
        )

        await worker.poll_once()
        after = await get_task_record(queued.id, db=db)
        assert after is not None
        from datetime import timezone
        delay = (after.available_at - datetime.now(timezone.utc)).total_seconds()
        assert delay <= 52, f"Delay exceeded max: {delay:.1f}s"


class TestTaskCleanup:
    """Old completed/failed tasks are purged by purge_old_tasks."""

    @pytest.mark.asyncio
    async def test_purges_old_completed_tasks(self, db):
        @task(name="tests.completed_task")
        async def completed_task() -> dict:
            return {}

        queued = await completed_task.enqueue(db=db)
        worker = TaskWorker(db)
        await worker.poll_once()

        # Age the record artificially
        await db.execute(
            f"UPDATE \"{TASKS_TABLE}\" SET updated_at = NOW() - INTERVAL '8 days' WHERE id = $1",
            queued.id,
        )

        count = await worker.purge_old_tasks(older_than_seconds=7 * 86400)
        assert count == 1

        record = await get_task_record(queued.id, db=db)
        assert record is None

    @pytest.mark.asyncio
    async def test_does_not_purge_recent_tasks(self, db):
        @task(name="tests.recent_task")
        async def recent_task() -> dict:
            return {}

        queued = await recent_task.enqueue(db=db)
        worker = TaskWorker(db)
        await worker.poll_once()

        # Task is fresh (just completed) — should not be purged
        count = await worker.purge_old_tasks(older_than_seconds=7 * 86400)
        assert count == 0

        record = await get_task_record(queued.id, db=db)
        assert record is not None

    @pytest.mark.asyncio
    async def test_purge_respects_status_filter(self, db):
        """Only the specified statuses are purged."""

        @task(name="tests.failed_for_purge", max_attempts=1)
        async def failed_for_purge() -> dict:
            raise RuntimeError("fail")

        queued = await failed_for_purge.enqueue(db=db)
        worker = TaskWorker(db)
        await worker.poll_once()

        # Age the record
        await db.execute(
            f"UPDATE \"{TASKS_TABLE}\" SET updated_at = NOW() - INTERVAL '8 days' WHERE id = $1",
            queued.id,
        )

        # Purge 'completed' only — should not touch 'failed'
        count = await worker.purge_old_tasks(
            statuses=("completed",), older_than_seconds=7 * 86400
        )
        assert count == 0

        # Purge 'failed' — should delete it
        count = await worker.purge_old_tasks(
            statuses=("failed",), older_than_seconds=7 * 86400
        )
        assert count == 1


class TestRecurringTasks:
    """Tasks registered with every= are automatically scheduled by the worker."""

    @pytest.mark.asyncio
    async def test_recurring_task_is_enqueued_on_first_schedule(self, db):
        seen: list[int] = []

        @task(name="tests.recurring_heartbeat", every=timedelta(minutes=5))
        async def recurring_heartbeat() -> dict:
            seen.append(1)
            return {}

        worker = TaskWorker(db)
        enqueued = await worker._schedule_recurring_tasks()
        assert enqueued == 1

        # The task should now be in the queue
        rows = await db.fetch(
            f"SELECT * FROM \"{TASKS_TABLE}\" WHERE task_name = $1",
            "tests.recurring_heartbeat",
        )
        assert len(rows) == 1
        assert rows[0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_recurring_task_not_double_enqueued(self, db):
        """Calling the scheduler twice in quick succession enqueues only once."""

        @task(name="tests.recurring_once", every=timedelta(minutes=5))
        async def recurring_once() -> dict:
            return {}

        worker = TaskWorker(db)
        first = await worker._schedule_recurring_tasks()
        second = await worker._schedule_recurring_tasks()

        assert first == 1
        assert second == 0

        rows = await db.fetch(
            f"SELECT * FROM \"{TASKS_TABLE}\" WHERE task_name = $1",
            "tests.recurring_once",
        )
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_recurring_task_re_enqueues_after_interval(self, db):
        """After the interval elapses, the scheduler enqueues a new instance."""

        @task(name="tests.recurring_fast", every=timedelta(seconds=1))
        async def recurring_fast() -> dict:
            return {}

        worker = TaskWorker(db)
        first = await worker._schedule_recurring_tasks()
        assert first == 1

        # Rewind the cron state to simulate time passing
        await db.execute(
            f"""
            UPDATE "{CRON_STATE_TABLE}"
            SET last_enqueued_at = CURRENT_TIMESTAMP - INTERVAL '2 seconds'
            WHERE task_name = $1
            """,
            "tests.recurring_fast",
        )

        second = await worker._schedule_recurring_tasks()
        assert second == 1

        rows = await db.fetch(
            f"SELECT * FROM \"{TASKS_TABLE}\" WHERE task_name = $1 ORDER BY created_at",
            "tests.recurring_fast",
        )
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_recurring_task_every_accepts_seconds(self, db):
        """every= accepts plain int/float seconds in addition to timedelta."""

        @task(name="tests.recurring_int_every", every=300)
        async def recurring_int_every() -> dict:
            return {}

        from aksara.tasks import _TASK_REGISTRY
        reg = _TASK_REGISTRY["tests.recurring_int_every"]
        assert reg.every == timedelta(seconds=300)

    @pytest.mark.asyncio
    async def test_recurring_task_queue_filter(self, db):
        """Worker bound to a queue only schedules recurring tasks on that queue."""

        @task(name="tests.recurring_email", every=timedelta(minutes=1), queue="emails")
        async def recurring_email() -> dict:
            return {}

        @task(name="tests.recurring_default", every=timedelta(minutes=1), queue="default")
        async def recurring_default() -> dict:
            return {}

        email_worker = TaskWorker(db, queues=["emails"])
        enqueued = await email_worker._schedule_recurring_tasks()
        assert enqueued == 1

        rows = await db.fetch(
            f"SELECT task_name FROM \"{TASKS_TABLE}\" ORDER BY task_name"
        )
        task_names = [r["task_name"] for r in rows]
        assert "tests.recurring_email" in task_names
        assert "tests.recurring_default" not in task_names
