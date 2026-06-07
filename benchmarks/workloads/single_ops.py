"""Single-operation latency workloads."""

from __future__ import annotations

from benchmarks.config import BenchmarkRunConfig
from benchmarks.implementations.base import BenchmarkImplementation
from benchmarks.metrics import BenchmarkResult
from benchmarks.workloads.common import run_case


async def run(impl: BenchmarkImplementation, config: BenchmarkRunConfig) -> list[BenchmarkResult]:
    cases = [
        ("insert_one_vendor", impl.insert_one_vendor),
        ("insert_one_invoice", impl.insert_one_invoice),
        ("insert_invoice_with_10_lines_transaction", impl.insert_invoice_with_lines_transaction),
        ("get_invoice_by_primary_key", impl.get_invoice_by_pk),
        ("get_invoice_by_indexed_number", impl.get_invoice_by_number),
        ("update_invoice_status", impl.update_invoice_status),
        ("delete_draft_invoice", impl.delete_draft_invoice),
    ]
    return [
        await run_case(impl, config, workload="single_ops", benchmark_name=name, operation=operation)
        for name, operation in cases
    ]

