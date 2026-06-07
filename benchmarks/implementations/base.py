"""Base classes shared by benchmark implementation adapters."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from benchmarks.config import BenchmarkRunConfig
from benchmarks.correctness import CorrectnessCheck
from benchmarks.datasets import InvoiceDataset


class UnsupportedOperation(RuntimeError):
    """Raised when an implementation intentionally does not support a benchmark."""


class BenchmarkImplementation:
    """Default adapter surface. Concrete implementations override supported methods."""

    name = "base"
    table_prefix = "bench_base_"

    def __init__(self, config: BenchmarkRunConfig):
        self.config = config
        self.dataset = InvoiceDataset(config.profile, seed=config.seed)
        self.postgres_version: str | None = None
        self._runtime_namespace: ContextVar[str] = ContextVar(
            f"{self.name}_benchmark_runtime_namespace",
            default=self.name,
        )

    def table(self, logical_name: str) -> str:
        return f"{self.table_prefix}{logical_name}"

    @property
    def runtime_namespace(self) -> str:
        return self._runtime_namespace.get()

    @contextmanager
    def scoped_runtime_namespace(self, namespace: str):
        token = self._runtime_namespace.set(namespace)
        try:
            yield
        finally:
            self._runtime_namespace.reset(token)

    async def setup(self) -> None:
        raise NotImplementedError

    async def teardown(self) -> None:
        raise NotImplementedError

    async def execute(self, sql: str, *args: Any) -> Any:
        raise NotImplementedError

    async def fetch(self, sql: str, *args: Any) -> list[Any]:
        raise NotImplementedError

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        raise NotImplementedError

    async def fetchval(self, sql: str, *args: Any) -> Any:
        raise NotImplementedError

    def unsupported(self, name: str) -> None:
        raise UnsupportedOperation(f"{self.name} does not support {name}")

    async def insert_one_vendor(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("insert_one_vendor")

    async def insert_one_invoice(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("insert_one_invoice")

    async def insert_invoice_with_lines_transaction(self, iteration: int, line_count: int = 10) -> CorrectnessCheck:
        self.unsupported("insert_invoice_with_lines_transaction")

    async def get_invoice_by_pk(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("get_invoice_by_pk")

    async def get_invoice_by_number(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("get_invoice_by_number")

    async def update_invoice_status(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("update_invoice_status")

    async def delete_draft_invoice(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("delete_draft_invoice")

    async def bulk_insert_vendors(self, iteration: int, count: int) -> CorrectnessCheck:
        self.unsupported("bulk_insert_vendors")

    async def bulk_insert_invoices(self, iteration: int, count: int) -> CorrectnessCheck:
        self.unsupported("bulk_insert_invoices")

    async def bulk_insert_invoice_lines(self, iteration: int, count: int) -> CorrectnessCheck:
        self.unsupported("bulk_insert_invoice_lines")

    async def bulk_update_invoice_status(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("bulk_update_invoice_status")

    async def bulk_delete_drafts(self, iteration: int, count: int) -> CorrectnessCheck:
        self.unsupported("bulk_delete_drafts")

    async def read_primary_key_lookup(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("read_primary_key_lookup")

    async def read_indexed_lookup(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("read_indexed_lookup")

    async def read_filter_status(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("read_filter_status")

    async def read_filter_vendor(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("read_filter_vendor")

    async def read_date_range(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("read_date_range")

    async def read_multi_filter(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("read_multi_filter")

    async def read_ordered_pagination(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("read_ordered_pagination")

    async def read_count(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("read_count")

    async def read_exists(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("read_exists")

    async def read_aggregate_total_by_vendor(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("read_aggregate_total_by_vendor")

    async def read_grouped_monthly_total_by_status(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("read_grouped_monthly_total_by_status")

    async def read_join_invoice_vendor(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("read_join_invoice_vendor")

    async def read_nested_invoice_vendor_lines(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("read_nested_invoice_vendor_lines")

    async def load_one_invoice_vendor(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("load_one_invoice_vendor")

    async def load_one_invoice_lines(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("load_one_invoice_lines")

    async def load_100_invoices_vendors(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("load_100_invoices_vendors")

    async def load_100_invoices_lines(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("load_100_invoices_lines")

    async def load_100_invoices_vendors_lines(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("load_100_invoices_vendors_lines")

    async def load_vendor_with_invoices(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("load_vendor_with_invoices")

    async def load_user_with_roles(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("load_user_with_roles")

    async def transaction_commit_all_rows(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("transaction_commit_all_rows")

    async def transaction_rollback_on_exception(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("transaction_rollback_on_exception")

    async def transaction_duplicate_unique_error(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("transaction_duplicate_unique_error")

    async def transaction_fk_violation_error(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("transaction_fk_violation_error")

    async def transaction_concurrent_update_same_row(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("transaction_concurrent_update_same_row")

    async def transaction_rollback_connection_usable(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("transaction_rollback_connection_usable")

    async def transaction_repeated_failures_no_leak(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("transaction_repeated_failures_no_leak")

    async def concurrency_pk_read(self, iteration: int) -> CorrectnessCheck:
        return await self.read_primary_key_lookup(iteration)

    async def concurrency_filtered_read(self, iteration: int) -> CorrectnessCheck:
        return await self.read_filter_status(iteration)

    async def concurrency_insert(self, iteration: int) -> CorrectnessCheck:
        return await self.insert_one_vendor(iteration)

    async def concurrency_mixed_read_write(self, iteration: int) -> CorrectnessCheck:
        if iteration % 2:
            return await self.insert_one_vendor(1_000_000 + iteration)
        return await self.read_indexed_lookup(iteration)

    async def concurrency_transaction(self, iteration: int) -> CorrectnessCheck:
        return await self.transaction_commit_all_rows(1_000_000 + iteration)

    async def concurrency_pool_starvation(self, iteration: int) -> CorrectnessCheck:
        return await self.read_primary_key_lookup(iteration)

    async def migration_reliability(self, iteration: int) -> CorrectnessCheck:
        self.unsupported("migration_reliability")

    async def soak_read_once(self, iteration: int) -> CorrectnessCheck:
        return await self.read_primary_key_lookup(iteration)

    async def soak_mixed_once(self, iteration: int) -> CorrectnessCheck:
        return await self.concurrency_mixed_read_write(iteration)

    async def soak_failed_transaction_once(self, iteration: int) -> CorrectnessCheck:
        return await self.transaction_rollback_connection_usable(iteration)

    async def soak_connection_cycle_once(self, iteration: int) -> CorrectnessCheck:
        return await self.read_exists(iteration)
