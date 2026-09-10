"""Restricted-role PostgreSQL fixture for durable operation tests."""

from __future__ import annotations

import os
import secrets
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio

from aksara.db import Database
from aksara.migrations.executor import discover_internal_migrations, load_migration_module


def _role_dsn(database_url: str, role: str, password: str) -> str:
    parsed = urlsplit(database_url)
    host = parsed.hostname or "localhost"
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parsed.port}" if parsed.port else ""
    return urlunsplit(
        (
            parsed.scheme,
            f"{quote(role)}:{quote(password)}@{host}{port}",
            parsed.path,
            parsed.query,
            parsed.fragment,
        )
    )


def _migration(name: str):
    migrations = dict(discover_internal_migrations())
    return load_migration_module(Path(migrations[name]))


@pytest_asyncio.fixture
async def durable_db() -> AsyncIterator[Database]:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required")

    suffix = uuid4().hex[:10]
    schema = f"aksara_v070_{suffix}"
    role = f"aksara_v070_role_{suffix}"
    password = secrets.token_urlsafe(24)
    admin = await asyncpg.connect(database_url)
    previous_database = Database._instance
    database: Database | None = None
    try:
        escaped_password = password.replace("'", "''")
        await admin.execute(f'CREATE SCHEMA "{schema}"')
        await admin.execute(
            f'''CREATE ROLE "{role}" LOGIN PASSWORD '{escaped_password}' '''
            "NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION"
        )
        await admin.execute(f'ALTER ROLE "{role}" SET search_path TO "{schema}", public')
        await admin.execute(f'SET search_path TO "{schema}", public')
        runtime = _migration("aksara_core_migrations_0001_runtime_tables")()
        durable = _migration("aksara_core_migrations_0002_durable_operations")()
        for operation in (*runtime.operations, *durable.operations):
            await operation.apply(admin)
        await admin.execute(
            """
            CREATE TABLE durable_test_counters (
                id UUID PRIMARY KEY,
                tenant_scope TEXT NOT NULL,
                mutation_counter INTEGER NOT NULL DEFAULT 0
                    CHECK (mutation_counter >= 0)
            );
            ALTER TABLE durable_test_counters ENABLE ROW LEVEL SECURITY;
            ALTER TABLE durable_test_counters FORCE ROW LEVEL SECURITY;
            CREATE POLICY durable_test_counters_tenant_policy
            ON durable_test_counters
            USING (tenant_scope = current_setting('aksara.current_tenant_id', true))
            WITH CHECK (tenant_scope = current_setting('aksara.current_tenant_id', true));
            """
        )
        await admin.execute(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"')
        await admin.execute(
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"'
        )
        await admin.execute(
            f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA "{schema}" TO "{role}"'
        )

        database = Database(_role_dsn(database_url, role, password), min_size=1, max_size=6)
        await database.connect()
        yield database
    finally:
        Database._instance = previous_database
        if database is not None:
            await database.disconnect()
        await admin.execute("SET search_path TO public")
        await admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await admin.execute(f'DROP ROLE IF EXISTS "{role}"')
        await admin.close()
