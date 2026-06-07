"""JSON, CSV, and Markdown reporting for benchmark runs."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
from glob import glob
import json
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable

from benchmarks.config import BenchmarkRunConfig
from benchmarks.metrics import BenchmarkResult


def write_json(results: Iterable[BenchmarkResult], path: Path) -> None:
    rows = [result.to_dict() for result in results]
    path.write_text(json.dumps(rows, indent=2, default=str) + "\n")


def write_csv(results: Iterable[BenchmarkResult], path: Path) -> None:
    rows = [result.to_dict() for result in results]
    if not rows:
        path.write_text("")
        return
    fieldnames = [key for key in rows[0] if key != "extra"] + ["extra"]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            row = row.copy()
            row["extra"] = json.dumps(row.get("extra", {}), default=str)
            row["command_options"] = json.dumps(row.get("command_options", {}), default=str)
            writer.writerow(row)


def write_summary_csv(rows: Iterable[dict[str, Any]], path: Path) -> None:
    """Write loaded result rows to CSV for spreadsheet analysis."""

    materialized = [row.copy() for row in rows]
    if not materialized:
        path.write_text("")
        return

    preferred = [
        "run_id",
        "started_at",
        "completed_at",
        "git_commit",
        "benchmark_mode",
        "implementation_name",
        "dataset_profile",
        "workload",
        "benchmark_name",
        "concurrency_level",
        "status",
        "correctness_passed",
        "failure_count",
        "p50_latency_ms",
        "p95_latency_ms",
        "p99_latency_ms",
        "throughput_ops_sec",
        "error_details",
        "_source_file",
    ]
    keys = {key for row in materialized for key in row}
    fieldnames = [key for key in preferred if key in keys]
    fieldnames.extend(sorted(keys - set(fieldnames)))

    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in materialized:
            serialized = {}
            for key in fieldnames:
                value = row.get(key)
                if isinstance(value, dict | list | tuple):
                    serialized[key] = json.dumps(value, default=str)
                elif value is None:
                    serialized[key] = ""
                else:
                    serialized[key] = value
            writer.writerow(serialized)


def render_markdown(results: list[BenchmarkResult], config: BenchmarkRunConfig) -> str:
    dataset = config.profile
    lines = [
        "# Aksara ORM Operational Benchmark Report",
        "",
        "## Environment Summary",
        "",
        f"- Database: `{config.database.masked_url}`",
        f"- PostgreSQL: `{results[0].postgres_version if results else 'unknown'}`",
        f"- Dataset profile: `{dataset.name}`",
        f"- Benchmark mode: `{config.mode}`",
        f"- Run ID: `{config.run_id or 'unknown'}`",
        f"- Implementations: `{', '.join(config.implementations)}`",
        f"- Workloads: `{', '.join(config.workloads)}`",
        f"- Iterations: `{config.iterations}`",
        f"- Warmup iterations: `{config.warmup_iterations}`",
        f"- Git commit: `{config.git_commit or 'unknown'}`",
        "",
        "## Dataset Summary",
        "",
        "| Table family | Rows |",
        "| --- | ---: |",
        f"| companies | {dataset.companies} |",
        f"| vendors | {dataset.vendors} |",
        f"| invoices | {dataset.invoices} |",
        f"| invoice_lines | {dataset.invoice_lines} |",
        "",
        "## Benchmark Summary",
        "",
        "| Implementation | Workload | Benchmark | Concurrency | Status | p50 ms | p95 ms | p99 ms | ops/sec | Correct |",
        "| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- |",
    ]

    for result in results:
        correct = "n/a" if result.correctness_passed is None else str(result.correctness_passed).lower()
        lines.append(
            "| {impl} | {workload} | {name} | {conc} | {status} | {p50:.2f} | {p95:.2f} | {p99:.2f} | {ops:.2f} | {correct} |".format(
                impl=result.implementation_name,
                workload=result.workload,
                name=result.benchmark_name,
                conc=result.concurrency_level,
                status=result.status,
                p50=result.p50_latency_ms,
                p95=result.p95_latency_ms,
                p99=result.p99_latency_ms,
                ops=result.throughput_ops_sec,
                correct=correct,
            )
        )

    failures = [r for r in results if r.status == "failed"]
    unsupported = [r for r in results if r.status == "unsupported"]
    slowest = sorted((r for r in results if r.status == "passed"), key=lambda r: r.p99_latency_ms, reverse=True)[:10]

    lines.extend(["", "## Correctness Failures", ""])
    if failures:
        for result in failures:
            lines.append(f"- `{result.implementation_name}/{result.workload}/{result.benchmark_name}`: {result.error_details or 'failed'}")
    else:
        lines.append("No correctness failures recorded.")

    lines.extend(["", "## Stability Warnings", ""])
    warnings = [
        r for r in results
        if r.peak_memory_mb is not None
        and r.rss_before_mb is not None
        and r.rss_after_mb is not None
        and (r.rss_after_mb - r.rss_before_mb) > 128
    ]
    if warnings:
        for result in warnings:
            delta = (result.rss_after_mb or 0) - (result.rss_before_mb or 0)
            lines.append(f"- `{result.benchmark_name}` grew RSS by {delta:.1f} MB.")
    else:
        lines.append("No RSS growth warnings recorded by the harness.")

    lines.extend(["", "## Slowest Operations", ""])
    if slowest:
        for result in slowest:
            lines.append(
                f"- `{result.implementation_name}/{result.benchmark_name}` p99={result.p99_latency_ms:.2f} ms, p95={result.p95_latency_ms:.2f} ms"
            )
    else:
        lines.append("No completed benchmark rows.")

    lines.extend(["", "## Concurrency Degradation", ""])
    concurrency_rows = [r for r in results if r.workload == "concurrency" and r.status == "passed"]
    if concurrency_rows:
        lines.append("| Implementation | Benchmark | Concurrency | p95 ms | ops/sec |")
        lines.append("| --- | --- | ---: | ---: | ---: |")
        for result in concurrency_rows:
            lines.append(
                f"| {result.implementation_name} | {result.benchmark_name} | {result.concurrency_level} | {result.p95_latency_ms:.2f} | {result.throughput_ops_sec:.2f} |"
            )
    else:
        lines.append("No completed concurrency rows.")

    lines.extend(["", "## Unsupported Workloads", ""])
    if unsupported:
        for result in unsupported:
            lines.append(f"- `{result.implementation_name}/{result.benchmark_name}`: {result.error_details}")
    else:
        lines.append("No unsupported workloads reported.")

    lines.append("")
    return "\n".join(lines)


def write_markdown(results: list[BenchmarkResult], config: BenchmarkRunConfig, path: Path) -> None:
    path.write_text(render_markdown(results, config))


def load_result_rows(paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            data = data.get("results", [])
        if not isinstance(data, list):
            raise ValueError(f"{path} does not contain a JSON result list")
        for row in data:
            if not isinstance(row, dict):
                continue
            normalized = row.copy()
            normalized["_source_file"] = str(path)
            rows.append(normalized)
    return rows


def expand_result_paths(paths: Iterable[Path]) -> list[Path]:
    expanded: list[Path] = []
    for path in paths:
        text = str(path)
        if any(char in text for char in "*?["):
            expanded.extend(Path(match) for match in sorted(glob(text)))
        else:
            expanded.append(path)
    return expanded


def _run_key(row: dict[str, Any]) -> str:
    return row.get("run_id") or f"legacy:{row.get('_source_file', 'unknown')}"


def _int_value(row: dict[str, Any], field: str, default: int = 1) -> int:
    try:
        return int(row.get(field) or default)
    except (TypeError, ValueError):
        return default


def _group_key(row: dict[str, Any]) -> tuple[str, str, str, int]:
    return (
        str(row.get("implementation_name", "unknown")),
        str(row.get("workload", "unknown")),
        str(row.get("benchmark_name", "unknown")),
        _int_value(row, "concurrency_level"),
    )


def _case_key(row: dict[str, Any]) -> tuple[str, str, str, int]:
    return (
        str(row.get("dataset_profile", "unknown")),
        str(row.get("workload", "unknown")),
        str(row.get("benchmark_name", "unknown")),
        _int_value(row, "concurrency_level"),
    )


def _duplicate_key(row: dict[str, Any]) -> tuple[str, str, str, str, str, int]:
    impl, workload, benchmark, concurrency = _group_key(row)
    return (
        _run_key(row),
        impl,
        str(row.get("dataset_profile", "unknown")),
        workload,
        benchmark,
        concurrency,
    )


def _parse_time(value: Any) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    text = str(value)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _row_time(row: dict[str, Any]) -> datetime:
    return max(
        _parse_time(row.get("started_at")),
        _parse_time(row.get("timestamp")),
        _parse_time(row.get("completed_at")),
    )


def _run_time(rows: list[dict[str, Any]]) -> datetime:
    return max((_row_time(row) for row in rows), default=datetime.min.replace(tzinfo=timezone.utc))


def _run_completed(rows: list[dict[str, Any]]) -> str:
    completed = max(
        (str(row.get("completed_at") or "") for row in rows if row.get("completed_at")),
        default="unknown",
    )
    return completed or "unknown"


def _is_failed(row: dict[str, Any]) -> bool:
    return row.get("status") == "failed" or row.get("correctness_passed") is False


def _is_unsupported(row: dict[str, Any]) -> bool:
    return row.get("status") == "unsupported"


def _is_passed(row: dict[str, Any]) -> bool:
    return row.get("status") == "passed" and row.get("correctness_passed") is not False


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    failed = sum(1 for row in rows if _is_failed(row))
    unsupported = sum(1 for row in rows if _is_unsupported(row))
    passed = sum(1 for row in rows if _is_passed(row))
    other = max(0, len(rows) - failed - unsupported - passed)
    return {"passed": passed, "failed": failed, "unsupported": unsupported, "other": other}


def _mean(rows: list[dict[str, Any]], field: str) -> float:
    values = [float(row.get(field) or 0) for row in rows]
    return fmean(values) if values else 0.0


def _error_text(row: dict[str, Any], fallback: str) -> str:
    return str(row.get("error_details") or fallback).replace("\n", " ")[:180]


def _format_sources(rows: list[dict[str, Any]]) -> str:
    source_files = sorted({str(row.get("_source_file", "unknown")) for row in rows})
    return ", ".join(source_files)


def _append_latest_run(lines: list[str], run_id: str, rows: list[dict[str, Any]]) -> None:
    first = rows[0]
    counts = _status_counts(rows)
    implementations = sorted({str(row.get("implementation_name", "unknown")) for row in rows})
    workloads = sorted({str(row.get("workload", "unknown")) for row in rows})
    profiles = sorted({str(row.get("dataset_profile", "unknown")) for row in rows})

    lines.extend(
        [
            "## Latest Run",
            "",
            f"- Run: `{run_id}`",
            f"- Mode: `{first.get('benchmark_mode') or 'unknown'}`",
            f"- Profiles: `{', '.join(profiles)}`",
            f"- Started: `{first.get('started_at') or 'unknown'}`",
            f"- Completed: `{_run_completed(rows)}`",
            f"- Implementations: `{', '.join(implementations)}`",
            f"- Workloads: `{', '.join(workloads)}`",
            f"- Rows: `{len(rows)}` total, `{counts['passed']}` passed, `{counts['failed']}` failed, "
            f"`{counts['unsupported']}` unsupported",
            f"- Source files: `{_format_sources(rows)}`",
            "",
        ]
    )

    failures = [row for row in rows if _is_failed(row)]
    if failures:
        lines.append("### Latest Failures")
        lines.append("")
        lines.append("| Implementation | Workload | Benchmark | Concurrency | Error |")
        lines.append("| --- | --- | --- | ---: | --- |")
        for row in sorted(failures, key=_group_key):
            impl, workload, benchmark, concurrency = _group_key(row)
            lines.append(f"| {impl} | {workload} | {benchmark} | {concurrency} | {_error_text(row, 'failed')} |")
        lines.append("")


def _append_latest_successful_run(
    lines: list[str],
    sorted_runs: list[tuple[str, list[dict[str, Any]]]],
) -> None:
    lines.extend(["## Latest Successful Run", ""])
    for run_id, rows in sorted_runs:
        counts = _status_counts(rows)
        if counts["failed"] == 0 and counts["passed"] > 0:
            first = rows[0]
            lines.extend(
                [
                    f"- Run: `{run_id}`",
                    f"- Mode: `{first.get('benchmark_mode') or 'unknown'}`",
                    f"- Started: `{first.get('started_at') or 'unknown'}`",
                    f"- Completed: `{_run_completed(rows)}`",
                    f"- Rows: `{len(rows)}` total, `{counts['passed']}` passed, "
                    f"`{counts['unsupported']}` unsupported",
                    f"- Source files: `{_format_sources(rows)}`",
                    "",
                ]
            )
            return
    lines.append("No successful run with passed rows found in the provided result files.")
    lines.append("")


def _append_historical_failures(lines: list[str], rows: list[dict[str, Any]]) -> None:
    failures = [row for row in rows if _is_failed(row)]
    lines.extend(["## Historical Failures Detected", ""])
    if not failures:
        lines.append("No historical correctness failures detected in the provided result files.")
        lines.append("")
        return

    grouped: dict[tuple[str, str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in failures:
        grouped[_group_key(row)].append(row)

    lines.append("| Implementation | Workload | Benchmark | Concurrency | Runs | Latest Seen | Example Error |")
    lines.append("| --- | --- | --- | ---: | ---: | --- | --- |")
    for (impl, workload, benchmark, concurrency), group in sorted(grouped.items()):
        run_count = len({_run_key(row) for row in group})
        latest = max(str(row.get("started_at") or row.get("timestamp") or "unknown") for row in group)
        lines.append(
            f"| {impl} | {workload} | {benchmark} | {concurrency} | {run_count} | {latest} | "
            f"{_error_text(group[0], 'failed')} |"
        )
    lines.append("")


def _append_historical_unsupported(lines: list[str], rows: list[dict[str, Any]]) -> None:
    unsupported = [row for row in rows if _is_unsupported(row)]
    lines.extend(["## Historical Unsupported", ""])
    if not unsupported:
        lines.append("No unsupported implementation/workload pairs detected in the provided result files.")
        lines.append("")
        return

    grouped: dict[tuple[str, str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in unsupported:
        grouped[_group_key(row)].append(row)

    lines.append("| Implementation | Workload | Benchmark | Concurrency | Runs | Latest Seen | Reason |")
    lines.append("| --- | --- | --- | ---: | ---: | --- | --- |")
    for (impl, workload, benchmark, concurrency), group in sorted(grouped.items()):
        run_count = len({_run_key(row) for row in group})
        latest_row = max(group, key=_row_time)
        latest = str(latest_row.get("started_at") or latest_row.get("timestamp") or "unknown")
        lines.append(
            f"| {impl} | {workload} | {benchmark} | {concurrency} | {run_count} | {latest} | "
            f"{_error_text(latest_row, 'unsupported')} |"
        )
    lines.append("")


def _append_duplicates(lines: list[str], rows: list[dict[str, Any]]) -> None:
    grouped: dict[tuple[str, str, str, str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_duplicate_key(row)].append(row)
    duplicates = {key: group for key, group in grouped.items() if len(group) > 1}

    lines.extend(["## Duplicate Result Rows", ""])
    if not duplicates:
        lines.append("No duplicate benchmark rows detected within a run.")
        lines.append("")
        return

    lines.append("| Run | Implementation | Profile | Workload | Benchmark | Concurrency | Count | Source files |")
    lines.append("| --- | --- | --- | --- | --- | ---: | ---: | --- |")
    for (run_id, impl, profile, workload, benchmark, concurrency), group in sorted(duplicates.items()):
        lines.append(
            f"| {run_id} | {impl} | {profile} | {workload} | {benchmark} | {concurrency} | "
            f"{len(group)} | {_format_sources(group)} |"
        )
    lines.append("")


def _comparison_groups(
    rows: list[dict[str, Any]],
) -> list[tuple[tuple[str, str, str, int], dict[str, list[dict[str, Any]]]]]:
    passed = [row for row in rows if _is_passed(row)]
    grouped: dict[tuple[str, str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in passed:
        grouped[_case_key(row)].append(row)

    comparisons: list[tuple[tuple[str, str, str, int], dict[str, list[dict[str, Any]]]]] = []
    for key, group in grouped.items():
        by_impl: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in group:
            by_impl[str(row.get("implementation_name", "unknown"))].append(row)
        if len(by_impl) > 1:
            comparisons.append((key, by_impl))
    return comparisons


def _append_comparisons(
    lines: list[str],
    sorted_runs: list[tuple[str, list[dict[str, Any]]]],
) -> None:
    selected_run_id = ""
    comparisons: list[tuple[tuple[str, str, str, int], dict[str, list[dict[str, Any]]]]] = []
    for run_id, run_rows in sorted_runs:
        comparisons = _comparison_groups(run_rows)
        if comparisons:
            selected_run_id = run_id
            break

    lines.extend(["## Performance Comparison", ""])
    if not comparisons:
        lines.append("No same-run implementation comparisons available in the provided result files.")
        lines.append("")
        return

    lines.append(f"Newest comparable run `{selected_run_id}`. Failed and unsupported rows are excluded.")
    lines.append("")
    lines.append("| Profile | Workload | Benchmark | Concurrency | Implementation | p95 ms | p99 ms | ops/sec | p95 vs best |")
    lines.append("| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: |")
    for (profile, workload, benchmark, concurrency), by_impl in sorted(comparisons):
        p95_by_impl = {impl: _mean(group, "p95_latency_ms") for impl, group in by_impl.items()}
        best_p95 = min((value for value in p95_by_impl.values() if value > 0), default=0.0)
        for impl, group in sorted(by_impl.items()):
            p95 = p95_by_impl[impl]
            ratio = (p95 / best_p95) if best_p95 > 0 else 0.0
            lines.append(
                f"| {profile} | {workload} | {benchmark} | {concurrency} | {impl} | "
                f"{p95:.2f} | {_mean(group, 'p99_latency_ms'):.2f} | "
                f"{_mean(group, 'throughput_ops_sec'):.2f} | {ratio:.2f}x |"
            )
    lines.append("")


def render_summary(rows: list[dict[str, Any]]) -> str:
    runs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        runs[_run_key(row)].append(row)

    lines = ["# Benchmark Result Summary", ""]
    if not runs:
        lines.append("No benchmark result rows found.")
        return "\n".join(lines)

    sorted_runs = sorted(
        runs.items(),
        key=lambda item: _run_time(item[1]),
        reverse=True,
    )
    latest_run_id, latest_rows = sorted_runs[0]
    _append_latest_run(lines, latest_run_id, latest_rows)
    _append_latest_successful_run(lines, sorted_runs)
    _append_historical_failures(lines, rows)
    _append_historical_unsupported(lines, rows)
    _append_duplicates(lines, rows)
    _append_comparisons(lines, sorted_runs)

    lines.extend(["## Runs", ""])

    for run_id, run_rows in sorted_runs:
        first = run_rows[0]
        mode = first.get("benchmark_mode") or "unknown"
        started_at = first.get("started_at") or "unknown"
        completed_at = _run_completed(run_rows)
        git_commit = first.get("git_commit") or "unknown"
        counts = _status_counts(run_rows)

        lines.extend(
            [
                f"## Run `{run_id}`",
                "",
                f"- Mode: `{mode}`",
                f"- Started: `{started_at}`",
                f"- Completed: `{completed_at}`",
                f"- Git commit: `{git_commit}`",
                f"- Rows: `{len(run_rows)}` total, `{counts['passed']}` passed, `{counts['failed']}` failed, "
                f"`{counts['unsupported']}` unsupported",
                f"- Source files: `{_format_sources(run_rows)}`",
                "",
            ]
        )

        failures = [row for row in run_rows if _is_failed(row)]
        unsupported = [row for row in run_rows if _is_unsupported(row)]
        passed = [row for row in run_rows if _is_passed(row)]

        lines.append("### Correctness Failures")
        lines.append("")
        if failures:
            lines.append("| Implementation | Workload | Benchmark | Concurrency | Count | Error |")
            lines.append("| --- | --- | --- | ---: | ---: | --- |")
            grouped: dict[tuple[str, str, str, int], list[dict[str, Any]]] = defaultdict(list)
            for row in failures:
                grouped[_group_key(row)].append(row)
            for (impl, workload, benchmark, concurrency), group in sorted(grouped.items()):
                lines.append(
                    f"| {impl} | {workload} | {benchmark} | {concurrency} | {len(group)} | "
                    f"{_error_text(group[0], 'failed')} |"
                )
        else:
            lines.append("No correctness failures.")

        lines.extend(["", "### Unsupported", ""])
        if unsupported:
            lines.append("| Implementation | Workload | Benchmark | Concurrency | Count | Reason |")
            lines.append("| --- | --- | --- | ---: | ---: | --- |")
            grouped = defaultdict(list)
            for row in unsupported:
                grouped[_group_key(row)].append(row)
            for (impl, workload, benchmark, concurrency), group in sorted(grouped.items()):
                lines.append(
                    f"| {impl} | {workload} | {benchmark} | {concurrency} | {len(group)} | "
                    f"{_error_text(group[0], 'unsupported')} |"
                )
        else:
            lines.append("No unsupported rows.")

        lines.extend(["", "### Passed Performance", ""])
        if passed:
            lines.append("| Implementation | Workload | Benchmark | Concurrency | Count | p50 ms | p95 ms | p99 ms | ops/sec |")
            lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
            grouped = defaultdict(list)
            for row in passed:
                grouped[_group_key(row)].append(row)
            for (impl, workload, benchmark, concurrency), group in sorted(grouped.items()):
                lines.append(
                    f"| {impl} | {workload} | {benchmark} | {concurrency} | {len(group)} | "
                    f"{_mean(group, 'p50_latency_ms'):.2f} | {_mean(group, 'p95_latency_ms'):.2f} | "
                    f"{_mean(group, 'p99_latency_ms'):.2f} | {_mean(group, 'throughput_ops_sec'):.2f} |"
                )
        else:
            lines.append("No passed performance rows.")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_summary_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize benchmark JSON result files.")
    parser.add_argument("paths", nargs="+", type=Path, help="Benchmark JSON result files.")
    parser.add_argument("--markdown", type=Path, help="Optional path to write the Markdown summary.")
    parser.add_argument("--csv", type=Path, help="Optional path to write flattened aggregate rows as CSV.")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_summary_parser()
    args = parser.parse_args(argv)
    paths = expand_result_paths(args.paths)
    rows = load_result_rows(paths)
    summary = render_summary(rows)
    if args.markdown:
        args.markdown.write_text(summary)
    if args.csv:
        write_summary_csv(rows, args.csv)
    print(summary, end="")


if __name__ == "__main__":
    main()
