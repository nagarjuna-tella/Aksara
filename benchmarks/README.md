# Aksara ORM Operational Benchmarks

This benchmark suite answers one question:

> Is Aksara ORM operationally sound under realistic PostgreSQL workloads compared to mature Python ORM/database stacks?

The suite is PostgreSQL-only. It focuses on performance, correctness, stability, concurrency behavior, transaction safety, and migration execution reliability.

## Current Status

- The tiny smoke suite validates harness behavior and basic database compatibility.
- `iterations=1` smoke output is not publishable performance data.
- Performance claims require `--mode performance`, which defaults to the `small` profile and warmup iterations.
- SQLAlchemy requires benchmark extras: `pip install -e ".[benchmarks]"`.
- `asyncpg` migration rows are expected to be unsupported because Aksara migration reliability is Aksara-specific.
- Generated JSON files should be interpreted through `run_id` grouping and aggregation, not as isolated files.

## Intentionally Excluded

This benchmark phase does not compare:

- Lines of code or file count
- Developer productivity or DX scoring
- Generated API comparisons
- Studio/admin functionality
- MCP or AI-native features

Those belong in separate benchmark tracks.

## Implementations

The first pass includes:

- `aksara`: Aksara ORM
- `asyncpg`: raw SQL baseline
- `sqlalchemy`: SQLAlchemy async, if installed

Django ORM and Tortoise ORM can be added later by implementing the adapter surface in `benchmarks/implementations/`.

SQLAlchemy is optional. Install benchmark dependencies before expecting it to run:

```bash
pip install -e ".[benchmarks]"
```

The benchmark extra installs `asyncpg`, `sqlalchemy[asyncio]`, and `psutil`. If SQLAlchemy dependencies are missing, the runner marks SQLAlchemy as `unsupported` and records setup instructions in the result row.

## Database Setup

The suite always uses PostgreSQL. Local defaults are:

```text
host: localhost
port: 5432
database: aksara_test
user: postgres
password: qwertyuiop
```

Environment overrides:

```bash
export AKSARA_BENCH_DB_HOST=localhost
export AKSARA_BENCH_DB_PORT=5432
export AKSARA_BENCH_DB_NAME=aksara_test
export AKSARA_BENCH_DB_USER=postgres
export AKSARA_BENCH_DB_PASSWORD=qwertyuiop
export AKSARA_BENCH_DB_POOL_SIZE=20
```

Setup resets only implementation-prefixed benchmark tables:

- `bench_aksara_*`
- `bench_asyncpg_*`
- `bench_sqlalchemy_*`

The runner refuses obvious production-like database names such as `postgres`, `prod`, and `production`.

## CLI Examples

```bash
python -m benchmarks.runner --impl aksara --profile tiny --mode smoke
python -m benchmarks.runner --impl aksara --profile tiny --mode correctness
python -m benchmarks.runner --impl asyncpg --profile small --mode correctness
python -m benchmarks.runner --impl sqlalchemy --profile small --mode correctness
python -m benchmarks.runner --impl all --profile tiny --mode smoke
python -m benchmarks.runner --impl aksara --profile small --workload transactions --mode correctness
python -m benchmarks.runner --impl aksara --profile small --workload concurrency --concurrency 1,10,50,100 --mode correctness
python -m benchmarks.runner --impl aksara --profile tiny --mode soak --duration 60
python -m benchmarks.runner --impl all --profile small --mode performance --iterations 100 --warmup 10
python -m benchmarks.runner --list-workloads
python -m benchmarks.runner --list-impls
```

The `large` profile and concurrency level `500` are opt-in:

```bash
python -m benchmarks.runner --profile large --allow-large-profile
python -m benchmarks.runner --workload concurrency --concurrency 1,10,50,100,250,500 --allow-concurrency-500
```

## Benchmark Modes

| Mode | Default profile | Default iterations | Default warmup | Purpose |
| --- | --- | ---: | ---: | --- |
| `smoke` | `tiny` | 1 | 0 | Fast harness and database sanity check only |
| `correctness` | `tiny` | 3 | 1 | Repeatable correctness validation with light timing |
| `performance` | `small` | 100 | 10 | Performance measurement with warmup excluded |
| `soak` | `tiny` | duration-based | 0 | Stability loop for reads, writes, failures, and connection cycling |

CLI flags always win over mode defaults:

```bash
python -m benchmarks.runner --mode performance --iterations 250 --warmup 25
python -m benchmarks.runner --mode performance --profile tiny
```

Do not publish or quote performance claims from `iterations=1` smoke runs. Smoke JSON files prove the harness ran; they are not final benchmark evidence.

## Dataset Profiles

| Profile | Companies | Vendors | Invoices | Lines per invoice |
| --- | ---: | ---: | ---: | ---: |
| `tiny` | 2 | 100 | 1,000 | 3 |
| `small` | 10 | 1,000 | 10,000 | 5 |
| `medium` | 25 | 5,000 | 100,000 | 5 |
| `large` | 100 | 10,000 | 1,000,000 | 5 |

When `--profile` is omitted, the mode chooses the profile: `smoke`, `correctness`, and `soak` use `tiny`; `performance` uses `small`.

Use `tiny` and `small` for smoke and correctness runs. Reserve `medium` and `large` for deliberate performance investigations on machines where the database size and reset cost are acceptable.

## Domain Schema

The benchmark uses an InvoiceOps-style schema:

- Company
- Vendor
- Invoice
- InvoiceLine
- Payment
- User
- Role
- UserRole
- AuditLog

It covers UUID primary keys, foreign keys, one-to-many relationships, explicit many-to-many joins, decimal fields, datetime fields, status fields, nullable fields, JSONB metadata, indexes, unique constraints, and audit-style inserts.

## Workloads

Workloads are modular under `benchmarks/workloads/`:

- `single_ops`: one-row CRUD and invoice-with-lines transaction latency
- `bulk_writes`: batch inserts, updates, and deletes
- `read_queries`: primary-key/indexed lookups, filters, pagination, counts, exists, aggregations, joins, nested loads
- `relationships`: FK and explicit many-to-many loading patterns
- `concurrency`: read, write, mixed, transaction, and pool-starvation scenarios at configured concurrency levels
- `transactions`: commit, rollback, unique/FK failures, concurrent row updates, connection usability after failure
- `migrations`: Aksara migration-operation reliability checks
- `soak`: opt-in repeated reads, mixed read/write, transaction failures, and connection cycles

Default `all` excludes `soak` because soak runs for a duration.

## Correctness Gates

Every measured workload validates correctness. Examples include:

- Inserted rows are visible and have expected totals
- Invoice line totals match invoice totals
- Pagination has stable ordering and no duplicate row IDs
- Aggregates match raw SQL references
- Rollbacks do not partially commit rows
- Failed transactions leave the connection/session usable
- Concurrent updates leave a valid final state

Concurrency failures should be treated as serious until explained. If a failure is caused by benchmark-generated data collision, fix the benchmark and add a regression test. If it is caused by ORM behavior, keep the benchmark failing and document the failure.

For Aksara, correctness and stability failures are release-blocking signals:

- Any correctness failure
- Transaction rollback failure
- FK integrity failure
- Migration data preservation failure
- Connection/session leak
- ORM unusable after failed transaction
- Process crash during normal benchmark
- Unexplained memory growth during soak

Performance numbers are reported, but they are not hard failures unless the harness records an operational failure.

## Outputs

Results are written to `benchmarks/results/`:

- JSON rows
- CSV rows
- Markdown summary report

Generated result files are ignored by Git. Only `benchmarks/results/.gitkeep` is tracked.

Each result row includes benchmark name, implementation, dataset profile, concurrency, iterations, warmups, success/failure counts, p50/p95/p99/min/max/mean/stdev latency, throughput, runtime, RSS memory, correctness status, errors, timestamp, Python version, PostgreSQL version, and platform details.

Every result row also includes run metadata:

- `run_id`
- `started_at`
- `completed_at`
- `git_commit`
- `benchmark_mode`
- normalized `command_options`

`connection_peak` and `sql_query_count` are reserved in the result schema but are not yet implemented. They remain `null` until they can be collected consistently without adding fragile implementation-specific hooks.

Aggregate existing JSON files with:

```bash
python -m benchmarks.reporting benchmarks/results/*.json
python -m benchmarks.reporting benchmarks/results/*.json --markdown benchmarks/results/aggregate.md --csv benchmarks/results/aggregate.csv
```

The aggregate summary highlights the latest run first, preserves historical correctness failures across all provided files, detects duplicate benchmark rows within a run, and compares implementations for matching workload, benchmark, concurrency, and dataset profile. Correctness failures are shown before unsupported rows and passed performance numbers. Failed correctness rows are not included in performance comparison tables.

Runtime-generated IDs are namespaced by `run_id`, implementation, workload, benchmark name, concurrency task, and iteration. That keeps concurrent writes deterministic without letting one implementation or workload collide with another.

## Legacy Benchmark Cleanup

The previous `benchmarks/` folder contained single-file User/Post/Tag scripts and a committed generated JSON result. That code was removed because it did not match this PostgreSQL operational benchmark track. The useful idea from it, a shared result/timing layer, is preserved in `benchmarks/metrics.py`.

## Harness Tests

The normal test suite includes only lightweight, database-free harness tests:

```bash
python -m pytest tests/benchmarks -q
```

Heavy benchmark workloads run only when explicitly invoked through `python -m benchmarks.runner`.
