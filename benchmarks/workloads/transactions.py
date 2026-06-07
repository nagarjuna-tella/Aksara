"""Transaction correctness workloads."""

from __future__ import annotations

from benchmarks.config import BenchmarkRunConfig
from benchmarks.implementations.base import BenchmarkImplementation
from benchmarks.metrics import BenchmarkResult
from benchmarks.workloads.common import run_case


async def run(impl: BenchmarkImplementation, config: BenchmarkRunConfig) -> list[BenchmarkResult]:
    cases = [
        ("transaction_commits_all_rows", impl.transaction_commit_all_rows),
        ("exception_rolls_back_everything", impl.transaction_rollback_on_exception),
        ("duplicate_unique_error_clean", impl.transaction_duplicate_unique_error),
        ("fk_violation_error_clean", impl.transaction_fk_violation_error),
        ("concurrent_update_same_row", impl.transaction_concurrent_update_same_row),
        ("rollback_leaves_connection_usable", impl.transaction_rollback_connection_usable),
        ("repeated_failed_transactions_no_leak", impl.transaction_repeated_failures_no_leak),
    ]
    return [
        await run_case(impl, config, workload="transactions", benchmark_name=name, operation=operation)
        for name, operation in cases
    ]

