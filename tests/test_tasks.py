"""
Tests for built-in background task processing.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from aksara import Aksara
from aksara.conf import settings
from aksara.db import Database
from aksara.tasks import TASKS_TABLE, TaskWorker, clear_task_registry, get_task_record, task


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

    try:
        await database.execute(f'DROP TABLE IF EXISTS "{TASKS_TABLE}" CASCADE')
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