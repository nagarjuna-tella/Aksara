"""Production migration coverage for the durable operation substrate."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest

from aksara.migrations.executor import (
    build_migration_graph,
    discover_internal_migrations,
    load_migration_module,
)

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"), reason="DATABASE_URL is required"
)


def _migration(name: str):
    migrations = dict(discover_internal_migrations())
    return load_migration_module(Path(migrations[name]))


def test_durable_migration_is_ordered_after_runtime_tables():
    name = "aksara_core_migrations_0002_durable_operations"
    discovered = dict(discover_internal_migrations())
    assert name in discovered

    graph = build_migration_graph(migrations_list=list(discovered.items()))
    node = graph.get_node("core", name)
    assert node is not None
    assert ("core", "aksara_core_migrations_0001_runtime_tables") in node.dependencies


@pytest.mark.asyncio
async def test_durable_schema_bootstraps_and_reverses_transactionally():
    connection = await asyncpg.connect(os.environ["DATABASE_URL"])
    schema = f"aksara_v070_migration_{uuid4().hex[:12]}"
    transaction = connection.transaction()
    await transaction.start()
    try:
        await connection.execute(f'CREATE SCHEMA "{schema}"')
        await connection.execute(f'SET LOCAL search_path TO "{schema}", public')

        runtime = _migration("aksara_core_migrations_0001_runtime_tables")()
        durable = _migration("aksara_core_migrations_0002_durable_operations")()
        for operation in runtime.operations:
            await operation.apply(connection)
        for operation in durable.operations:
            await operation.apply(connection)

        tables = {
            row["table_name"]
            for row in await connection.fetch(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = $1
                """,
                schema,
            )
        }
        assert {
            "aksara_operations",
            "aksara_operation_commands",
            "aksara_operation_attempts",
            "aksara_operation_idempotency",
            "aksara_operation_approval_decisions",
            "aksara_operation_transitions",
            "aksara_operation_outbox",
            "aksara_operation_effects",
        } <= tables

        task_columns = {
            row["column_name"]
            for row in await connection.fetch(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = $1 AND table_name = 'aksara_tasks'
                """,
                schema,
            )
        }
        assert "operation_id" in task_columns

        rls_tables = {
            row["tablename"]
            for row in await connection.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname = $1 AND rowsecurity",
                schema,
            )
        }
        assert "aksara_operations" in rls_tables
        assert "aksara_operation_attempts" in rls_tables
        assert "aksara_operation_outbox" in rls_tables

        reverse = durable.operations[0].reverse()
        assert reverse is not None
        await connection.execute(reverse.sql)
        assert await connection.fetchval(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = $1 AND table_name = 'aksara_operations'
            """,
            schema,
        ) == 0
    finally:
        await transaction.rollback()
        await connection.close()
