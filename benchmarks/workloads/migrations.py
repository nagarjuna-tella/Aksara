"""Migration execution reliability workloads."""

from __future__ import annotations

from benchmarks.config import BenchmarkRunConfig
from benchmarks.implementations.base import BenchmarkImplementation
from benchmarks.metrics import BenchmarkResult
from benchmarks.workloads.common import run_case


async def run(impl: BenchmarkImplementation, config: BenchmarkRunConfig) -> list[BenchmarkResult]:
    return [
        await run_case(
            impl,
            config,
            workload="migrations",
            benchmark_name="aksara_migration_execution_reliability",
            operation=impl.migration_reliability,
            iterations=1,
            warmup_iterations=0,
        )
    ]

