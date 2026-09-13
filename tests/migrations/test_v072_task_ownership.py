"""Migration coverage for ordinary-task lease ownership."""

from __future__ import annotations

import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import asyncpg
import pytest

from aksara.db import Database
from aksara.migrations.executor import (
    apply_migration,
    apply_migrations,
    build_migration_graph,
    discover_internal_migrations,
)
from aksara.tasks import TaskWorker

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"), reason="DATABASE_URL is required"
)

RUNTIME = "aksara_core_migrations_0001_runtime_tables"
DURABLE = "aksara_core_migrations_0002_durable_operations"
OWNERSHIP = "aksara_core_migrations_0003_task_claim_ownership"


def _scoped_dsn(database_url: str, schema: str) -> str:
    parsed = urlsplit(database_url)
    query = dict(parse_qsl(parsed.query))
    query["search_path"] = f"{schema},public"
    return urlunsplit(parsed._replace(query=urlencode(query)))

def test_task_ownership_migration_is_ordered_after_durable_operations():
    discovered = dict(discover_internal_migrations())
    assert OWNERSHIP in discovered

    graph = build_migration_graph(migrations_list=list(discovered.items()))
    node = graph.get_node("core", OWNERSHIP)
    assert node is not None
    assert ("core", DURABLE) in node.dependencies


@pytest.mark.asyncio
async def test_v071_task_rows_upgrade_without_state_loss(tmp_path):
    database_url = os.environ["DATABASE_URL"]
    connection = await asyncpg.connect(database_url)
    schema = f"aksara_v072_task_upgrade_{uuid4().hex[:12]}"
    database: Database | None = None
    try:
        await connection.execute(f'CREATE SCHEMA "{schema}"')
        await connection.execute(f'SET search_path TO "{schema}", public')
        discovered = dict(discover_internal_migrations())
        for name in (RUNTIME, DURABLE):
            await apply_migration(
                connection,
                name,
                discovered[name],
                verbose=False,
            )

        pending_id = uuid4()
        stale_id = uuid4()
        running_id = uuid4()
        await connection.execute(
            """
            INSERT INTO aksara_tasks (
                id, task_name, payload, status, attempts, locked_at
            ) VALUES
                ($1, 'tests.pending', '{}'::jsonb, 'pending', 0, NULL),
                ($2, 'tests.stale', '{}'::jsonb, 'running', 1,
                    clock_timestamp() - INTERVAL '10 minutes'),
                ($3, 'tests.running', '{}'::jsonb, 'running', 1,
                    clock_timestamp())
            """,
            pending_id,
            stale_id,
            running_id,
        )

        upgraded = await apply_migrations(connection, tmp_path, verbose=False)
        assert upgraded["errors"] == []
        assert OWNERSHIP in upgraded["applied"]

        columns = {
            row["column_name"]
            for row in await connection.fetch(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = $1 AND table_name = 'aksara_tasks'
                """,
                schema,
            )
        }
        assert {"locked_by", "claim_token", "lock_expires_at"} <= columns
        rows = await connection.fetch(
            """
            SELECT id, status, attempts, locked_at, locked_by,
                   claim_token, lock_expires_at
            FROM aksara_tasks ORDER BY task_name
            """
        )
        assert {row["id"] for row in rows} == {pending_id, stale_id, running_id}
        assert all(row["locked_by"] is None for row in rows)
        assert all(row["claim_token"] is None for row in rows)
        assert all(row["lock_expires_at"] is None for row in rows)

        database = Database(_scoped_dsn(database_url, schema), min_size=1, max_size=4)
        await database.connect()
        worker = TaskWorker(
            database,
            worker_id="post-upgrade-worker",
            stale_lock_timeout_seconds=300,
        )
        assert await worker.recover_stale_locks() == 1
        statuses = {
            row["id"]: row["status"]
            for row in await database.fetch("SELECT id, status FROM aksara_tasks")
        }
        assert statuses[pending_id] == "pending"
        assert statuses[stale_id] == "pending"
        assert statuses[running_id] == "running"

        claim = await worker._claim_task()
        assert claim is not None
        assert claim.id in {pending_id, stale_id}
        assert claim.locked_by == "post-upgrade-worker"
        assert claim.claim_token is not None
        assert claim.lock_expires_at is not None

        replayed = await apply_migrations(connection, tmp_path, verbose=False)
        assert replayed["errors"] == []
        assert replayed["applied"] == []
        assert OWNERSHIP in replayed["skipped"]
    finally:
        if database is not None:
            await database.disconnect()
        await connection.execute("SET search_path TO public")
        await connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await connection.close()


@pytest.mark.asyncio
async def test_fresh_internal_migration_chain_has_task_lease_index(tmp_path):
    connection = await asyncpg.connect(os.environ["DATABASE_URL"])
    schema = f"aksara_v072_task_fresh_{uuid4().hex[:12]}"
    transaction = connection.transaction()
    await transaction.start()
    try:
        await connection.execute(f'CREATE SCHEMA "{schema}"')
        await connection.execute(f'SET LOCAL search_path TO "{schema}", public')
        applied = await apply_migrations(connection, tmp_path, verbose=False)
        assert applied["errors"] == []
        assert OWNERSHIP in applied["applied"]
        assert await connection.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE schemaname = $1
                  AND tablename = 'aksara_tasks'
                  AND indexname = 'idx_aksara_tasks_running_lease'
            )
            """,
            schema,
        )
    finally:
        await transaction.rollback()
        await connection.close()
