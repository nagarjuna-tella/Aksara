"""Shared workload execution helpers."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from benchmarks.config import BenchmarkRunConfig
from benchmarks.correctness import CorrectnessCheck
from benchmarks.implementations.base import BenchmarkImplementation, UnsupportedOperation
from benchmarks.metrics import BenchmarkResult, ResourceSnapshot


Operation = Callable[[int], Awaitable[CorrectnessCheck]]


def run_metadata_kwargs(config: BenchmarkRunConfig) -> dict[str, object]:
    return {
        "run_id": config.run_id,
        "started_at": config.started_at,
        "git_commit": config.git_commit,
        "benchmark_mode": config.mode,
        "command_options": config.command_options or {},
    }


def operation_namespace(
    config: BenchmarkRunConfig,
    impl: BenchmarkImplementation,
    workload: str,
    benchmark_name: str,
) -> str:
    run_part = config.run_id or f"seed-{config.seed}"
    return f"{run_part}:{impl.name}:{workload}:{benchmark_name}"


def concurrent_iteration_index(concurrency_level: int, batch: int, offset: int) -> int:
    """Return a deterministic ID-space index unique per concurrency level/task."""

    if concurrency_level <= 0:
        raise ValueError("concurrency_level must be positive")
    if batch < 0 or offset < 0:
        raise ValueError("batch and offset must be non-negative")
    if offset >= concurrency_level:
        raise ValueError("offset must be lower than concurrency_level")
    return concurrency_level * 1_000_000_000 + batch * concurrency_level + offset


async def run_case(
    impl: BenchmarkImplementation,
    config: BenchmarkRunConfig,
    *,
    workload: str,
    benchmark_name: str,
    operation: Operation,
    iterations: int | None = None,
    warmup_iterations: int | None = None,
) -> BenchmarkResult:
    iterations = config.iterations if iterations is None else iterations
    warmups = config.warmup_iterations if warmup_iterations is None else warmup_iterations

    try:
        for index in range(warmups):
            with impl.scoped_runtime_namespace(operation_namespace(config, impl, workload, benchmark_name)):
                await operation(-(index + 1))
    except UnsupportedOperation as exc:
        return BenchmarkResult.unsupported(
            benchmark_name=benchmark_name,
            implementation_name=impl.name,
            dataset_profile=config.profile.name,
            workload=workload,
            reason=str(exc),
            postgres_version=impl.postgres_version,
            **run_metadata_kwargs(config),
        )

    latencies: list[float] = []
    success_count = 0
    failure_count = 0
    errors: list[str] = []
    rss_before = ResourceSnapshot.capture()
    total_start = time.perf_counter()

    for index in range(iterations):
        start = time.perf_counter()
        try:
            with impl.scoped_runtime_namespace(operation_namespace(config, impl, workload, benchmark_name)):
                check = await operation(index)
            if check.passed:
                success_count += 1
            else:
                failure_count += 1
                errors.extend(check.errors or (check.details or "correctness check failed",))
        except UnsupportedOperation as exc:
            return BenchmarkResult.unsupported(
                benchmark_name=benchmark_name,
                implementation_name=impl.name,
                dataset_profile=config.profile.name,
                workload=workload,
                reason=str(exc),
                postgres_version=impl.postgres_version,
                **run_metadata_kwargs(config),
            )
        except Exception as exc:
            failure_count += 1
            errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            latencies.append((time.perf_counter() - start) * 1000)

    total_runtime = time.perf_counter() - total_start
    rss_after = ResourceSnapshot.capture()
    return BenchmarkResult.from_latencies(
        benchmark_name=benchmark_name,
        implementation_name=impl.name,
        dataset_profile=config.profile.name,
        workload=workload,
        iterations=iterations,
        warmup_iterations=warmups,
        latencies_ms=latencies,
        success_count=success_count,
        failure_count=failure_count,
        total_runtime_sec=total_runtime,
        rss_before_mb=rss_before.rss_mb,
        rss_after_mb=rss_after.rss_mb,
        correctness_passed=failure_count == 0,
        error_details="; ".join(errors[:5]) if errors else None,
        postgres_version=impl.postgres_version,
        **run_metadata_kwargs(config),
    )


async def run_concurrent_case(
    impl: BenchmarkImplementation,
    config: BenchmarkRunConfig,
    *,
    workload: str,
    benchmark_name: str,
    operation: Operation,
    concurrency_level: int,
) -> BenchmarkResult:
    latencies: list[float] = []
    success_count = 0
    failure_count = 0
    errors: list[str] = []
    rss_before = ResourceSnapshot.capture()
    total_start = time.perf_counter()

    async def run_one(index: int) -> tuple[float, CorrectnessCheck | Exception]:
        start = time.perf_counter()
        try:
            with impl.scoped_runtime_namespace(operation_namespace(config, impl, workload, benchmark_name)):
                check = await operation(index)
            return (time.perf_counter() - start) * 1000, check
        except Exception as exc:
            return (time.perf_counter() - start) * 1000, exc

    for batch in range(config.iterations):
        results = await asyncio.gather(
            *(
                run_one(concurrent_iteration_index(concurrency_level, batch, offset))
                for offset in range(concurrency_level)
            )
        )
        for latency, outcome in results:
            latencies.append(latency)
            if isinstance(outcome, UnsupportedOperation):
                return BenchmarkResult.unsupported(
                    benchmark_name=benchmark_name,
                    implementation_name=impl.name,
                    dataset_profile=config.profile.name,
                    workload=workload,
                    reason=str(outcome),
                    concurrency_level=concurrency_level,
                    postgres_version=impl.postgres_version,
                    **run_metadata_kwargs(config),
                )
            if isinstance(outcome, Exception):
                failure_count += 1
                errors.append(f"{type(outcome).__name__}: {outcome}")
            elif outcome.passed:
                success_count += 1
            else:
                failure_count += 1
                errors.extend(outcome.errors or (outcome.details or "correctness check failed",))

    total_runtime = time.perf_counter() - total_start
    rss_after = ResourceSnapshot.capture()
    return BenchmarkResult.from_latencies(
        benchmark_name=benchmark_name,
        implementation_name=impl.name,
        dataset_profile=config.profile.name,
        workload=workload,
        concurrency_level=concurrency_level,
        iterations=config.iterations * concurrency_level,
        warmup_iterations=0,
        latencies_ms=latencies,
        success_count=success_count,
        failure_count=failure_count,
        total_runtime_sec=total_runtime,
        rss_before_mb=rss_before.rss_mb,
        rss_after_mb=rss_after.rss_mb,
        correctness_passed=failure_count == 0,
        error_details="; ".join(errors[:5]) if errors else None,
        postgres_version=impl.postgres_version,
        **run_metadata_kwargs(config),
    )


async def run_soak_case(
    impl: BenchmarkImplementation,
    config: BenchmarkRunConfig,
    *,
    benchmark_name: str,
    operation: Operation,
) -> BenchmarkResult:
    latencies: list[float] = []
    success_count = 0
    failure_count = 0
    errors: list[str] = []
    rss_before = ResourceSnapshot.capture()
    total_start = time.perf_counter()
    deadline = total_start + config.duration_seconds
    iteration = 0

    while time.perf_counter() < deadline:
        start = time.perf_counter()
        try:
            with impl.scoped_runtime_namespace(operation_namespace(config, impl, "soak", benchmark_name)):
                check = await operation(iteration)
            if check.passed:
                success_count += 1
            else:
                failure_count += 1
                errors.extend(check.errors or (check.details or "correctness check failed",))
        except UnsupportedOperation as exc:
            return BenchmarkResult.unsupported(
                benchmark_name=benchmark_name,
                implementation_name=impl.name,
                dataset_profile=config.profile.name,
                workload="soak",
                reason=str(exc),
                postgres_version=impl.postgres_version,
                **run_metadata_kwargs(config),
            )
        except Exception as exc:
            failure_count += 1
            errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            latencies.append((time.perf_counter() - start) * 1000)
        iteration += 1

    total_runtime = time.perf_counter() - total_start
    rss_after = ResourceSnapshot.capture()
    leak_warning = ""
    if rss_after.rss_mb - rss_before.rss_mb > 128:
        failure_count += 1
        leak_warning = f"RSS grew by {rss_after.rss_mb - rss_before.rss_mb:.1f} MB"
        errors.append(leak_warning)

    return BenchmarkResult.from_latencies(
        benchmark_name=benchmark_name,
        implementation_name=impl.name,
        dataset_profile=config.profile.name,
        workload="soak",
        iterations=iteration,
        warmup_iterations=0,
        latencies_ms=latencies,
        success_count=success_count,
        failure_count=failure_count,
        total_runtime_sec=total_runtime,
        rss_before_mb=rss_before.rss_mb,
        rss_after_mb=rss_after.rss_mb,
        correctness_passed=failure_count == 0,
        error_details="; ".join(errors[:5]) if errors else None,
        postgres_version=impl.postgres_version,
        **run_metadata_kwargs(config),
        extra={"duration_seconds": config.duration_seconds, "rss_warning": leak_warning},
    )
