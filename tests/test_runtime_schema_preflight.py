"""Production-role regressions for migrated framework runtime tables."""

from unittest.mock import AsyncMock

import pytest

from aksara.contenttypes import ensure_content_types_table
from aksara.contrib.auth.session import _ensure_sessions_table
from aksara.migrations.executor import discover_internal_migrations
from aksara.tasks import ensure_cron_state_table, ensure_tasks_table


@pytest.mark.asyncio
async def test_session_preflight_skips_ddl_for_current_schema():
    db = AsyncMock()
    db.fetchval.return_value = True

    await _ensure_sessions_table(db)

    db.fetchval.assert_awaited_once()
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_content_type_preflight_skips_ddl_for_current_schema():
    db = AsyncMock()
    db.fetchval.return_value = True

    await ensure_content_types_table(db)

    db.fetchval.assert_awaited_once()
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_task_preflight_skips_and_caches_ddl_for_current_schema():
    db = AsyncMock()
    db.fetchval.return_value = True

    await ensure_tasks_table(db)
    await ensure_tasks_table(db)

    db.fetchval.assert_awaited_once()
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_cron_preflight_skips_and_caches_ddl_for_current_schema():
    db = AsyncMock()
    db.fetchval.return_value = True

    await ensure_cron_state_table(db)
    await ensure_cron_state_table(db)

    db.fetchval.assert_awaited_once()
    db.execute.assert_not_awaited()


def test_runtime_table_migration_is_discovered():
    names = {name for name, _ in discover_internal_migrations()}
    assert "aksara_core_migrations_0001_runtime_tables" in names
