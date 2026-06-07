"""Bulk write workloads."""

from __future__ import annotations

from benchmarks.config import BenchmarkRunConfig
from benchmarks.implementations.base import BenchmarkImplementation
from benchmarks.metrics import BenchmarkResult
from benchmarks.workloads.common import run_case


async def run(impl: BenchmarkImplementation, config: BenchmarkRunConfig) -> list[BenchmarkResult]:
    count = config.bulk_size
    cases = [
        ("bulk_insert_vendors", lambda index: impl.bulk_insert_vendors(index, count)),
        ("bulk_insert_invoices", lambda index: impl.bulk_insert_invoices(index, count)),
        ("bulk_insert_invoice_lines", lambda index: impl.bulk_insert_invoice_lines(index, count)),
        ("bulk_update_invoice_status", impl.bulk_update_invoice_status),
        ("bulk_delete_draft_records", lambda index: impl.bulk_delete_drafts(index, count)),
    ]
    return [
        await run_case(impl, config, workload="bulk_writes", benchmark_name=name, operation=operation)
        for name, operation in cases
    ]

