"""Shared SQL workload implementations used for raw baselines and fallbacks."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

from benchmarks.correctness import (
    CorrectnessCheck,
    require,
    require_decimal_equal,
    require_equal,
    validate_no_duplicate_page_rows,
)
from benchmarks.datasets import BASE_TIME, stable_uuid
from benchmarks.implementations.postgres_common import (
    assert_connection_usable,
    assert_reference_aggregate,
    insert_dicts,
    invoice_integrity,
    quote_ident,
)


class SqlWorkloadMixin:
    """Operational workload methods expressed as parameterized PostgreSQL."""

    def qtable(self, logical_name: str) -> str:
        return quote_ident(self.table(logical_name))

    async def _insert_vendor_row(self, row: dict[str, Any]) -> None:
        await self.execute(
            f"""
            INSERT INTO {self.qtable('vendors')}
                (id, company_id, name, tax_id, email, status, metadata, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9)
            """,
            row["id"],
            row["company_id"],
            row["name"],
            row["tax_id"],
            row["email"],
            row["status"],
            self._json(row["metadata"]),
            BASE_TIME,
            BASE_TIME,
        )

    async def _insert_invoice_row(self, row: dict[str, Any]) -> None:
        await self.execute(
            f"""
            INSERT INTO {self.qtable('invoices')}
                (id, company_id, vendor_id, invoice_number, status, issued_at, due_at,
                 subtotal, tax, total, currency, metadata, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb, $13, $14)
            """,
            row["id"],
            row["company_id"],
            row["vendor_id"],
            row["invoice_number"],
            row["status"],
            row["issued_at"],
            row["due_at"],
            row["subtotal"],
            row["tax"],
            row["total"],
            row["currency"],
            self._json(row["metadata"]),
            BASE_TIME,
            BASE_TIME,
        )

    async def _insert_line_row(self, row: dict[str, Any]) -> None:
        await self.execute(
            f"""
            INSERT INTO {self.qtable('invoice_lines')}
                (id, invoice_id, line_no, description, quantity, unit_price, amount, metadata, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10)
            """,
            row["id"],
            row["invoice_id"],
            row["line_no"],
            row["description"],
            row["quantity"],
            row["unit_price"],
            row["amount"],
            self._json(row["metadata"]),
            BASE_TIME,
            BASE_TIME,
        )

    def _json(self, value: Any) -> str:
        import json

        return json.dumps(value, allow_nan=False)

    async def insert_one_vendor(self, iteration: int) -> CorrectnessCheck:
        row = self.dataset.runtime_vendor(self.runtime_namespace, iteration)
        await self._insert_vendor_row(row)
        exists = await self.fetchval(f"SELECT EXISTS (SELECT 1 FROM {self.qtable('vendors')} WHERE id = $1)", row["id"])
        return require(exists is True, "inserted vendor was not found", name="vendor_inserted")

    async def insert_one_invoice(self, iteration: int) -> CorrectnessCheck:
        invoice, _lines = self.dataset.runtime_invoice(self.runtime_namespace, 100_000 + iteration, line_count=1)
        await self._insert_invoice_row(invoice)
        row = await self.fetchrow(f"SELECT id, total FROM {self.qtable('invoices')} WHERE id = $1", invoice["id"])
        return CorrectnessCheck.combine(
            "invoice_inserted",
            [
                require(row is not None, "inserted invoice was not found"),
                require_decimal_equal(row["total"], invoice["total"]) if row else CorrectnessCheck.fail("total", "missing row"),
            ],
        )

    async def insert_invoice_with_lines_transaction(self, iteration: int, line_count: int = 10) -> CorrectnessCheck:
        invoice, lines = self.dataset.runtime_invoice(self.runtime_namespace, 200_000 + iteration, line_count=line_count)
        async with self.transaction():
            await self._insert_invoice_row(invoice)
            for line in lines:
                await self._insert_line_row(line)
        return await invoice_integrity(self.fetchrow, self.fetch, self.table_prefix, invoice["id"])

    async def get_invoice_by_pk(self, iteration: int) -> CorrectnessCheck:
        invoice_id = self.dataset.sample_invoice_id(iteration)
        row = await self.fetchrow(f"SELECT id FROM {self.qtable('invoices')} WHERE id = $1", invoice_id)
        return require(row is not None and row["id"] == invoice_id, "primary-key lookup returned wrong invoice", name="pk_lookup")

    async def get_invoice_by_number(self, iteration: int) -> CorrectnessCheck:
        number = self.dataset.sample_invoice_number(iteration)
        row = await self.fetchrow(f"SELECT invoice_number FROM {self.qtable('invoices')} WHERE invoice_number = $1", number)
        return require(row is not None and row["invoice_number"] == number, "indexed lookup returned wrong invoice", name="indexed_lookup")

    async def update_invoice_status(self, iteration: int) -> CorrectnessCheck:
        invoice_id = self.dataset.sample_invoice_id(iteration)
        status = "sent" if iteration % 2 else "paid"
        await self.execute(f"UPDATE {self.qtable('invoices')} SET status = $1, updated_at = NOW() WHERE id = $2", status, invoice_id)
        observed = await self.fetchval(f"SELECT status FROM {self.qtable('invoices')} WHERE id = $1", invoice_id)
        return require_equal(observed, status, name="status_updated")

    async def delete_draft_invoice(self, iteration: int) -> CorrectnessCheck:
        invoice, _lines = self.dataset.runtime_invoice(self.runtime_namespace, 300_000 + iteration, line_count=1)
        await self._insert_invoice_row(invoice)
        await self.execute(f"DELETE FROM {self.qtable('invoices')} WHERE id = $1 AND status = 'draft'", invoice["id"])
        exists = await self.fetchval(f"SELECT EXISTS (SELECT 1 FROM {self.qtable('invoices')} WHERE id = $1)", invoice["id"])
        return require(exists is False, "draft invoice still exists after delete", name="draft_deleted")

    async def bulk_insert_vendors(self, iteration: int, count: int) -> CorrectnessCheck:
        rows = [self.dataset.runtime_vendor(self.runtime_namespace, 400_000 + iteration * count + i) for i in range(count)]
        async with self.acquire() as conn:
            await insert_dicts(
                conn,
                self.table("vendors"),
                ("id", "company_id", "name", "tax_id", "email", "status", "metadata"),
                rows,
            )
        observed = await self.fetchval(
            f"SELECT COUNT(*) FROM {self.qtable('vendors')} WHERE id = ANY($1::uuid[])",
            [row["id"] for row in rows],
        )
        return require_equal(observed, count, name="bulk_vendors_inserted")

    async def bulk_insert_invoices(self, iteration: int, count: int) -> CorrectnessCheck:
        rows = [
            self.dataset.runtime_invoice(self.runtime_namespace, 500_000 + iteration * count + i, line_count=1)[0]
            for i in range(count)
        ]
        async with self.acquire() as conn:
            await insert_dicts(
                conn,
                self.table("invoices"),
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
                ),
                rows,
            )
        observed = await self.fetchval(
            f"SELECT COUNT(*) FROM {self.qtable('invoices')} WHERE id = ANY($1::uuid[])",
            [row["id"] for row in rows],
        )
        return require_equal(observed, count, name="bulk_invoices_inserted")

    async def bulk_insert_invoice_lines(self, iteration: int, count: int) -> CorrectnessCheck:
        invoice, lines = self.dataset.runtime_invoice(self.runtime_namespace, 600_000 + iteration, line_count=count)
        await self._insert_invoice_row(invoice)
        async with self.acquire() as conn:
            await insert_dicts(
                conn,
                self.table("invoice_lines"),
                ("id", "invoice_id", "line_no", "description", "quantity", "unit_price", "amount", "metadata"),
                lines,
            )
        return await invoice_integrity(self.fetchrow, self.fetch, self.table_prefix, invoice["id"])

    async def bulk_update_invoice_status(self, iteration: int) -> CorrectnessCheck:
        count = min(self.config.bulk_size, 100)
        rows = [
            self.dataset.runtime_invoice(self.runtime_namespace, 700_000 + iteration * count + i, line_count=1)[0]
            for i in range(count)
        ]
        async with self.acquire() as conn:
            await insert_dicts(
                conn,
                self.table("invoices"),
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
                ),
                rows,
            )
        row_ids = [row["id"] for row in rows]
        await self.execute(f"UPDATE {self.qtable('invoices')} SET status = 'sent' WHERE id = ANY($1::uuid[])", row_ids)
        observed = await self.fetchval(
            f"SELECT COUNT(*) FROM {self.qtable('invoices')} WHERE id = ANY($1::uuid[]) AND status = 'sent'",
            row_ids,
        )
        return require_equal(observed, count, name="bulk_status_updated")

    async def bulk_delete_drafts(self, iteration: int, count: int) -> CorrectnessCheck:
        rows = [
            self.dataset.runtime_invoice(self.runtime_namespace, 800_000 + iteration * count + i, line_count=1)[0]
            for i in range(count)
        ]
        async with self.acquire() as conn:
            await insert_dicts(
                conn,
                self.table("invoices"),
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
                ),
                rows,
            )
        row_ids = [row["id"] for row in rows]
        await self.execute(f"DELETE FROM {self.qtable('invoices')} WHERE id = ANY($1::uuid[]) AND status = 'draft'", row_ids)
        observed = await self.fetchval(
            f"SELECT COUNT(*) FROM {self.qtable('invoices')} WHERE id = ANY($1::uuid[])",
            row_ids,
        )
        return require_equal(observed, 0, name="bulk_drafts_deleted")

    async def read_primary_key_lookup(self, iteration: int) -> CorrectnessCheck:
        return await self.get_invoice_by_pk(iteration)

    async def read_indexed_lookup(self, iteration: int) -> CorrectnessCheck:
        return await self.get_invoice_by_number(iteration)

    async def read_filter_status(self, iteration: int) -> CorrectnessCheck:
        rows = await self.fetch(f"SELECT id, status FROM {self.qtable('invoices')} WHERE status = $1 LIMIT 50", "paid")
        return require(rows and all(row["status"] == "paid" for row in rows), "status filter returned wrong rows", name="status_filter")

    async def read_filter_vendor(self, iteration: int) -> CorrectnessCheck:
        vendor_id = self.dataset.sample_vendor_id(iteration)
        rows = await self.fetch(f"SELECT id, vendor_id FROM {self.qtable('invoices')} WHERE vendor_id = $1 LIMIT 50", vendor_id)
        return require(rows and all(row["vendor_id"] == vendor_id for row in rows), "vendor filter returned wrong rows", name="vendor_filter")

    async def read_date_range(self, iteration: int) -> CorrectnessCheck:
        start = self.dataset.issued_at(0)
        end = start.replace(month=3)
        rows = await self.fetch(
            f"SELECT id, issued_at FROM {self.qtable('invoices')} WHERE issued_at >= $1 AND issued_at < $2 LIMIT 50",
            start,
            end,
        )
        return require(rows and all(start <= row["issued_at"] < end for row in rows), "date range returned wrong rows", name="date_range")

    async def read_multi_filter(self, iteration: int) -> CorrectnessCheck:
        sample_index = 2
        vendor_id = self.dataset.sample_vendor_id(sample_index)
        start = self.dataset.issued_at(0)
        end = start.replace(year=start.year + 2)
        rows = await self.fetch(
            f"""
            SELECT id, vendor_id, status, issued_at
            FROM {self.qtable('invoices')}
            WHERE vendor_id = $1 AND status = $2 AND issued_at >= $3 AND issued_at < $4
            LIMIT 50
            """,
            vendor_id,
            "paid",
            start,
            end,
        )
        return require(
            all(row["vendor_id"] == vendor_id and row["status"] == "paid" and start <= row["issued_at"] < end for row in rows),
            "multi-filter returned wrong rows",
            name="multi_filter",
        )

    async def read_ordered_pagination(self, iteration: int) -> CorrectnessCheck:
        limit = 50
        page1 = await self.fetch(
            f"SELECT id, issued_at FROM {self.qtable('invoices')} ORDER BY issued_at, id LIMIT $1 OFFSET 0",
            limit,
        )
        page2 = await self.fetch(
            f"SELECT id, issued_at FROM {self.qtable('invoices')} ORDER BY issued_at, id LIMIT $1 OFFSET $2",
            limit,
            limit,
        )
        ids = [row["id"] for row in page1 + page2]
        ordered = all((page1 + page2)[i]["issued_at"] <= (page1 + page2)[i + 1]["issued_at"] for i in range(len(page1 + page2) - 1))
        return CorrectnessCheck.combine(
            "ordered_pagination",
            [
                require(len(page1) == limit and len(page2) == limit, "pagination returned wrong page size"),
                validate_no_duplicate_page_rows(ids),
                require(ordered, "pagination order is unstable"),
            ],
        )

    async def read_count(self, iteration: int) -> CorrectnessCheck:
        observed = await self.fetchval(f"SELECT COUNT(*) FROM {self.qtable('invoices')} WHERE status = $1", "paid")
        return require(observed > 0, "count query returned zero paid invoices", name="count_paid")

    async def read_exists(self, iteration: int) -> CorrectnessCheck:
        exists = await self.fetchval(
            f"SELECT EXISTS (SELECT 1 FROM {self.qtable('invoices')} WHERE invoice_number = $1)",
            self.dataset.sample_invoice_number(iteration),
        )
        return require(exists is True, "exists query did not find seeded invoice", name="exists_invoice")

    async def read_aggregate_total_by_vendor(self, iteration: int) -> CorrectnessCheck:
        vendor_id = self.dataset.sample_vendor_id(iteration)
        observed = await self.fetchval(
            f"SELECT COALESCE(SUM(total), 0) FROM {self.qtable('invoices')} WHERE vendor_id = $1",
            vendor_id,
        )
        return await assert_reference_aggregate(self.fetchval, self.table_prefix, vendor_id, observed or Decimal("0"))

    async def read_grouped_monthly_total_by_status(self, iteration: int) -> CorrectnessCheck:
        rows = await self.fetch(
            f"""
            SELECT date_trunc('month', issued_at) AS month, status, SUM(total) AS total
            FROM {self.qtable('invoices')}
            GROUP BY month, status
            ORDER BY month, status
            LIMIT 50
            """
        )
        return require(rows and all(row["total"] is not None for row in rows), "monthly grouped aggregation failed", name="monthly_grouped")

    async def read_join_invoice_vendor(self, iteration: int) -> CorrectnessCheck:
        invoice_id = self.dataset.sample_invoice_id(iteration)
        row = await self.fetchrow(
            f"""
            SELECT i.id AS invoice_id, v.id AS vendor_id, v.name AS vendor_name
            FROM {self.qtable('invoices')} i
            JOIN {self.qtable('vendors')} v ON v.id = i.vendor_id
            WHERE i.id = $1
            """,
            invoice_id,
        )
        return require(row is not None and row["vendor_name"], "invoice/vendor join returned no vendor", name="join_invoice_vendor")

    async def read_nested_invoice_vendor_lines(self, iteration: int) -> CorrectnessCheck:
        invoice_id = self.dataset.sample_invoice_id(iteration)
        invoice = await self.fetchrow(
            f"""
            SELECT i.*, v.name AS vendor_name
            FROM {self.qtable('invoices')} i
            JOIN {self.qtable('vendors')} v ON v.id = i.vendor_id
            WHERE i.id = $1
            """,
            invoice_id,
        )
        lines = await self.fetch(f"SELECT * FROM {self.qtable('invoice_lines')} WHERE invoice_id = $1 ORDER BY line_no", invoice_id)
        return CorrectnessCheck.combine(
            "nested_invoice_vendor_lines",
            [
                require(invoice is not None and invoice["vendor_name"], "nested load missing invoice/vendor"),
                require_equal(len(lines), self.config.profile.invoice_lines_per_invoice, name="nested_line_count"),
            ],
        )

    async def load_one_invoice_vendor(self, iteration: int) -> CorrectnessCheck:
        return await self.read_join_invoice_vendor(iteration)

    async def load_one_invoice_lines(self, iteration: int) -> CorrectnessCheck:
        invoice_id = self.dataset.sample_invoice_id(iteration)
        lines = await self.fetch(f"SELECT * FROM {self.qtable('invoice_lines')} WHERE invoice_id = $1", invoice_id)
        return require_equal(len(lines), self.config.profile.invoice_lines_per_invoice, name="one_invoice_lines")

    async def load_100_invoices_vendors(self, iteration: int) -> CorrectnessCheck:
        rows = await self.fetch(
            f"""
            SELECT i.id, v.name
            FROM {self.qtable('invoices')} i
            JOIN {self.qtable('vendors')} v ON v.id = i.vendor_id
            ORDER BY i.issued_at, i.id
            LIMIT 100
            """
        )
        return require(len(rows) == min(100, self.config.profile.invoices) and all(row["name"] for row in rows), "failed to load 100 invoices with vendors")

    async def load_100_invoices_lines(self, iteration: int) -> CorrectnessCheck:
        invoices = await self.fetch(f"SELECT id FROM {self.qtable('invoices')} ORDER BY issued_at, id LIMIT 100")
        invoice_ids = [row["id"] for row in invoices]
        lines = await self.fetch(f"SELECT invoice_id FROM {self.qtable('invoice_lines')} WHERE invoice_id = ANY($1::uuid[])", invoice_ids)
        return require_equal(len(lines), len(invoice_ids) * self.config.profile.invoice_lines_per_invoice, name="hundred_invoice_lines")

    async def load_100_invoices_vendors_lines(self, iteration: int) -> CorrectnessCheck:
        vendor_check = await self.load_100_invoices_vendors(iteration)
        lines_check = await self.load_100_invoices_lines(iteration)
        return CorrectnessCheck.combine("hundred_invoices_vendors_lines", [vendor_check, lines_check])

    async def load_vendor_with_invoices(self, iteration: int) -> CorrectnessCheck:
        vendor_id = self.dataset.sample_vendor_id(iteration)
        rows = await self.fetch(f"SELECT id FROM {self.qtable('invoices')} WHERE vendor_id = $1 LIMIT 100", vendor_id)
        return require(rows, "vendor had no invoices", name="vendor_invoices")

    async def load_user_with_roles(self, iteration: int) -> CorrectnessCheck:
        user_id = self.dataset.id_for("user", iteration % self.dataset.user_count)
        rows = await self.fetch(
            f"""
            SELECT u.id AS user_id, r.name AS role_name
            FROM {self.qtable('users')} u
            JOIN {self.qtable('user_roles')} ur ON ur.user_id = u.id
            JOIN {self.qtable('roles')} r ON r.id = ur.role_id
            WHERE u.id = $1
            """,
            user_id,
        )
        return require(len(rows) >= 1 and all(row["role_name"] for row in rows), "user roles load failed", name="user_roles")

    async def transaction_commit_all_rows(self, iteration: int) -> CorrectnessCheck:
        invoice, lines = self.dataset.runtime_invoice(self.runtime_namespace, 900_000 + iteration, line_count=3)
        async with self.transaction():
            await self._insert_invoice_row(invoice)
            for line in lines:
                await self._insert_line_row(line)
        return await invoice_integrity(self.fetchrow, self.fetch, self.table_prefix, invoice["id"])

    async def transaction_rollback_on_exception(self, iteration: int) -> CorrectnessCheck:
        invoice, lines = self.dataset.runtime_invoice(self.runtime_namespace, 1_000_000 + iteration, line_count=3)
        try:
            async with self.transaction():
                await self._insert_invoice_row(invoice)
                await self._insert_line_row(lines[0])
                raise RuntimeError("intentional rollback")
        except RuntimeError:
            pass
        exists = await self.fetchval(f"SELECT EXISTS (SELECT 1 FROM {self.qtable('invoices')} WHERE id = $1)", invoice["id"])
        return require(exists is False, "rollback partially committed invoice", name="rollback_clean")

    async def transaction_duplicate_unique_error(self, iteration: int) -> CorrectnessCheck:
        row = self.dataset.runtime_vendor(self.runtime_namespace, 1_100_000 + iteration)
        await self._insert_vendor_row(row)
        try:
            await self._insert_vendor_row(row)
        except Exception:
            usable = await assert_connection_usable(self.fetchval)
            count = await self.fetchval(f"SELECT COUNT(*) FROM {self.qtable('vendors')} WHERE tax_id = $1", row["tax_id"])
            return CorrectnessCheck.combine(
                "duplicate_unique_error",
                [usable, require_equal(count, 1, name="duplicate_not_duplicated")],
            )
        return CorrectnessCheck.fail("duplicate_unique_error", "duplicate unique insert did not raise")

    async def transaction_fk_violation_error(self, iteration: int) -> CorrectnessCheck:
        invoice, _lines = self.dataset.runtime_invoice(self.runtime_namespace, 1_200_000 + iteration, line_count=1)
        invoice["vendor_id"] = stable_uuid(f"{self.name}:missing-vendor:{iteration}")
        try:
            await self._insert_invoice_row(invoice)
        except Exception:
            return await assert_connection_usable(self.fetchval)
        return CorrectnessCheck.fail("fk_violation_error", "FK violation did not raise")

    async def transaction_concurrent_update_same_row(self, iteration: int) -> CorrectnessCheck:
        invoice, _lines = self.dataset.runtime_invoice(self.runtime_namespace, 1_300_000 + iteration, line_count=1)
        await self._insert_invoice_row(invoice)

        async def update_status(status: str) -> None:
            async with self.transaction():
                await self.fetchrow(f"SELECT id FROM {self.qtable('invoices')} WHERE id = $1 FOR UPDATE", invoice["id"])
                await self.execute(f"UPDATE {self.qtable('invoices')} SET status = $1 WHERE id = $2", status, invoice["id"])

        await asyncio.gather(update_status("sent"), update_status("paid"))
        final_status = await self.fetchval(f"SELECT status FROM {self.qtable('invoices')} WHERE id = $1", invoice["id"])
        return require(final_status in {"sent", "paid"}, "concurrent update left invalid status", name="concurrent_update_valid")

    async def transaction_rollback_connection_usable(self, iteration: int) -> CorrectnessCheck:
        rollback = await self.transaction_rollback_on_exception(1_400_000 + iteration)
        usable = await assert_connection_usable(self.fetchval)
        return CorrectnessCheck.combine("rollback_connection_usable", [rollback, usable])

    async def transaction_repeated_failures_no_leak(self, iteration: int) -> CorrectnessCheck:
        failures = 0
        for offset in range(5):
            check = await self.transaction_fk_violation_error(1_500_000 + iteration * 10 + offset)
            if check.passed:
                failures += 1
        usable = await assert_connection_usable(self.fetchval)
        return CorrectnessCheck.combine(
            "repeated_failures_no_leak",
            [require_equal(failures, 5, name="failures_captured"), usable],
        )

    async def concurrency_pool_starvation(self, iteration: int) -> CorrectnessCheck:
        if iteration % 10 == 0:
            await self.fetchval("SELECT pg_sleep(0.02)")
        return await self.read_exists(iteration)
