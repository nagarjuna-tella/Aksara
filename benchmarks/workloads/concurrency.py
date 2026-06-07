"""Concurrency behavior workloads."""

from __future__ import annotations

from benchmarks.config import BenchmarkRunConfig
from benchmarks.implementations.base import BenchmarkImplementation
from benchmarks.metrics import BenchmarkResult
from benchmarks.workloads.common import run_concurrent_case


async def run(impl: BenchmarkImplementation, config: BenchmarkRunConfig) -> list[BenchmarkResult]:
    cases = [
        ("concurrent_primary_key_reads", impl.concurrency_pk_read),
        ("concurrent_filtered_reads", impl.concurrency_filtered_read),
        ("concurrent_inserts", impl.concurrency_insert),
        ("concurrent_mixed_read_write", impl.concurrency_mixed_read_write),
        ("concurrent_transactions", impl.concurrency_transaction),
        ("pool_starvation_long_short_mix", impl.concurrency_pool_starvation),
    ]
    results: list[BenchmarkResult] = []
    for level in config.concurrency_levels:
        for name, operation in cases:
            results.append(
                await run_concurrent_case(
                    impl,
                    config,
                    workload="concurrency",
                    benchmark_name=name,
                    operation=operation,
                    concurrency_level=level,
                )
            )
    return results

