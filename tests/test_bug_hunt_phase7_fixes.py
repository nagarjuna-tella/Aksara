"""
Regression tests for Phase 7 bug-hunt findings on the durable task
subsystem and tenant middleware.

Each test exercises one of the four confirmed bugs from
`bug-hunt/phase-7-findings.md`. The task-subsystem tests require a
live PostgreSQL connection (via DATABASE_URL); they skip otherwise.
The middleware test runs against an in-memory ASGI app.
"""

from __future__ import annotations

import dataclasses
import os
from typing import Any

import pytest
from starlette.requests import Request as StarletteRequest
from starlette.testclient import TestClient

from aksara import Aksara
from aksara.context_state import tenant_id_var
from aksara.middleware import TenantMiddleware
from aksara.tasks import (
    CRON_STATE_TABLE,
    TASKS_TABLE,
    TaskRecord,
    TaskWorker,
    clear_task_registry,
    enqueue_task,
    get_task_record,
    task,
)


_db_required = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set",
)


# ─── Fix #3 — TenantMiddleware rejects empty tenant headers ───────────────


class TestTenantMiddlewareEmptyHeader:
    def test_empty_header_returns_400(self):
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[(TenantMiddleware, {})],
        )

        @app.get("/whoami")
        async def whoami(request: StarletteRequest):
            return {"tenant_id": request.state.tenant_id}

        client = TestClient(app)
        response = client.get("/whoami", headers={"X-Tenant-Id": ""})
        # Pre-fix the request silently succeeded with tenant_id == "",
        # which then disables tenant scoping in the DB layer. The fix
        # must fail closed.
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    def test_whitespace_only_header_returns_400(self):
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[(TenantMiddleware, {})],
        )

        @app.get("/whoami")
        async def whoami(request: StarletteRequest):
            return {"tenant_id": request.state.tenant_id}

        client = TestClient(app)
        response = client.get("/whoami", headers={"X-Tenant-Id": "   "})
        assert response.status_code == 400

    def test_missing_header_still_allowed(self):
        """Sanity: omitting the header is distinct from sending it empty."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[(TenantMiddleware, {})],
        )

        @app.get("/whoami")
        async def whoami(request: StarletteRequest):
            return {"tenant_id": request.state.tenant_id}

        client = TestClient(app)
        response = client.get("/whoami")
        assert response.status_code == 200
        assert response.json()["tenant_id"] is None


# ─── Fix #4 — TaskRecord carries a tenant_id field ─────────────────────────


class TestTaskRecordHasTenantId:
    def test_dataclass_exposes_tenant_id_field(self):
        names = {f.name for f in dataclasses.fields(TaskRecord)}
        assert "tenant_id" in names

    def test_default_tenant_id_is_none(self):
        record = TaskRecord(
            id="00000000-0000-0000-0000-000000000000",  # type: ignore[arg-type]
            task_name="x",
            payload={},
            status="pending",
            attempts=0,
            max_attempts=1,
        )
        assert record.tenant_id is None


# ─── Fix #1 + #2 — tenant context survives the enqueue → worker round-trip ─


@_db_required
class TestTaskTenantContextRoundTrip:
    @pytest.fixture(autouse=True)
    def _clear(self):
        clear_task_registry()
        yield
        clear_task_registry()

    @pytest.fixture
    async def db(self):
        from aksara.db import Database

        database = Database(os.environ["DATABASE_URL"])
        await database.connect()
        try:
            yield database
        finally:
            for tbl in (TASKS_TABLE, CRON_STATE_TABLE):
                try:
                    await database.execute(f'DROP TABLE IF EXISTS "{tbl}" CASCADE')
                except Exception:
                    pass
            await database.disconnect()

    @pytest.mark.asyncio
    async def test_enqueue_persists_tenant_id_from_contextvar(self, db):
        @task(name="tests.tenant_capture")
        async def capture() -> dict[str, Any]:
            return {"tenant": tenant_id_var.get()}

        token = tenant_id_var.set("acme")
        try:
            queued = await capture.enqueue(db=db)
        finally:
            tenant_id_var.reset(token)

        # Persisted task record must carry the enqueuing tenant; before
        # the fix the payload kept only {"args": [], "kwargs": {}}.
        assert queued.tenant_id == "acme"

        stored = await get_task_record(queued.id, db=db)
        assert stored is not None
        assert stored.tenant_id == "acme"

    @pytest.mark.asyncio
    async def test_worker_restores_tenant_context_before_execute(self, db):
        observed: dict[str, Any] = {}

        @task(name="tests.tenant_observe")
        async def observe() -> dict[str, Any]:
            # Worker must restore tenant_id_var to the enqueue-time value
            # before invoking the callable.
            observed["tenant"] = tenant_id_var.get()
            return {"tenant": tenant_id_var.get()}

        token = tenant_id_var.set("globex")
        try:
            queued = await observe.enqueue(db=db)
        finally:
            tenant_id_var.reset(token)

        # Sanity: with the request-time tenant cleared, the worker has
        # to depend on the persisted task record to recover the tenant.
        assert tenant_id_var.get() is None

        worker = TaskWorker(db, retry_delay_seconds=0.0)
        processed = await worker.poll_once()

        assert processed is not None
        assert processed.status == "completed"
        assert observed["tenant"] == "globex"
        assert processed.result == {"tenant": "globex"}

        # And the worker must not leak the tenant back into the
        # surrounding context.
        assert tenant_id_var.get() is None
