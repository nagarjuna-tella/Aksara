"""Relationship-loading workloads."""

from __future__ import annotations

from benchmarks.config import BenchmarkRunConfig
from benchmarks.implementations.base import BenchmarkImplementation
from benchmarks.metrics import BenchmarkResult
from benchmarks.workloads.common import run_case


async def run(impl: BenchmarkImplementation, config: BenchmarkRunConfig) -> list[BenchmarkResult]:
    cases = [
        ("load_one_invoice_with_vendor", impl.load_one_invoice_vendor),
        ("load_one_invoice_with_lines", impl.load_one_invoice_lines),
        ("load_100_invoices_with_vendors", impl.load_100_invoices_vendors),
        ("load_100_invoices_with_lines", impl.load_100_invoices_lines),
        ("load_100_invoices_with_vendors_and_lines", impl.load_100_invoices_vendors_lines),
        ("load_vendor_with_many_invoices", impl.load_vendor_with_invoices),
        ("load_user_with_roles", impl.load_user_with_roles),
    ]
    return [
        await run_case(impl, config, workload="relationships", benchmark_name=name, operation=operation)
        for name, operation in cases
    ]

