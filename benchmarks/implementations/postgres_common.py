"""PostgreSQL schema and seed helpers shared by implementation adapters."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Iterable

from benchmarks.correctness import CorrectnessCheck, require, require_decimal_equal, validate_invoice_totals
from benchmarks.datasets import BASE_TIME, InvoiceDataset, batched


LOGICAL_TABLES = (
    "companies",
    "vendors",
    "users",
    "roles",
    "user_roles",
    "invoices",
    "invoice_lines",
    "payments",
    "audit_logs",
)
DROP_ORDER = (
    "audit_logs",
    "user_roles",
    "payments",
    "invoice_lines",
    "invoices",
    "vendors",
    "users",
    "roles",
    "companies",
)


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def table(prefix: str, logical_name: str) -> str:
    return f"{prefix}{logical_name}"


def _coerce_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, allow_nan=False)
    return value


async def execute_many(conn: Any, sql: str, rows: Iterable[tuple[Any, ...]]) -> None:
    data = list(rows)
    if not data:
        return
    await conn.executemany(sql, data)


async def drop_prefixed_tables(executor: Any, prefix: str) -> None:
    for logical in DROP_ORDER:
        await executor.execute(f"DROP TABLE IF EXISTS {quote_ident(table(prefix, logical))} CASCADE")


async def create_common_indexes(executor: Any, prefix: str) -> None:
    statements = [
        f"CREATE INDEX IF NOT EXISTS {quote_ident(prefix + 'idx_vendors_company_status')} ON {quote_ident(table(prefix, 'vendors'))} (company_id, status)",
        f"CREATE INDEX IF NOT EXISTS {quote_ident(prefix + 'idx_invoices_vendor')} ON {quote_ident(table(prefix, 'invoices'))} (vendor_id)",
        f"CREATE INDEX IF NOT EXISTS {quote_ident(prefix + 'idx_invoices_status')} ON {quote_ident(table(prefix, 'invoices'))} (status)",
        f"CREATE INDEX IF NOT EXISTS {quote_ident(prefix + 'idx_invoices_issued_at')} ON {quote_ident(table(prefix, 'invoices'))} (issued_at)",
        f"CREATE INDEX IF NOT EXISTS {quote_ident(prefix + 'idx_invoices_vendor_status_date')} ON {quote_ident(table(prefix, 'invoices'))} (vendor_id, status, issued_at)",
        f"CREATE INDEX IF NOT EXISTS {quote_ident(prefix + 'idx_invoice_lines_invoice')} ON {quote_ident(table(prefix, 'invoice_lines'))} (invoice_id)",
        f"CREATE INDEX IF NOT EXISTS {quote_ident(prefix + 'idx_payments_invoice')} ON {quote_ident(table(prefix, 'payments'))} (invoice_id)",
        f"CREATE INDEX IF NOT EXISTS {quote_ident(prefix + 'idx_user_roles_user')} ON {quote_ident(table(prefix, 'user_roles'))} (user_id)",
        f"CREATE INDEX IF NOT EXISTS {quote_ident(prefix + 'idx_audit_logs_entity')} ON {quote_ident(table(prefix, 'audit_logs'))} (entity_type, entity_id)",
    ]
    for statement in statements:
        await executor.execute(statement)


async def insert_dicts(conn: Any, table_name: str, columns: tuple[str, ...], rows: Iterable[dict[str, Any]]) -> None:
    placeholders = ", ".join(f"${idx}" for idx in range(1, len(columns) + 1))
    column_sql = ", ".join(quote_ident(column) for column in columns)
    sql = f"INSERT INTO {quote_ident(table_name)} ({column_sql}) VALUES ({placeholders})"
    await execute_many(
        conn,
        sql,
        (tuple(_coerce_value(row.get(column)) for column in columns) for row in rows),
    )


def with_timestamps(rows: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for row in rows:
        copy = row.copy()
        copy.setdefault("created_at", BASE_TIME)
        copy.setdefault("updated_at", BASE_TIME)
        yield copy


async def seed_dataset(pool: Any, prefix: str, dataset: InvoiceDataset, *, chunk_size: int = 1000) -> None:
    async with pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        for chunk in batched(dataset.companies(), chunk_size):
            await insert_dicts(
                conn,
                table(prefix, "companies"),
                ("id", "name", "external_ref", "metadata", "created_at", "updated_at"),
                with_timestamps(chunk),
            )
        for chunk in batched(dataset.vendors(), chunk_size):
            await insert_dicts(
                conn,
                table(prefix, "vendors"),
                ("id", "company_id", "name", "tax_id", "email", "status", "metadata", "created_at", "updated_at"),
                with_timestamps(chunk),
            )
        for chunk in batched(dataset.users(), chunk_size):
            await insert_dicts(
                conn,
                table(prefix, "users"),
                ("id", "company_id", "email", "name", "is_active", "metadata", "created_at", "updated_at"),
                with_timestamps(chunk),
            )
        for chunk in batched(dataset.roles(), chunk_size):
            await insert_dicts(
                conn,
                table(prefix, "roles"),
                ("id", "name", "description", "created_at", "updated_at"),
                with_timestamps(chunk),
            )
        for chunk in batched(dataset.user_roles(), chunk_size):
            await insert_dicts(
                conn,
                table(prefix, "user_roles"),
                ("id", "user_id", "role_id", "created_at", "updated_at"),
                with_timestamps(chunk),
            )
        for chunk in batched(dataset.invoices(), chunk_size):
            await insert_dicts(
                conn,
                table(prefix, "invoices"),
                (
                    "id",
                    "company_id",
                    "vendor_id",
                    "invoice_number",
                    "status",
                    "issued_at",
                    "due_at",
                    "subtotal",
                    "tax",
                    "total",
                    "currency",
                    "metadata",
                    "created_at",
                    "updated_at",
                ),
                with_timestamps(chunk),
            )
        for chunk in batched(dataset.invoice_lines(), chunk_size):
            await insert_dicts(
                conn,
                table(prefix, "invoice_lines"),
                (
                    "id",
                    "invoice_id",
                    "line_no",
                    "description",
                    "quantity",
                    "unit_price",
                    "amount",
                    "metadata",
                    "created_at",
                    "updated_at",
                ),
                with_timestamps(chunk),
            )
        for chunk in batched(dataset.payments(), chunk_size):
            await insert_dicts(
                conn,
                table(prefix, "payments"),
                ("id", "invoice_id", "amount", "paid_at", "method", "reference", "metadata", "created_at", "updated_at"),
                with_timestamps(chunk),
            )
        for chunk in batched(dataset.audit_logs(), chunk_size):
            await insert_dicts(
                conn,
                table(prefix, "audit_logs"),
                (
                    "id",
                    "company_id",
                    "user_id",
                    "entity_type",
                    "entity_id",
                    "action",
                    "metadata",
                    "created_at",
                    "updated_at",
                ),
                with_timestamps(chunk),
            )


async def count_rows(fetchval: Any, prefix: str, logical_name: str) -> int:
    return int(await fetchval(f"SELECT COUNT(*) FROM {quote_ident(table(prefix, logical_name))}") or 0)


async def invoice_integrity(fetchrow: Any, fetch: Any, prefix: str, invoice_id: Any) -> CorrectnessCheck:
    invoice = await fetchrow(f"SELECT * FROM {quote_ident(table(prefix, 'invoices'))} WHERE id = $1", invoice_id)
    lines = await fetch(f"SELECT * FROM {quote_ident(table(prefix, 'invoice_lines'))} WHERE invoice_id = $1", invoice_id)
    if invoice is None:
        return CorrectnessCheck.fail("invoice_integrity", f"invoice {invoice_id} does not exist")
    return validate_invoice_totals(dict(invoice), [dict(line) for line in lines])


async def assert_reference_aggregate(fetchval: Any, prefix: str, vendor_id: Any, observed: Decimal) -> CorrectnessCheck:
    expected = await fetchval(
        f"SELECT COALESCE(SUM(total), 0) FROM {quote_ident(table(prefix, 'invoices'))} WHERE vendor_id = $1",
        vendor_id,
    )
    return require_decimal_equal(observed, expected or Decimal("0"), name="aggregate_matches_raw_sql")


async def assert_connection_usable(fetchval: Any) -> CorrectnessCheck:
    return require(await fetchval("SELECT 1") == 1, "connection/session is not usable after failure", name="connection_usable")
