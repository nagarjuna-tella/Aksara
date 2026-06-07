"""Aksara ORM workload operations."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from aksara.db import atomic
from aksara.migrations import operations as op
from aksara.migrations.executor import ensure_migrations_table, get_applied_migrations, record_migration

from benchmarks.correctness import CorrectnessCheck, require, require_decimal_equal, require_equal
from benchmarks.implementations.aksara_impl.models import (
    BenchInvoice,
    BenchInvoiceLine,
    BenchVendor,
)
from benchmarks.implementations.postgres_common import invoice_integrity
from benchmarks.implementations.sql_workload_mixin import SqlWorkloadMixin


class AksaraOperations(SqlWorkloadMixin):
    """Aksara-specific ORM implementations for the core workload surface."""

    @asynccontextmanager
    async def transaction(self):
        async with atomic(db=self.db):
            yield

    @asynccontextmanager
    async def acquire(self):
        async with self.db.acquire() as conn:
            yield conn

    async def execute(self, sql: str, *args: Any) -> Any:
        return await self.db.execute(sql, *args)

    async def fetch(self, sql: str, *args: Any) -> list[Any]:
        return await self.db.fetch(sql, *args)

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        return await self.db.fetchrow(sql, *args)

    async def fetchval(self, sql: str, *args: Any) -> Any:
        return await self.db.fetchval(sql, *args)

    @staticmethod
    def _vendor_kwargs(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "company_id": row["company_id"],
            "name": row["name"],
            "tax_id": row["tax_id"],
            "email": row["email"],
            "status": row["status"],
            "metadata": row["metadata"],
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
            "metadata": row["metadata"],
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
            "metadata": row["metadata"],
        }

    async def insert_one_vendor(self, iteration: int) -> CorrectnessCheck:
        row = self.dataset.runtime_vendor(self.runtime_namespace, iteration)
        vendor = await BenchVendor.objects.create(**self._vendor_kwargs(row))
        return require(vendor.id == row["id"], "Aksara returned wrong vendor id", name="vendor_inserted")

    async def insert_one_invoice(self, iteration: int) -> CorrectnessCheck:
        invoice, _lines = self.dataset.runtime_invoice(self.runtime_namespace, 100_000 + iteration, line_count=1)
        created = await BenchInvoice.objects.create(**self._invoice_kwargs(invoice))
        return CorrectnessCheck.combine(
            "invoice_inserted",
            [
                require(created.id == invoice["id"], "Aksara returned wrong invoice id"),
                require_decimal_equal(created.total, invoice["total"]),
            ],
        )

    async def insert_invoice_with_lines_transaction(self, iteration: int, line_count: int = 10) -> CorrectnessCheck:
        invoice, lines = self.dataset.runtime_invoice(self.runtime_namespace, 200_000 + iteration, line_count=line_count)
        async with atomic(db=self.db):
            await BenchInvoice.objects.create(**self._invoice_kwargs(invoice))
            await BenchInvoiceLine.objects.bulk_create(
                [BenchInvoiceLine(**self._line_kwargs(line)) for line in lines],
                batch_size=max(line_count, 1),
            )
        return await invoice_integrity(self.fetchrow, self.fetch, self.table_prefix, invoice["id"])

    async def get_invoice_by_pk(self, iteration: int) -> CorrectnessCheck:
        invoice_id = self.dataset.sample_invoice_id(iteration)
        invoice = await BenchInvoice.objects.get(id=invoice_id)
        return require(invoice.id == invoice_id, "Aksara primary-key lookup returned wrong invoice", name="pk_lookup")

    async def get_invoice_by_number(self, iteration: int) -> CorrectnessCheck:
        number = self.dataset.sample_invoice_number(iteration)
        invoice = await BenchInvoice.objects.get(invoice_number=number)
        return require_equal(invoice.invoice_number, number, name="indexed_lookup")

    async def update_invoice_status(self, iteration: int) -> CorrectnessCheck:
        invoice_id = self.dataset.sample_invoice_id(iteration)
        status = "sent" if iteration % 2 else "paid"
        await BenchInvoice.objects.filter(id=invoice_id).update(status=status)
        invoice = await BenchInvoice.objects.get(id=invoice_id)
        return require_equal(invoice.status, status, name="status_updated")

    async def delete_draft_invoice(self, iteration: int) -> CorrectnessCheck:
        invoice, _lines = self.dataset.runtime_invoice(self.runtime_namespace, 300_000 + iteration, line_count=1)
        created = await BenchInvoice.objects.create(**self._invoice_kwargs(invoice))
        await created.delete()
        exists = await BenchInvoice.objects.filter(id=invoice["id"]).exists()
        return require(exists is False, "Aksara draft invoice still exists after delete", name="draft_deleted")

    async def bulk_insert_vendors(self, iteration: int, count: int) -> CorrectnessCheck:
        rows = [self.dataset.runtime_vendor(self.runtime_namespace, 400_000 + iteration * count + i) for i in range(count)]
        await BenchVendor.objects.bulk_create([BenchVendor(**self._vendor_kwargs(row)) for row in rows], batch_size=count)
        observed = await BenchVendor.objects.filter(id__in=[row["id"] for row in rows]).count()
        return require_equal(observed, count, name="bulk_vendors_inserted")

    async def bulk_insert_invoices(self, iteration: int, count: int) -> CorrectnessCheck:
        rows = [
            self.dataset.runtime_invoice(self.runtime_namespace, 500_000 + iteration * count + i, line_count=1)[0]
            for i in range(count)
        ]
        await BenchInvoice.objects.bulk_create([BenchInvoice(**self._invoice_kwargs(row)) for row in rows], batch_size=count)
        observed = await BenchInvoice.objects.filter(id__in=[row["id"] for row in rows]).count()
        return require_equal(observed, count, name="bulk_invoices_inserted")

    async def bulk_insert_invoice_lines(self, iteration: int, count: int) -> CorrectnessCheck:
        invoice, lines = self.dataset.runtime_invoice(self.runtime_namespace, 600_000 + iteration, line_count=count)
        await BenchInvoice.objects.create(**self._invoice_kwargs(invoice))
        await BenchInvoiceLine.objects.bulk_create(
            [BenchInvoiceLine(**self._line_kwargs(line)) for line in lines],
            batch_size=max(count, 1),
        )
        return await invoice_integrity(self.fetchrow, self.fetch, self.table_prefix, invoice["id"])

    async def bulk_update_invoice_status(self, iteration: int) -> CorrectnessCheck:
        count = min(self.config.bulk_size, 100)
        rows = [
            self.dataset.runtime_invoice(self.runtime_namespace, 700_000 + iteration * count + i, line_count=1)[0]
            for i in range(count)
        ]
        await BenchInvoice.objects.bulk_create([BenchInvoice(**self._invoice_kwargs(row)) for row in rows], batch_size=count)
        ids = [row["id"] for row in rows]
        await BenchInvoice.objects.filter(id__in=ids).update(status="sent")
        observed = await BenchInvoice.objects.filter(id__in=ids, status="sent").count()
        return require_equal(observed, count, name="bulk_status_updated")

    async def bulk_delete_drafts(self, iteration: int, count: int) -> CorrectnessCheck:
        rows = [
            self.dataset.runtime_invoice(self.runtime_namespace, 800_000 + iteration * count + i, line_count=1)[0]
            for i in range(count)
        ]
        await BenchInvoice.objects.bulk_create([BenchInvoice(**self._invoice_kwargs(row)) for row in rows], batch_size=count)
        ids = [row["id"] for row in rows]
        await BenchInvoice.objects.filter(id__in=ids, status="draft").delete()
        observed = await BenchInvoice.objects.filter(id__in=ids).count()
        return require_equal(observed, 0, name="bulk_drafts_deleted")

    async def read_filter_status(self, iteration: int) -> CorrectnessCheck:
        invoices = await BenchInvoice.objects.filter(status="paid").limit(50).all()
        return require(invoices and all(invoice.status == "paid" for invoice in invoices), "Aksara status filter returned wrong rows")

    async def read_filter_vendor(self, iteration: int) -> CorrectnessCheck:
        vendor_id = self.dataset.sample_vendor_id(iteration)
        invoices = await BenchInvoice.objects.filter(vendor_id=vendor_id).limit(50).all()
        return require(invoices and all(invoice.vendor_id == vendor_id for invoice in invoices), "Aksara vendor filter returned wrong rows")

    async def read_count(self, iteration: int) -> CorrectnessCheck:
        observed = await BenchInvoice.objects.filter(status="paid").count()
        return require(observed > 0, "Aksara count returned zero paid invoices", name="count_paid")

    async def read_exists(self, iteration: int) -> CorrectnessCheck:
        exists = await BenchInvoice.objects.filter(invoice_number=self.dataset.sample_invoice_number(iteration)).exists()
        return require(exists is True, "Aksara exists did not find seeded invoice", name="exists_invoice")

    async def load_one_invoice_vendor(self, iteration: int) -> CorrectnessCheck:
        invoice_id = self.dataset.sample_invoice_id(iteration)
        invoice = (await BenchInvoice.objects.select_related("vendor").filter(id=invoice_id).all())[0]
        vendor = invoice.get_related("vendor")
        return require(vendor is not None and vendor.id == invoice.vendor_id, "Aksara select_related returned wrong vendor")

    async def load_one_invoice_lines(self, iteration: int) -> CorrectnessCheck:
        invoice_id = self.dataset.sample_invoice_id(iteration)
        lines = await BenchInvoiceLine.objects.filter(invoice_id=invoice_id).all()
        return require_equal(len(lines), self.config.profile.invoice_lines_per_invoice, name="one_invoice_lines")

    async def load_100_invoices_vendors(self, iteration: int) -> CorrectnessCheck:
        invoices = await BenchInvoice.objects.select_related("vendor").order_by("issued_at", "id").limit(100).all()
        return require(
            len(invoices) == min(100, self.config.profile.invoices)
            and all(invoice.get_related("vendor") is not None for invoice in invoices),
            "Aksara failed loading 100 invoices with vendors",
        )

    async def load_100_invoices_lines(self, iteration: int) -> CorrectnessCheck:
        invoices = await BenchInvoice.objects.order_by("issued_at", "id").limit(100).all()
        ids = [invoice.id for invoice in invoices]
        lines = await BenchInvoiceLine.objects.filter(invoice_id__in=ids).all()
        return require_equal(len(lines), len(ids) * self.config.profile.invoice_lines_per_invoice, name="hundred_invoice_lines")

    async def load_100_invoices_vendors_lines(self, iteration: int) -> CorrectnessCheck:
        return CorrectnessCheck.combine(
            "hundred_invoices_vendors_lines",
            [
                await self.load_100_invoices_vendors(iteration),
                await self.load_100_invoices_lines(iteration),
            ],
        )

    async def migration_reliability(self, iteration: int) -> CorrectnessCheck:
        table = f"{self.table_prefix}migration_probe_{iteration}"
        child = f"{self.table_prefix}migration_child_{iteration}"
        migration_name = f"bench_migration_reliability_{iteration}"

        await ensure_migrations_table(self.db)
        await self.db.execute(f'DROP TABLE IF EXISTS "{child}" CASCADE')
        await self.db.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
        await self.db.execute("DELETE FROM aksara_migrations WHERE name = $1", migration_name)

        create = op.CreateTable(
            name=table,
            fields=[
                ("id", op.UUIDField(primary_key=True)),
                ("invoice_number", op.StringField(max_length=80, unique=True)),
                ("total", op.DecimalField(max_digits=14, decimal_places=2, default=0)),
            ],
        )
        await create.apply(self.db)
        await self.db.execute(
            f'INSERT INTO "{table}" (invoice_number, total) VALUES ($1, $2)',
            "MIG-0001",
            "42.50",
        )

        await op.AddField(table=table, name="notes", field=op.TextField(nullable=True)).apply(self.db)
        await op.AddField(
            table=table,
            name="status",
            field=op.StringField(max_length=24, nullable=False, default="draft"),
        ).apply(self.db)
        await op.AddIndex(op.IndexOp(name=f"{table}_status_idx", table=table, columns=["status"])).apply(self.db)
        await op.CreateTable(
            name=child,
            fields=[
                ("id", op.UUIDField(primary_key=True)),
                ("probe_id", op.ForeignKeyField(to_table=table, nullable=False, on_delete="CASCADE")),
            ],
        ).apply(self.db)
        await op.RenameField(table=table, old_name="notes", new_name="internal_notes").apply(self.db)
        await op.RemoveField(table=table, name="internal_notes").apply(self.db)
        await op.RunSQL(sql=f'ALTER TABLE "{table}" ADD COLUMN raw_marker INTEGER DEFAULT 1').apply(self.db)

        duplicate_failed = False
        try:
            await op.AddField(table=table, name="status", field=op.StringField(max_length=24)).apply(self.db)
        except Exception:
            duplicate_failed = True

        await create.apply(self.db)
        await record_migration(self.db, migration_name, checksum="bench")
        applied = await get_applied_migrations(self.db)

        row = await self.db.fetchrow(f'SELECT invoice_number, status, raw_marker FROM "{table}" WHERE invoice_number = $1', "MIG-0001")
        checks = [
            require(row is not None, "migration probe row disappeared", name="migration_row_exists"),
            require(row is not None and row["status"] == "draft", "non-null default was not backfilled", name="migration_default"),
            require(row is not None and row["raw_marker"] == 1, "raw SQL migration did not apply", name="migration_raw_sql"),
            require(duplicate_failed, "failed migration did not raise clearly", name="migration_failure_detected"),
            require(migration_name in applied, "migration history record missing", name="migration_history"),
        ]
        return CorrectnessCheck.combine("migration_reliability", checks)
