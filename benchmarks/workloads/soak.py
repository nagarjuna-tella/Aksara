"""Opt-in stability and soak workloads."""

from __future__ import annotations

from benchmarks.config import BenchmarkRunConfig
from benchmarks.implementations.base import BenchmarkImplementation
from benchmarks.metrics import BenchmarkResult
from benchmarks.workloads.common import run_soak_case


async def run(impl: BenchmarkImplementation, config: BenchmarkRunConfig) -> list[BenchmarkResult]:
    cases = [
        ("continuous_reads", impl.soak_read_once),
        ("mixed_read_write", impl.soak_mixed_once),
        ("repeated_transaction_failures", impl.soak_failed_transaction_once),
        ("connection_acquire_release_cycles", impl.soak_connection_cycle_once),
    ]
    return [
        await run_soak_case(impl, config, benchmark_name=name, operation=operation)
        for name, operation in cases
    ]

