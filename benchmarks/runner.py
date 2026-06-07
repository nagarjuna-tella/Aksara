"""CLI runner for the Aksara operational ORM benchmark suite."""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import uuid
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path

from benchmarks.config import (
    DATASET_PROFILES,
    IMPLEMENTATIONS,
    WORKLOADS,
    BENCHMARK_MODES,
    BenchmarkRunConfig,
    DatabaseConfig,
    format_list,
    mode_default_profile,
    mode_iteration_defaults,
    parse_concurrency_levels,
    resolve_implementations,
    resolve_mode,
    resolve_profile,
    resolve_workloads,
    validate_postgresql_reachable,
)
from benchmarks.implementations.base import UnsupportedOperation
from benchmarks.implementations.registry import load_implementation
from benchmarks.metrics import BenchmarkResult
from benchmarks.reporting import write_csv, write_json, write_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run PostgreSQL operational ORM benchmarks.")
    parser.add_argument("--impl", default="all", help="Implementation: aksara, asyncpg, sqlalchemy, or all.")
    parser.add_argument("--profile", default=None, choices=tuple(DATASET_PROFILES), help="Dataset profile.")
    parser.add_argument("--workload", default="all", help="Workload name, comma list, or all.")
    parser.add_argument("--mode", default="smoke", choices=BENCHMARK_MODES, help="Benchmark mode preset.")
    parser.add_argument("--iterations", type=int, default=None, help="Measured iterations per case.")
    parser.add_argument(
        "--warmup",
        "--warmup-iterations",
        dest="warmup_iterations",
        type=int,
        default=None,
        help="Warmup iterations per case.",
    )
    parser.add_argument("--concurrency", default=None, help="Comma-separated concurrency levels.")
    parser.add_argument("--duration", type=int, default=60, help="Soak duration in seconds.")
    parser.add_argument("--bulk-size", type=int, default=100, help="Rows per bulk-write iteration.")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic dataset seed.")
    parser.add_argument("--output-dir", default="benchmarks/results", help="Output directory for result files.")
    parser.add_argument("--allow-large-profile", action="store_true", help="Allow the opt-in large dataset profile.")
    parser.add_argument("--allow-concurrency-500", action="store_true", help="Allow concurrency level 500 or higher.")
    parser.add_argument("--list-workloads", action="store_true", help="List workload names and exit.")
    parser.add_argument("--list-impls", action="store_true", help="List implementation names and exit.")
    return parser


def git_commit_hash() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return result.stdout.strip() or None


def normalized_options(args: argparse.Namespace, config: BenchmarkRunConfig) -> dict[str, object]:
    return {
        "impl": list(config.implementations),
        "profile": config.profile.name,
        "workload": list(config.workloads),
        "mode": config.mode,
        "iterations": config.iterations,
        "warmup_iterations": config.warmup_iterations,
        "concurrency": list(config.concurrency_levels),
        "duration": config.duration_seconds,
        "bulk_size": config.bulk_size,
        "seed": config.seed,
        "output_dir": str(config.output_dir),
        "database": config.database.masked_url,
        "allow_large_profile": args.allow_large_profile,
        "allow_concurrency_500": args.allow_concurrency_500,
    }


def config_from_args(args: argparse.Namespace) -> BenchmarkRunConfig:
    mode = resolve_mode(args.mode)
    default_iterations, default_warmups = mode_iteration_defaults(mode)
    iterations = default_iterations if args.iterations is None else args.iterations
    warmups = default_warmups if args.warmup_iterations is None else args.warmup_iterations
    profile_name = args.profile or mode_default_profile(mode)
    if iterations <= 0:
        raise ValueError("iterations must be a positive integer")
    if warmups < 0:
        raise ValueError("warmup iterations must be zero or greater")

    config = BenchmarkRunConfig(
        database=DatabaseConfig.from_env(),
        profile=resolve_profile(profile_name, allow_large=args.allow_large_profile),
        implementations=resolve_implementations(args.impl),
        workloads=resolve_workloads(args.workload, mode=mode),
        mode=mode,
        iterations=iterations,
        warmup_iterations=warmups,
        concurrency_levels=parse_concurrency_levels(args.concurrency, allow_500=args.allow_concurrency_500),
        duration_seconds=args.duration,
        bulk_size=args.bulk_size,
        seed=args.seed,
        output_dir=Path(args.output_dir),
        allow_large_profile=args.allow_large_profile,
        allow_concurrency_500=args.allow_concurrency_500,
        run_id=uuid.uuid4().hex,
        started_at=datetime.now(timezone.utc).isoformat(),
        git_commit=git_commit_hash(),
    )
    return BenchmarkRunConfig(
        **{
            **config.__dict__,
            "command_options": normalized_options(args, config),
        }
    )


async def run_workload(name: str, impl, config: BenchmarkRunConfig) -> list[BenchmarkResult]:
    module = import_module(f"benchmarks.workloads.{name}")
    return await module.run(impl, config)


async def run(config: BenchmarkRunConfig) -> list[BenchmarkResult]:
    postgres_version = await validate_postgresql_reachable(config.database)
    print(f"PostgreSQL reachable: {postgres_version}")
    print(f"Database: {config.database.masked_url}")
    print(f"Profile: {config.profile.name}")
    print(f"Mode: {config.mode} (iterations={config.iterations}, warmup={config.warmup_iterations})")
    print(f"Run ID: {config.run_id}")
    print("Benchmark setup resets only tables with implementation-specific benchmark prefixes.")

    all_results: list[BenchmarkResult] = []
    for impl_name in config.implementations:
        print(f"\n== {impl_name} ==")
        try:
            impl = load_implementation(impl_name, config)
        except UnsupportedOperation as exc:
            all_results.append(
                BenchmarkResult.unsupported(
                    benchmark_name="implementation_setup",
                    implementation_name=impl_name,
                    dataset_profile=config.profile.name,
                    workload="setup",
                    reason=str(exc),
                    postgres_version=postgres_version,
                    run_id=config.run_id,
                    started_at=config.started_at,
                    git_commit=config.git_commit,
                    benchmark_mode=config.mode,
                    command_options=config.command_options or {},
                )
            )
            print(f"unsupported: {exc}")
            continue

        try:
            await impl.setup()
            for workload in config.workloads:
                print(f"running {workload}...")
                results = await run_workload(workload, impl, config)
                all_results.extend(results)
                passed = sum(1 for result in results if result.status == "passed")
                failed = sum(1 for result in results if result.status == "failed")
                unsupported = sum(1 for result in results if result.status == "unsupported")
                print(f"{workload}: {passed} passed, {failed} failed, {unsupported} unsupported")
        finally:
            await impl.teardown()

    return all_results


def write_outputs(results: list[BenchmarkResult], config: BenchmarkRunConfig) -> tuple[Path, Path, Path]:
    config.output_dir_abs.mkdir(parents=True, exist_ok=True)
    completed_at = datetime.now(timezone.utc).isoformat()
    for result in results:
        result.apply_run_metadata(
            run_id=config.run_id,
            started_at=config.started_at,
            completed_at=completed_at,
            git_commit=config.git_commit,
            benchmark_mode=config.mode,
            command_options=config.command_options or {},
        )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = config.output_dir_abs / f"benchmark-{config.profile.name}-{stamp}"
    json_path = base.with_suffix(".json")
    csv_path = base.with_suffix(".csv")
    md_path = base.with_suffix(".md")
    write_json(results, json_path)
    write_csv(results, csv_path)
    write_markdown(results, config, md_path)
    return json_path, csv_path, md_path


async def async_main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_workloads:
        print(format_list(WORKLOADS))
        return 0
    if args.list_impls:
        print(format_list(IMPLEMENTATIONS))
        return 0

    try:
        config = config_from_args(args)
    except ValueError as exc:
        parser.error(str(exc))
    results = await run(config)
    json_path, csv_path, md_path = write_outputs(results, config)
    failed = sum(1 for result in results if result.status == "failed")
    unsupported = sum(1 for result in results if result.status == "unsupported")
    print(f"\nWrote JSON: {json_path}")
    print(f"Wrote CSV: {csv_path}")
    print(f"Wrote Markdown: {md_path}")
    print(f"Completed with {failed} failed and {unsupported} unsupported result rows.")
    return 1 if failed else 0


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
