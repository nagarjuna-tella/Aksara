"""Metrics and result models for ORM benchmarks."""

from __future__ import annotations

import math
import platform
import resource
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable


def percentile(values: Iterable[float], pct: float) -> float:
    """Return an interpolated percentile for a finite numeric sample."""

    data = sorted(float(v) for v in values)
    if not data:
        return 0.0
    if len(data) == 1:
        return data[0]
    if pct <= 0:
        return data[0]
    if pct >= 100:
        return data[-1]

    rank = (len(data) - 1) * (pct / 100.0)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return data[int(rank)]
    weight = rank - lower
    return data[lower] * (1 - weight) + data[upper] * weight


def _current_rss_mb() -> float:
    try:
        import psutil
    except Exception:
        psutil = None
    if psutil is not None:
        try:
            return psutil.Process().memory_info().rss / (1024 * 1024)
        except Exception:
            pass

    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system().lower() == "darwin":
        return usage / (1024 * 1024)
    return usage / 1024


@dataclass(frozen=True)
class ResourceSnapshot:
    rss_mb: float
    timestamp: float

    @classmethod
    def capture(cls) -> "ResourceSnapshot":
        return cls(rss_mb=_current_rss_mb(), timestamp=time.perf_counter())


@dataclass
class BenchmarkResult:
    """A normalized benchmark result row."""

    benchmark_name: str
    implementation_name: str
    dataset_profile: str
    workload: str
    concurrency_level: int
    iterations: int
    warmup_iterations: int
    success_count: int
    failure_count: int
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    mean_latency_ms: float
    stdev_latency_ms: float
    throughput_ops_sec: float
    total_runtime_sec: float
    peak_memory_mb: float | None
    rss_before_mb: float | None
    rss_after_mb: float | None
    connection_peak: int | None
    sql_query_count: int | None
    correctness_passed: bool | None
    error_details: str | None
    postgres_version: str | None
    run_id: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    git_commit: str | None = None
    benchmark_mode: str | None = None
    command_options: dict[str, Any] = field(default_factory=dict)
    status: str = "passed"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    python_version: str = field(default_factory=lambda: sys.version.replace("\n", " "))
    platform_info: str = field(default_factory=platform.platform)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_latencies(
        cls,
        *,
        benchmark_name: str,
        implementation_name: str,
        dataset_profile: str,
        workload: str,
        concurrency_level: int = 1,
        iterations: int,
        warmup_iterations: int,
        latencies_ms: list[float],
        success_count: int,
        failure_count: int,
        total_runtime_sec: float,
        rss_before_mb: float | None = None,
        rss_after_mb: float | None = None,
        connection_peak: int | None = None,
        sql_query_count: int | None = None,
        correctness_passed: bool | None = None,
        error_details: str | None = None,
        postgres_version: str | None = None,
        run_id: str | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
        git_commit: str | None = None,
        benchmark_mode: str | None = None,
        command_options: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> "BenchmarkResult":
        sample = latencies_ms or [0.0]
        throughput = success_count / total_runtime_sec if total_runtime_sec > 0 else 0.0
        status = "passed" if failure_count == 0 and correctness_passed is not False else "failed"
        return cls(
            benchmark_name=benchmark_name,
            implementation_name=implementation_name,
            dataset_profile=dataset_profile,
            workload=workload,
            concurrency_level=concurrency_level,
            iterations=iterations,
            warmup_iterations=warmup_iterations,
            success_count=success_count,
            failure_count=failure_count,
            p50_latency_ms=percentile(sample, 50),
            p95_latency_ms=percentile(sample, 95),
            p99_latency_ms=percentile(sample, 99),
            min_latency_ms=min(sample),
            max_latency_ms=max(sample),
            mean_latency_ms=statistics.fmean(sample),
            stdev_latency_ms=statistics.stdev(sample) if len(sample) > 1 else 0.0,
            throughput_ops_sec=throughput,
            total_runtime_sec=total_runtime_sec,
            peak_memory_mb=max(v for v in (rss_before_mb, rss_after_mb) if v is not None)
            if rss_before_mb is not None or rss_after_mb is not None
            else None,
            rss_before_mb=rss_before_mb,
            rss_after_mb=rss_after_mb,
            connection_peak=connection_peak,
            sql_query_count=sql_query_count,
            correctness_passed=correctness_passed,
            error_details=error_details,
            postgres_version=postgres_version,
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            git_commit=git_commit,
            benchmark_mode=benchmark_mode,
            command_options=command_options or {},
            status=status,
            extra=extra or {},
        )

    @classmethod
    def unsupported(
        cls,
        *,
        benchmark_name: str,
        implementation_name: str,
        dataset_profile: str,
        workload: str,
        reason: str,
        concurrency_level: int = 1,
        postgres_version: str | None = None,
        run_id: str | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
        git_commit: str | None = None,
        benchmark_mode: str | None = None,
        command_options: dict[str, Any] | None = None,
    ) -> "BenchmarkResult":
        return cls(
            benchmark_name=benchmark_name,
            implementation_name=implementation_name,
            dataset_profile=dataset_profile,
            workload=workload,
            concurrency_level=concurrency_level,
            iterations=0,
            warmup_iterations=0,
            success_count=0,
            failure_count=0,
            p50_latency_ms=0.0,
            p95_latency_ms=0.0,
            p99_latency_ms=0.0,
            min_latency_ms=0.0,
            max_latency_ms=0.0,
            mean_latency_ms=0.0,
            stdev_latency_ms=0.0,
            throughput_ops_sec=0.0,
            total_runtime_sec=0.0,
            peak_memory_mb=None,
            rss_before_mb=None,
            rss_after_mb=None,
            connection_peak=None,
            sql_query_count=None,
            correctness_passed=None,
            error_details=reason,
            postgres_version=postgres_version,
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            git_commit=git_commit,
            benchmark_mode=benchmark_mode,
            command_options=command_options or {},
            status="unsupported",
        )

    def apply_run_metadata(
        self,
        *,
        run_id: str | None,
        started_at: str | None,
        completed_at: str | None,
        git_commit: str | None,
        benchmark_mode: str | None,
        command_options: dict[str, Any] | None,
    ) -> None:
        self.run_id = self.run_id or run_id
        self.started_at = self.started_at or started_at
        self.completed_at = completed_at or self.completed_at
        self.git_commit = self.git_commit or git_commit
        self.benchmark_mode = self.benchmark_mode or benchmark_mode
        if not self.command_options and command_options:
            self.command_options = dict(command_options)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "git_commit": self.git_commit,
            "benchmark_mode": self.benchmark_mode,
            "command_options": self.command_options,
            "benchmark_name": self.benchmark_name,
            "implementation_name": self.implementation_name,
            "dataset_profile": self.dataset_profile,
            "workload": self.workload,
            "concurrency_level": self.concurrency_level,
            "iterations": self.iterations,
            "warmup_iterations": self.warmup_iterations,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "p50_latency_ms": self.p50_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "p99_latency_ms": self.p99_latency_ms,
            "min_latency_ms": self.min_latency_ms,
            "max_latency_ms": self.max_latency_ms,
            "mean_latency_ms": self.mean_latency_ms,
            "stdev_latency_ms": self.stdev_latency_ms,
            "throughput_ops_sec": self.throughput_ops_sec,
            "total_runtime_sec": self.total_runtime_sec,
            "peak_memory_mb": self.peak_memory_mb,
            "rss_before_mb": self.rss_before_mb,
            "rss_after_mb": self.rss_after_mb,
            "connection_peak": self.connection_peak,
            "sql_query_count": self.sql_query_count,
            "correctness_passed": self.correctness_passed,
            "error_details": self.error_details,
            "timestamp": self.timestamp,
            "python_version": self.python_version,
            "postgres_version": self.postgres_version,
            "platform_info": self.platform_info,
            "status": self.status,
            "extra": self.extra,
        }


class Timer:
    """Small monotonic timer for measured benchmark operations."""

    def __enter__(self) -> "Timer":
        self.start = time.perf_counter()
        self.end = self.start
        return self

    def __exit__(self, *_args: object) -> None:
        self.end = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        return (self.end - self.start) * 1000
