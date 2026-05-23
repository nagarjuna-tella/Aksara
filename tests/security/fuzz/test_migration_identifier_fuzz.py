from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from aksara.migrations.operations import (
    CreateTable,
    EnumField,
    JSONField,
    StringField,
    UUIDField,
    _format_jsonb_default,
    _quote_ident,
)

from .conftest import FUZZ_SETTINGS, MALICIOUS_IDENTIFIERS, CaptureConnection


pytestmark = [pytest.mark.security, pytest.mark.fuzz]


@pytest.mark.asyncio
@pytest.mark.parametrize("table_name", MALICIOUS_IDENTIFIERS)
async def test_migration_identifier_fuzz_rejects_or_quotes_unsafe_table_names(table_name):
    connection = CaptureConnection()
    operation = CreateTable(
        name=table_name,
        fields=[("id", UUIDField(primary_key=True)), ("name", StringField())],
    )

    await operation.apply(connection)

    sql = connection.sql[0]
    assert _quote_ident(table_name) in sql
    assert f"CREATE TABLE IF NOT EXISTS {table_name}" not in sql


@pytest.mark.asyncio
@pytest.mark.parametrize("column_name", MALICIOUS_IDENTIFIERS)
async def test_migration_identifier_fuzz_rejects_or_quotes_unsafe_column_names(column_name):
    connection = CaptureConnection()
    operation = CreateTable(
        name="safe_table",
        fields=[("id", UUIDField(primary_key=True)), (column_name, StringField())],
    )

    await operation.apply(connection)

    sql = connection.sql[0]
    assert _quote_ident(column_name) in sql
    assert f"\n    {column_name} " not in sql


@pytest.mark.parametrize("default", ["x'; DROP TABLE users; --", "quote ' inside"])
def test_migration_default_fuzz_escapes_quotes(default):
    sql = StringField(default=default).to_sql()
    escaped = default.replace("'", "''")

    assert f"DEFAULT '{default}'" not in sql
    assert f"DEFAULT '{escaped}'" in sql


def test_migration_json_default_fuzz_escapes_safely():
    payload = {"path": "x'; DROP TABLE users; --", "nested": {"quote": "\""}}
    sql = JSONField(default=payload).to_sql()

    assert _format_jsonb_default(payload) in sql
    assert "::jsonb" in sql


def test_migration_enum_value_fuzz_escapes_safely_if_supported():
    sql = EnumField(
        allowed_values=["safe", "x'; DROP TABLE users; --"],
        default="x'; DROP TABLE users; --",
    ).to_sql()

    assert "DEFAULT 'x''; DROP TABLE users; --'" in sql


@FUZZ_SETTINGS
@given(identifier=st.text(min_size=0, max_size=128))
def test_migration_identifier_fuzz_generated_identifiers_are_quoted(identifier):
    quoted = _quote_ident(identifier)

    assert quoted.startswith('"')
    assert quoted.endswith('"')
    assert '"' + identifier + '"' == quoted or '""' in quoted
