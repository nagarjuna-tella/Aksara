"""PostgreSQL contracts for the rollback-scoped test database helper."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio

from aksara import Model, fields
from aksara.db import Database, atomic
from aksara.registry import ModelRegistry
from aksara.testing import test_database as database_context

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"), reason="DATABASE_URL is required"
)


def _scoped_dsn(database_url: str, schema: str) -> str:
    parsed = urlsplit(database_url)
    query = dict(parse_qsl(parsed.query))
    query["search_path"] = f"{schema},public"
    return urlunsplit(parsed._replace(query=urlencode(query)))


@dataclass
class SchemaState:
    dsn: str
    observer: asyncpg.Connection


@pytest_asyncio.fixture
async def test_schema() -> AsyncIterator[SchemaState]:
    database_url = os.environ["DATABASE_URL"]
    schema = f"aksara_v072_testing_{uuid4().hex[:12]}"
    admin = await asyncpg.connect(database_url)
    observer: asyncpg.Connection | None = None
    try:
        await admin.execute(f'CREATE SCHEMA "{schema}"')
        dsn = _scoped_dsn(database_url, schema)
        observer = await asyncpg.connect(dsn)
        await observer.execute(
            "CREATE TABLE helper_rows (name TEXT PRIMARY KEY, value INTEGER NOT NULL)"
        )
        yield SchemaState(dsn=dsn, observer=observer)
    finally:
        ModelRegistry.clear()
        if observer is not None:
            await observer.close()
        await admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await admin.close()


def _assert_pool_closed(database: Database) -> None:
    with pytest.raises(RuntimeError, match="not connected"):
        _ = database.pool


@pytest.mark.asyncio
async def test_successful_context_rolls_back_and_closes_owned_pool(test_schema):
    helper: Database
    async with database_context(test_schema.dsn, cleanup=True) as helper:
        await helper.execute(
            "INSERT INTO helper_rows (name, value) VALUES ($1, $2)",
            "success",
            1,
        )
        assert await helper.fetchval(
            "SELECT value FROM helper_rows WHERE name = 'success'"
        ) == 1
        assert await test_schema.observer.fetchval(
            "SELECT count(*) FROM helper_rows WHERE name = 'success'"
        ) == 0

    assert helper is not None
    _assert_pool_closed(helper)
    assert await test_schema.observer.fetchval(
        "SELECT count(*) FROM helper_rows WHERE name = 'success'"
    ) == 0


@pytest.mark.asyncio
async def test_exception_rolls_back_and_closes_owned_pool(test_schema):
    helper = None
    with pytest.raises(RuntimeError, match="deliberate"):
        async with database_context(test_schema.dsn, cleanup=True) as helper:
            await helper.execute(
                "INSERT INTO helper_rows (name, value) VALUES ('exception', 2)"
            )
            raise RuntimeError("deliberate")

    assert helper is not None
    _assert_pool_closed(helper)
    assert await test_schema.observer.fetchval(
        "SELECT count(*) FROM helper_rows WHERE name = 'exception'"
    ) == 0


@pytest.mark.asyncio
async def test_cancellation_rolls_back_and_closes_owned_pool(test_schema):
    started = asyncio.Event()
    release = asyncio.Event()
    captured: list[Database] = []

    async def cancelled_work() -> None:
        async with database_context(test_schema.dsn, cleanup=True) as helper:
            captured.append(helper)
            await helper.execute(
                "INSERT INTO helper_rows (name, value) VALUES ('cancelled', 3)"
            )
            started.set()
            await release.wait()

    running = asyncio.create_task(cancelled_work())
    await asyncio.wait_for(started.wait(), timeout=2)
    assert await test_schema.observer.fetchval(
        "SELECT count(*) FROM helper_rows WHERE name = 'cancelled'"
    ) == 0
    running.cancel()
    with pytest.raises(asyncio.CancelledError):
        await running

    _assert_pool_closed(captured[0])
    assert await test_schema.observer.fetchval(
        "SELECT count(*) FROM helper_rows WHERE name = 'cancelled'"
    ) == 0


@pytest.mark.asyncio
async def test_nested_atomic_and_model_writes_share_outer_rollback(test_schema):
    class HelperRecord(Model):
        __tablename__ = "helper_models"

        name = fields.String()

    await test_schema.observer.execute(HelperRecord.get_create_table_sql())
    helper: Database
    async with database_context(test_schema.dsn, cleanup=True) as helper:
        async with atomic(db=helper):
            await helper.execute(
                "INSERT INTO helper_rows (name, value) VALUES ('nested', 4)"
            )
        saved = await HelperRecord.objects.create(name="model")
        assert saved.id is not None
        assert await HelperRecord.objects.count() == 1
        assert await test_schema.observer.fetchval(
            "SELECT count(*) FROM helper_models"
        ) == 0

    assert helper is not None
    _assert_pool_closed(helper)
    assert await test_schema.observer.fetchval("SELECT count(*) FROM helper_rows") == 0
    assert await test_schema.observer.fetchval("SELECT count(*) FROM helper_models") == 0


@pytest.mark.asyncio
async def test_cleanup_false_commits_but_still_closes_owned_pool(test_schema):
    helper: Database
    async with database_context(test_schema.dsn, cleanup=False) as helper:
        await helper.execute(
            "INSERT INTO helper_rows (name, value) VALUES ('committed', 5)"
        )

    assert helper is not None
    _assert_pool_closed(helper)
    assert await test_schema.observer.fetchval(
        "SELECT value FROM helper_rows WHERE name = 'committed'"
    ) == 5


@pytest.mark.asyncio
async def test_helper_can_be_reused_without_leaking_state_or_singleton(test_schema):
    original = Database.get_instance() if Database._instance is not None else None
    helpers = []
    for _ in range(2):
        async with database_context(test_schema.dsn, cleanup=True) as helper:
            helpers.append(helper)
            await helper.execute(
                "INSERT INTO helper_rows (name, value) VALUES ('repeat', 6)"
            )
        assert await test_schema.observer.fetchval(
            "SELECT count(*) FROM helper_rows WHERE name = 'repeat'"
        ) == 0

    assert all(helper._pool is None for helper in helpers)
    assert Database._instance is original
