"""SQLAlchemy async workload operations."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

from benchmarks.correctness import CorrectnessCheck, require, require_decimal_equal, require_equal
from benchmarks.implementations.postgres_common import invoice_integrity
from benchmarks.implementations.sql_workload_mixin import SqlWorkloadMixin
from benchmarks.implementations.sqlalchemy_impl.models import (
    SAInvoice,
    SAInvoiceLine,
    SAUser,
    SAVendor,
)


class SQLAlchemyOperations(SqlWorkloadMixin):
    """SQLAlchemy-specific ORM operations for core benchmark cases."""

    @asynccontextmanager
    async def acquire(self):
        if self.raw_pool is None:
            raise RuntimeError("raw asyncpg pool is not connected")
        async with self.raw_pool.acquire() as conn:
            yield conn

    @asynccontextmanager
    async def transaction(self):
        async with self.acquire() as conn:
            async with conn.transaction():
                yield conn

    async def execute(self, sql: str, *args: Any) -> Any:
        async with self.acquire() as conn:
            return await conn.execute(sql, *args)

    async def fetch(self, sql: str, *args: Any) -> list[Any]:
        async with self.acquire() as conn:
            return await conn.fetch(sql, *args)

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        async with self.acquire() as conn:
            return await conn.fetchrow(sql, *args)

    async def fetchval(self, sql: str, *args: Any) -> Any:
        async with self.acquire() as conn:
            return await conn.fetchval(sql, *args)

    @staticmethod
    def _vendor_kwargs(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "company_id": row["company_id"],
            "name": row["name"],
            "tax_id": row["tax_id"],
            "email": row["email"],
            "status": row["status"],
            "meta": row["metadata"],
        }

    @staticmethod
    def _invoice_kwargs(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "company_id": row["company_id"],
            "vendor_id": row["vendor_id"],
            "invoice_number": row["invoice_number"],
            "status": row["status"],
            "issued_at": row["issued_at"],
            "due_at": row["due_at"],
            "subtotal": row["subtotal"],
            "tax": row["tax"],
            "total": row["total"],
            "currency": row["currency"],
            "meta": row["metadata"],
        }

    @staticmethod
    def _line_kwargs(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "invoice_id": row["invoice_id"],
            "line_no": row["line_no"],
            "description": row["description"],
            "quantity": row["quantity"],
            "unit_price": row["unit_price"],
            "amount": row["amount"],
            "meta": row["metadata"],
        }

    async def insert_one_vendor(self, iteration: int) -> CorrectnessCheck:
        row = self.dataset.runtime_vendor(self.runtime_namespace, iteration)
        async with self.session_maker() as session:
            vendor = SAVendor(**self._vendor_kwargs(row))
            session.add(vendor)
            await session.commit()
        return require(await self.fetchval(f"SELECT EXISTS (SELECT 1 FROM {self.qtable('vendors')} WHERE id = $1)", row["id"]) is True, "SQLAlchemy vendor insert failed")

    async def insert_one_invoice(self, iteration: int) -> CorrectnessCheck:
        invoice, _lines = self.dataset.runtime_invoice(self.runtime_namespace, 100_000 + iteration, line_count=1)
        async with self.session_maker() as session:
            row = SAInvoice(**self._invoice_kwargs(invoice))
            session.add(row)
            await session.commit()
        return require_decimal_equal(
            await self.fetchval(f"SELECT total FROM {self.qtable('invoices')} WHERE id = $1", invoice["id"]),
            invoice["total"],
        )

    async def insert_invoice_with_lines_transaction(self, iteration: int, line_count: int = 10) -> CorrectnessCheck:
        invoice, lines = self.dataset.runtime_invoice(self.runtime_namespace, 200_000 + iteration, line_count=line_count)
        async with self.session_maker() as session:
            async with session.begin():
                session.add(SAInvoice(**self._invoice_kwargs(invoice)))
                session.add_all(SAInvoiceLine(**self._line_kwargs(line)) for line in lines)
        return await invoice_integrity(self.fetchrow, self.fetch, self.table_prefix, invoice["id"])

    async def get_invoice_by_pk(self, iteration: int) -> CorrectnessCheck:
        invoice_id = self.dataset.sample_invoice_id(iteration)
        async with self.session_maker() as session:
            invoice = await session.get(SAInvoice, invoice_id)
        return require(invoice is not None and invoice.id == invoice_id, "SQLAlchemy primary-key lookup failed")

    async def get_invoice_by_number(self, iteration: int) -> CorrectnessCheck:
        number = self.dataset.sample_invoice_number(iteration)
        async with self.session_maker() as session:
            invoice = (await session.execute(select(SAInvoice).where(SAInvoice.invoice_number == number))).scalar_one()
        return require_equal(invoice.invoice_number, number, name="indexed_lookup")

    async def update_invoice_status(self, iteration: int) -> CorrectnessCheck:
        invoice_id = self.dataset.sample_invoice_id(iteration)
        status = "sent" if iteration % 2 else "paid"
        async with self.session_maker() as session:
            await session.execute(update(SAInvoice).where(SAInvoice.id == invoice_id).values(status=status))
            await session.commit()
        observed = await self.fetchval(f"SELECT status FROM {self.qtable('invoices')} WHERE id = $1", invoice_id)
        return require_equal(observed, status, name="status_updated")

    async def delete_draft_invoice(self, iteration: int) -> CorrectnessCheck:
        invoice, _lines = self.dataset.runtime_invoice(self.runtime_namespace, 300_000 + iteration, line_count=1)
        async with self.session_maker() as session:
            row = SAInvoice(**self._invoice_kwargs(invoice))
            session.add(row)
            await session.commit()
            await session.delete(row)
            await session.commit()
        exists = await self.fetchval(f"SELECT EXISTS (SELECT 1 FROM {self.qtable('invoices')} WHERE id = $1)", invoice["id"])
        return require(exists is False, "SQLAlchemy draft invoice still exists after delete")

    async def bulk_insert_vendors(self, iteration: int, count: int) -> CorrectnessCheck:
        rows = [self.dataset.runtime_vendor(self.runtime_namespace, 400_000 + iteration * count + i) for i in range(count)]
        async with self.session_maker() as session:
            await session.execute(insert(SAVendor), [self._vendor_kwargs(row) for row in rows])
            await session.commit()
        observed = await self.fetchval(f"SELECT COUNT(*) FROM {self.qtable('vendors')} WHERE id = ANY($1::uuid[])", [row["id"] for row in rows])
        return require_equal(observed, count, name="bulk_vendors_inserted")

    async def bulk_insert_invoices(self, iteration: int, count: int) -> CorrectnessCheck:
        rows = [self.dataset.runtime_invoice(self.runtime_namespace, 500_000 + iteration * count + i, line_count=1)[0] for i in range(count)]
        async with self.session_maker() as session:
            await session.execute(insert(SAInvoice), [self._invoice_kwargs(row) for row in rows])
            await session.commit()
        observed = await self.fetchval(f"SELECT COUNT(*) FROM {self.qtable('invoices')} WHERE id = ANY($1::uuid[])", [row["id"] for row in rows])
        return require_equal(observed, count, name="bulk_invoices_inserted")

    async def read_filter_status(self, iteration: int) -> CorrectnessCheck:
        async with self.session_maker() as session:
            invoices = (await session.execute(select(SAInvoice).where(SAInvoice.status == "paid").limit(50))).scalars().all()
        return require(invoices and all(invoice.status == "paid" for invoice in invoices), "SQLAlchemy status filter failed")

    async def read_filter_vendor(self, iteration: int) -> CorrectnessCheck:
        vendor_id = self.dataset.sample_vendor_id(iteration)
        async with self.session_maker() as session:
            invoices = (await session.execute(select(SAInvoice).where(SAInvoice.vendor_id == vendor_id).limit(50))).scalars().all()
        return require(invoices and all(invoice.vendor_id == vendor_id for invoice in invoices), "SQLAlchemy vendor filter failed")

    async def read_count(self, iteration: int) -> CorrectnessCheck:
        async with self.session_maker() as session:
            observed = (await session.execute(select(func.count()).select_from(SAInvoice).where(SAInvoice.status == "paid"))).scalar_one()
        return require(observed > 0, "SQLAlchemy count returned zero")

    async def read_exists(self, iteration: int) -> CorrectnessCheck:
        number = self.dataset.sample_invoice_number(iteration)
        async with self.session_maker() as session:
            observed = (await session.execute(select(SAInvoice.id).where(SAInvoice.invoice_number == number).limit(1))).first()
        return require(observed is not None, "SQLAlchemy exists lookup failed")

    async def load_one_invoice_vendor(self, iteration: int) -> CorrectnessCheck:
        invoice_id = self.dataset.sample_invoice_id(iteration)
        async with self.session_maker() as session:
            invoice = (
                await session.execute(
                    select(SAInvoice).options(selectinload(SAInvoice.vendor)).where(SAInvoice.id == invoice_id)
                )
            ).scalar_one()
        return require(invoice.vendor is not None and invoice.vendor.id == invoice.vendor_id, "SQLAlchemy relationship load failed")

    async def load_one_invoice_lines(self, iteration: int) -> CorrectnessCheck:
        invoice_id = self.dataset.sample_invoice_id(iteration)
        async with self.session_maker() as session:
            invoice = (
                await session.execute(
                    select(SAInvoice).options(selectinload(SAInvoice.lines)).where(SAInvoice.id == invoice_id)
                )
            ).scalar_one()
        return require_equal(len(invoice.lines), self.config.profile.invoice_lines_per_invoice, name="one_invoice_lines")

    async def load_100_invoices_vendors(self, iteration: int) -> CorrectnessCheck:
        async with self.session_maker() as session:
            invoices = (
                await session.execute(
                    select(SAInvoice).options(selectinload(SAInvoice.vendor)).order_by(SAInvoice.issued_at, SAInvoice.id).limit(100)
                )
            ).scalars().all()
        return require(all(invoice.vendor is not None for invoice in invoices), "SQLAlchemy 100 invoice vendor load failed")

    async def load_100_invoices_lines(self, iteration: int) -> CorrectnessCheck:
        async with self.session_maker() as session:
            invoices = (
                await session.execute(
                    select(SAInvoice).options(selectinload(SAInvoice.lines)).order_by(SAInvoice.issued_at, SAInvoice.id).limit(100)
                )
            ).scalars().all()
        line_count = sum(len(invoice.lines) for invoice in invoices)
        return require_equal(line_count, len(invoices) * self.config.profile.invoice_lines_per_invoice, name="hundred_invoice_lines")

    async def load_100_invoices_vendors_lines(self, iteration: int) -> CorrectnessCheck:
        return CorrectnessCheck.combine(
            "hundred_invoices_vendors_lines",
            [await self.load_100_invoices_vendors(iteration), await self.load_100_invoices_lines(iteration)],
        )

    async def load_user_with_roles(self, iteration: int) -> CorrectnessCheck:
        user_id = self.dataset.id_for("user", iteration % self.dataset.user_count)
        async with self.session_maker() as session:
            user = (
                await session.execute(select(SAUser).options(selectinload(SAUser.roles)).where(SAUser.id == user_id))
            ).scalar_one()
        return require(user.roles, "SQLAlchemy user roles load failed")

