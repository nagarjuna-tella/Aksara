"""Read/query performance workloads."""

from __future__ import annotations

from benchmarks.config import BenchmarkRunConfig
from benchmarks.implementations.base import BenchmarkImplementation
from benchmarks.metrics import BenchmarkResult
from benchmarks.workloads.common import run_case


async def run(impl: BenchmarkImplementation, config: BenchmarkRunConfig) -> list[BenchmarkResult]:
    cases = [
        ("primary_key_lookup", impl.read_primary_key_lookup),
        ("indexed_lookup", impl.read_indexed_lookup),
        ("filter_by_status", impl.read_filter_status),
        ("filter_by_vendor", impl.read_filter_vendor),
        ("date_range_filter", impl.read_date_range),
        ("vendor_status_date_filter", impl.read_multi_filter),
        ("ordered_pagination", impl.read_ordered_pagination),
        ("count_query", impl.read_count),
        ("exists_query", impl.read_exists),
        ("aggregate_total_by_vendor", impl.read_aggregate_total_by_vendor),
        ("grouped_monthly_total_by_status", impl.read_grouped_monthly_total_by_status),
        ("join_invoice_vendor", impl.read_join_invoice_vendor),
        ("nested_invoice_vendor_lines", impl.read_nested_invoice_vendor_lines),
    ]
    return [
        await run_case(impl, config, workload="read_queries", benchmark_name=name, operation=operation)
        for name, operation in cases
    ]

