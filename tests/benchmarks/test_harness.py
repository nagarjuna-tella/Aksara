from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal

import pytest

from benchmarks.config import (
    BenchmarkRunConfig,
    DatabaseConfig,
    mode_default_profile,
    mode_iteration_defaults,
    parse_concurrency_levels,
    resolve_profile,
)
from benchmarks.correctness import CorrectnessCheck, require_decimal_equal, validate_invoice_totals
from benchmarks.datasets import InvoiceDataset
from benchmarks.implementations.base import UnsupportedOperation
from benchmarks.implementations.sql_workload_mixin import SqlWorkloadMixin
from benchmarks.metrics import BenchmarkResult, percentile
from benchmarks.reporting import render_summary, write_summary_csv
from benchmarks.runner import build_parser, config_from_args
from benchmarks.workloads.common import concurrent_iteration_index, operation_namespace, run_case, run_concurrent_case


def test_percentile_interpolates_sorted_samples():
    values = [5, 1, 3, 2, 4]

    assert percentile(values, 50) == 3
    assert percentile(values, 0) == 1
    assert percentile(values, 100) == 5
    assert percentile(values, 95) == pytest.approx(4.8)


def test_benchmark_result_calculates_latency_summary():
    result = BenchmarkResult.from_latencies(
        benchmark_name="case",
        implementation_name="impl",
        dataset_profile="tiny",
        workload="single_ops",
        iterations=4,
        warmup_iterations=1,
        latencies_ms=[1.0, 2.0, 3.0, 4.0],
        success_count=4,
        failure_count=0,
        total_runtime_sec=0.5,
        correctness_passed=True,
        postgres_version="test",
    )

    assert result.p50_latency_ms == 2.5
    assert result.throughput_ops_sec == 8
    assert result.status == "passed"


def test_config_uses_benchmark_postgres_defaults(monkeypatch):
    for key in (
        "AKSARA_BENCH_DB_HOST",
        "AKSARA_BENCH_DB_PORT",
        "AKSARA_BENCH_DB_NAME",
        "AKSARA_BENCH_DB_USER",
        "AKSARA_BENCH_DB_PASSWORD",
        "AKSARA_BENCH_DB_POOL_SIZE",
    ):
        monkeypatch.delenv(key, raising=False)

    config = DatabaseConfig.from_env()

    assert config.url == "postgresql://postgres:qwertyuiop@localhost:5432/aksara_test"
    assert config.pool_size == 20


def test_concurrency_500_is_opt_in():
    with pytest.raises(ValueError):
        parse_concurrency_levels("1,10,500")

    assert parse_concurrency_levels("1,10,500", allow_500=True) == (1, 10, 500)


def test_large_profile_is_opt_in():
    with pytest.raises(ValueError):
        resolve_profile("large")

    assert resolve_profile("large", allow_large=True).invoices == 1_000_000


def test_dataset_generation_is_deterministic():
    profile = resolve_profile("tiny")
    first = InvoiceDataset(profile, seed=42)
    second = InvoiceDataset(profile, seed=42)

    assert next(first.companies()) == next(second.companies())
    assert next(first.invoices()) == next(second.invoices())
    assert list(first.invoice_lines(start_invoice=0, invoice_count=1)) == list(
        second.invoice_lines(start_invoice=0, invoice_count=1)
    )


def test_invoice_total_correctness_helper_passes_and_fails():
    invoice = {"subtotal": Decimal("30.00"), "tax": Decimal("2.48"), "total": Decimal("32.48")}
    lines = [{"amount": Decimal("10.00")}, {"amount": Decimal("20.00")}]

    assert validate_invoice_totals(invoice, lines).passed is True
    assert require_decimal_equal("1.20", Decimal("1.20")).passed is True

    bad_invoice = {"subtotal": Decimal("31.00"), "tax": Decimal("2.48"), "total": Decimal("33.48")}
    assert validate_invoice_totals(bad_invoice, lines).passed is False


def test_mode_defaults_and_cli_overrides():
    assert mode_iteration_defaults("smoke") == (1, 0)
    assert mode_iteration_defaults("correctness") == (3, 1)
    assert mode_iteration_defaults("performance") == (100, 10)
    assert mode_default_profile("smoke") == "tiny"
    assert mode_default_profile("correctness") == "tiny"
    assert mode_default_profile("performance") == "small"

    parser = build_parser()
    config = config_from_args(parser.parse_args(["--mode", "correctness"]))
    assert config.mode == "correctness"
    assert config.profile.name == "tiny"
    assert config.iterations == 3
    assert config.warmup_iterations == 1
    assert config.run_id
    assert config.command_options["mode"] == "correctness"

    performance_default = config_from_args(parser.parse_args(["--mode", "performance"]))
    assert performance_default.profile.name == "small"

    overridden = config_from_args(
        parser.parse_args(["--mode", "performance", "--profile", "tiny", "--iterations", "7", "--warmup", "2"])
    )
    assert overridden.profile.name == "tiny"
    assert overridden.iterations == 7
    assert overridden.warmup_iterations == 2


def test_soak_mode_defaults_to_soak_workload():
    parser = build_parser()
    config = config_from_args(parser.parse_args(["--mode", "soak"]))

    assert config.workloads == ("soak",)


def test_concurrent_iteration_index_is_deterministic_and_unique():
    first = concurrent_iteration_index(10, 2, 3)
    second = concurrent_iteration_index(10, 2, 3)
    assert first == second

    values = {
        concurrent_iteration_index(level, batch, offset)
        for level in (1, 10, 50)
        for batch in range(3)
        for offset in range(level)
    }
    expected_count = sum(level * 3 for level in (1, 10, 50))
    assert len(values) == expected_count


class FakeImplementation:
    postgres_version = "test-postgres"

    def __init__(self, name="fake"):
        self.name = name
        self.runtime_namespace = name
        self.namespaces = []

    @contextmanager
    def scoped_runtime_namespace(self, namespace):
        previous = self.runtime_namespace
        self.runtime_namespace = namespace
        self.namespaces.append(namespace)
        try:
            yield
        finally:
            self.runtime_namespace = previous


def _run_config(*, iterations=2, warmups=1, run_id="run-123") -> BenchmarkRunConfig:
    return BenchmarkRunConfig(
        database=DatabaseConfig(),
        profile=resolve_profile("tiny"),
        implementations=("fake",),
        workloads=("single_ops",),
        mode="correctness",
        iterations=iterations,
        warmup_iterations=warmups,
        run_id=run_id,
        started_at="2026-05-31T00:00:00+00:00",
        git_commit="abc123",
        command_options={"mode": "correctness"},
    )


@pytest.mark.asyncio
async def test_run_case_excludes_warmups_and_propagates_run_id():
    calls = []
    impl = FakeImplementation()

    async def op(index):
        assert impl.runtime_namespace == "run-123:fake:single_ops:case"
        calls.append(index)
        return CorrectnessCheck.ok("ok")

    result = await run_case(
        impl,
        _run_config(iterations=2, warmups=1),
        workload="single_ops",
        benchmark_name="case",
        operation=op,
    )

    assert calls == [-1, 0, 1]
    assert impl.namespaces == ["run-123:fake:single_ops:case"] * 3
    assert result.success_count == 2
    assert result.iterations == 2
    assert result.warmup_iterations == 1
    assert result.run_id == "run-123"
    assert result.benchmark_mode == "correctness"


@pytest.mark.asyncio
async def test_run_case_failed_correctness_marks_failed():
    async def op(_index):
        return CorrectnessCheck.fail("bad", "wrong result")

    result = await run_case(
        FakeImplementation(),
        _run_config(iterations=1, warmups=0),
        workload="single_ops",
        benchmark_name="case",
        operation=op,
    )

    assert result.status == "failed"
    assert result.correctness_passed is False
    assert "wrong result" in result.error_details


@pytest.mark.asyncio
async def test_run_case_unsupported_result_keeps_run_metadata():
    async def op(_index):
        raise UnsupportedOperation("not available")

    result = await run_case(
        FakeImplementation(),
        _run_config(iterations=1, warmups=0),
        workload="migrations",
        benchmark_name="case",
        operation=op,
    )

    assert result.status == "unsupported"
    assert result.run_id == "run-123"
    assert result.error_details == "not available"


def test_operation_namespace_includes_run_impl_workload_and_benchmark():
    config = _run_config(run_id="run-a")
    namespaces = {
        operation_namespace(config, FakeImplementation(impl), workload, benchmark)
        for impl in ("aksara", "asyncpg")
        for workload in ("single_ops", "concurrency")
        for benchmark in ("insert", "mixed")
    }

    assert len(namespaces) == 8
    assert "run-a:aksara:single_ops:insert" in namespaces
    assert "run-a:asyncpg:concurrency:mixed" in namespaces


@pytest.mark.asyncio
async def test_concurrent_case_uses_unique_task_iteration_ids_and_namespace():
    impl = FakeImplementation("asyncpg")
    seen = []

    async def op(index):
        seen.append((index, impl.runtime_namespace))
        return CorrectnessCheck.ok("ok")

    result = await run_concurrent_case(
        impl,
        _run_config(iterations=2, warmups=0, run_id="run-c"),
        workload="concurrency",
        benchmark_name="mixed",
        operation=op,
        concurrency_level=3,
    )

    assert result.status == "passed"
    assert result.iterations == 6
    assert len({index for index, _namespace in seen}) == 6
    assert {namespace for _index, namespace in seen} == {"run-c:asyncpg:concurrency:mixed"}
    assert min(index for index, _namespace in seen) == 3_000_000_000


class CapturingSqlWorkload(SqlWorkloadMixin):
    name = "fake"
    table_prefix = "bench_fake_"

    def __init__(self):
        self.executed = []

    def table(self, logical_name):
        return f"{self.table_prefix}{logical_name}"

    async def execute(self, sql, *args):
        self.executed.append((sql, args))


@pytest.mark.asyncio
async def test_runtime_sql_inserts_include_not_null_timestamps():
    profile = resolve_profile("tiny")
    dataset = InvoiceDataset(profile, seed=42)
    workload = CapturingSqlWorkload()
    invoice, _lines = dataset.runtime_invoice("fake", 1, line_count=1)

    await workload._insert_invoice_row(invoice)

    sql, args = workload.executed[0]
    assert "created_at, updated_at" in sql
    assert len(args) == 14
    assert args[-1] is not None


def test_reporting_summary_separates_failed_unsupported_and_passed():
    rows = [
        {
            "run_id": "run-1",
            "benchmark_mode": "correctness",
            "started_at": "2026-05-31T00:00:00+00:00",
            "completed_at": "2026-05-31T00:01:00+00:00",
            "implementation_name": "aksara",
            "workload": "transactions",
            "benchmark_name": "rollback",
            "concurrency_level": 1,
            "status": "failed",
            "correctness_passed": False,
            "error_details": "rollback failed",
        },
        {
            "run_id": "run-1",
            "benchmark_mode": "correctness",
            "implementation_name": "asyncpg",
            "workload": "migrations",
            "benchmark_name": "migration",
            "concurrency_level": 1,
            "status": "unsupported",
            "error_details": "not supported",
        },
        {
            "run_id": "run-1",
            "benchmark_mode": "correctness",
            "implementation_name": "aksara",
            "workload": "read_queries",
            "benchmark_name": "pk",
            "concurrency_level": 1,
            "status": "passed",
            "correctness_passed": True,
            "p50_latency_ms": 1.0,
            "p95_latency_ms": 2.0,
            "p99_latency_ms": 3.0,
            "throughput_ops_sec": 10.0,
        },
    ]

    summary = render_summary(rows)

    assert summary.index("### Correctness Failures") < summary.index("### Passed Performance")
    assert "rollback failed" in summary
    assert "not supported" in summary
    assert "| aksara | read_queries | pk | 1 | 1 | 1.00 | 2.00 | 3.00 | 10.00 |" in summary
    passed_section = summary.split("### Passed Performance", 1)[1]
    assert "rollback |" not in passed_section


def test_reporting_summary_latest_failures_duplicates_and_comparisons():
    rows = [
        {
            "run_id": "run-old",
            "benchmark_mode": "correctness",
            "started_at": "2026-05-30T00:00:00+00:00",
            "implementation_name": "aksara",
            "dataset_profile": "tiny",
            "workload": "transactions",
            "benchmark_name": "rollback",
            "concurrency_level": 1,
            "status": "failed",
            "correctness_passed": False,
            "error_details": "rollback failed",
        },
        {
            "run_id": "run-new",
            "benchmark_mode": "smoke",
            "started_at": "2026-05-31T00:01:00+00:00",
            "implementation_name": "sqlalchemy",
            "dataset_profile": "tiny",
            "workload": "setup",
            "benchmark_name": "implementation_setup",
            "concurrency_level": 1,
            "status": "unsupported",
            "error_details": "install benchmark extras",
        },
        {
            "run_id": "run-success",
            "benchmark_mode": "smoke",
            "started_at": "2026-05-31T00:00:00+00:00",
            "completed_at": "2026-05-31T00:01:00+00:00",
            "implementation_name": "aksara",
            "dataset_profile": "tiny",
            "workload": "read_queries",
            "benchmark_name": "pk",
            "concurrency_level": 1,
            "status": "passed",
            "correctness_passed": True,
            "p95_latency_ms": 2.0,
            "p99_latency_ms": 3.0,
            "throughput_ops_sec": 10.0,
        },
        {
            "run_id": "run-success",
            "benchmark_mode": "smoke",
            "started_at": "2026-05-31T00:00:00+00:00",
            "implementation_name": "aksara",
            "dataset_profile": "tiny",
            "workload": "read_queries",
            "benchmark_name": "pk",
            "concurrency_level": 1,
            "status": "passed",
            "correctness_passed": True,
            "p95_latency_ms": 2.0,
            "p99_latency_ms": 3.0,
            "throughput_ops_sec": 10.0,
        },
        {
            "run_id": "run-success",
            "benchmark_mode": "smoke",
            "started_at": "2026-05-31T00:00:00+00:00",
            "implementation_name": "asyncpg",
            "dataset_profile": "tiny",
            "workload": "read_queries",
            "benchmark_name": "pk",
            "concurrency_level": 1,
            "status": "passed",
            "correctness_passed": True,
            "p95_latency_ms": 1.0,
            "p99_latency_ms": 2.0,
            "throughput_ops_sec": 20.0,
        },
        {
            "run_id": "run-success",
            "benchmark_mode": "smoke",
            "started_at": "2026-05-31T00:00:00+00:00",
            "implementation_name": "sqlalchemy",
            "dataset_profile": "tiny",
            "workload": "read_queries",
            "benchmark_name": "pk",
            "concurrency_level": 1,
            "status": "unsupported",
            "correctness_passed": None,
            "p95_latency_ms": 100.0,
            "p99_latency_ms": 120.0,
            "throughput_ops_sec": 1.0,
            "error_details": "not installed",
        },
    ]

    summary = render_summary(rows)

    assert "## Latest Run" in summary
    assert "- Run: `run-new`" in summary
    assert "## Latest Successful Run" in summary
    assert "- Run: `run-success`" in summary
    assert "install benchmark extras" in summary
    assert "## Historical Failures" in summary
    assert "run-old" in summary
    assert "rollback failed" in summary
    assert "| run-success | aksara | tiny | read_queries | pk | 1 | 2 |" in summary

    comparison = summary.split("## Performance Comparison", 1)[1].split("## Runs", 1)[0]
    assert "| tiny | read_queries | pk | 1 | asyncpg | 1.00 | 2.00 | 20.00 | 1.00x |" in comparison
    assert "| tiny | read_queries | pk | 1 | aksara | 2.00 | 3.00 | 10.00 | 2.00x |" in comparison
    assert "sqlalchemy" not in comparison


def test_write_summary_csv_serializes_aggregate_rows(tmp_path):
    path = tmp_path / "summary.csv"

    write_summary_csv(
        [
            {
                "run_id": "run-1",
                "implementation_name": "aksara",
                "command_options": {"mode": "smoke"},
                "extra": {"duration": 1},
            }
        ],
        path,
    )

    text = path.read_text()
    assert "run_id" in text
    assert "run-1" in text
    assert "mode" in text
    assert "smoke" in text
