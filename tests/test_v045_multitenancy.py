"""
Tests for v0.5.45 PostgreSQL RLS multi-tenancy support.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, Mock

import pytest

from aksara import TenantModel, fields
from aksara.db.engine import Database
from aksara.db.session import session_context
from aksara.middleware import tenant_id_var
from aksara.migrations import operations as op
from aksara.migrations.autodetector import detect_changes, operations_to_code
from aksara.db.tenant_context import (
    TENANT_SETTING_NAME,
    build_enable_rls_sql,
    get_tenant_policy_name,
)


class _AcquireContext:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        return None


def _build_database_with_pool(pool) -> Database:
    db = Database.__new__(Database)
    db._pool = pool
    return db


class TestTenantConnectionContext:
    """Tests for tenant-aware connection lifecycle."""

    @pytest.mark.asyncio
    async def test_acquire_applies_and_resets_tenant_setting(self):
        connection = Mock(execute=AsyncMock())
        pool = Mock(acquire=AsyncMock(return_value=connection), release=AsyncMock())
        db = _build_database_with_pool(pool)
        token = tenant_id_var.set("acme")

        try:
            async with db.acquire() as active_connection:
                assert active_connection is connection
        finally:
            tenant_id_var.reset(token)

        pool.release.assert_awaited_once_with(connection)
        assert connection.execute.await_count == 2
        first_call = connection.execute.await_args_list[0]
        second_call = connection.execute.await_args_list[1]
        assert TENANT_SETTING_NAME in first_call.args[0]
        assert first_call.args[1] == "acme"
        assert TENANT_SETTING_NAME in second_call.args[0]

    @pytest.mark.asyncio
    async def test_session_context_applies_and_resets_tenant_setting(self):
        connection = Mock(execute=AsyncMock())
        pool = Mock(acquire=AsyncMock(return_value=connection), release=AsyncMock())
        db = _build_database_with_pool(pool)
        token = tenant_id_var.set("globex")

        try:
            async with session_context(db) as active_connection:
                assert active_connection is connection
        finally:
            tenant_id_var.reset(token)

        pool.acquire.assert_awaited_once()
        pool.release.assert_awaited_once_with(connection)
        assert connection.execute.await_count == 2


class TestTenantMigrationSupport:
    """Tests for tenant-aware migration generation."""

    def test_new_tenant_model_generates_rls_policy_sql(self):
        class Invoice(TenantModel):
            amount = fields.Integer()

            class Meta:
                table_name = "invoices"

        diff, operations = detect_changes([], {"Invoice": Invoice})

        assert diff.has_changes
        assert any(isinstance(operation, op.CreateTable) for operation in operations)
        run_sql_ops = [operation for operation in operations if isinstance(operation, op.RunSQL)]
        assert len(run_sql_ops) == 1
        assert "ENABLE ROW LEVEL SECURITY" in run_sql_ops[0].sql
        assert get_tenant_policy_name("invoices") in run_sql_ops[0].sql

    def test_operations_to_code_preserves_run_sql_for_tenant_models(self):
        sql = build_enable_rls_sql("projects")
        code = operations_to_code([
            op.RunSQL(sql=sql, reverse_sql="DROP POLICY IF EXISTS foo ON projects"),
        ])

        assert "RunSQL" in code
        assert "ENABLE ROW LEVEL SECURITY" in code
        assert "reverse_sql=" in code

    def test_existing_table_becoming_tenant_scoped_generates_add_field_and_rls(self):
        migration = (
            'from aksara.migrations import Migration\n'
            'from aksara.migrations import operations as op\n\n'
            'class Migration(Migration):\n'
            '    dependencies = []\n'
            '    operations = [\n'
            '        op.CreateTable(\n'
            '            name="accounts",\n'
            '            fields=[\n'
            '                ("id", op.UUIDField(primary_key=True)),\n'
            '                ("name", op.StringField(100)),\n'
            '                ("created_at", op.DateTimeField(auto_now_add=True)),\n'
            '                ("updated_at", op.DateTimeField(auto_now=True)),\n'
            '            ],\n'
            '        ),\n'
            '    ]\n'
        )

        class Account(TenantModel):
            name = fields.String(max_length=100)

            class Meta:
                table_name = "accounts"

        with TemporaryDirectory() as temp_dir:
            migration_path = Path(temp_dir) / "0001_initial.py"
            migration_path.write_text(migration)
            diff, operations = detect_changes([("0001_initial", migration_path)], {"Account": Account})

        assert diff.has_changes
        assert any(
            isinstance(operation, op.AddField) and operation.name == "tenant_id"
            for operation in operations
        )
        assert any(
            isinstance(operation, op.RunSQL) and "ENABLE ROW LEVEL SECURITY" in operation.sql
            for operation in operations
        )