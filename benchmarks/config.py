"""Configuration for the PostgreSQL-only ORM benchmark suite."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import quote_plus


DEFAULT_DB_HOST = "localhost"
DEFAULT_DB_PORT = 5432
DEFAULT_DB_NAME = "aksara_test"
DEFAULT_DB_USER = "postgres"
DEFAULT_DB_PASSWORD = "qwertyuiop"
DEFAULT_DB_POOL_SIZE = 20

IMPLEMENTATIONS = ("aksara", "asyncpg", "sqlalchemy")
BENCHMARK_MODES = ("smoke", "correctness", "performance", "soak")
MODE_DEFAULTS = {
    "smoke": {"iterations": 1, "warmup_iterations": 0, "profile": "tiny"},
    "correctness": {"iterations": 3, "warmup_iterations": 1, "profile": "tiny"},
    "performance": {"iterations": 100, "warmup_iterations": 10, "profile": "small"},
    "soak": {"iterations": 1, "warmup_iterations": 0, "profile": "tiny"},
}
WORKLOADS = (
    "single_ops",
    "bulk_writes",
    "read_queries",
    "relationships",
    "concurrency",
    "transactions",
    "migrations",
    "soak",
)
DEFAULT_WORKLOADS = (
    "single_ops",
    "bulk_writes",
    "read_queries",
    "relationships",
    "concurrency",
    "transactions",
    "migrations",
)


@dataclass(frozen=True)
class DatasetProfile:
    """A deterministic benchmark dataset size profile."""

    name: str
    companies: int
    vendors: int
    invoices: int
    invoice_lines_per_invoice: int

    @property
    def invoice_lines(self) -> int:
        return self.invoices * self.invoice_lines_per_invoice


DATASET_PROFILES: dict[str, DatasetProfile] = {
    "tiny": DatasetProfile("tiny", companies=2, vendors=100, invoices=1_000, invoice_lines_per_invoice=3),
    "small": DatasetProfile("small", companies=10, vendors=1_000, invoices=10_000, invoice_lines_per_invoice=5),
    "medium": DatasetProfile("medium", companies=25, vendors=5_000, invoices=100_000, invoice_lines_per_invoice=5),
    "large": DatasetProfile("large", companies=100, vendors=10_000, invoices=1_000_000, invoice_lines_per_invoice=5),
}


@dataclass(frozen=True)
class DatabaseConfig:
    """PostgreSQL connection settings shared by every implementation."""

    host: str = DEFAULT_DB_HOST
    port: int = DEFAULT_DB_PORT
    database: str = DEFAULT_DB_NAME
    user: str = DEFAULT_DB_USER
    password: str = DEFAULT_DB_PASSWORD
    pool_size: int = DEFAULT_DB_POOL_SIZE

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        return cls(
            host=os.getenv("AKSARA_BENCH_DB_HOST", DEFAULT_DB_HOST),
            port=int(os.getenv("AKSARA_BENCH_DB_PORT", str(DEFAULT_DB_PORT))),
            database=os.getenv("AKSARA_BENCH_DB_NAME", DEFAULT_DB_NAME),
            user=os.getenv("AKSARA_BENCH_DB_USER", DEFAULT_DB_USER),
            password=os.getenv("AKSARA_BENCH_DB_PASSWORD", DEFAULT_DB_PASSWORD),
            pool_size=int(os.getenv("AKSARA_BENCH_DB_POOL_SIZE", str(DEFAULT_DB_POOL_SIZE))),
        )

    @property
    def url(self) -> str:
        return (
            f"postgresql://{quote_plus(self.user)}:{quote_plus(self.password)}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    @property
    def sqlalchemy_url(self) -> str:
        return self.url.replace("postgresql://", "postgresql+asyncpg://", 1)

    @property
    def masked_url(self) -> str:
        return f"postgresql://{self.user}:***@{self.host}:{self.port}/{self.database}"


@dataclass(frozen=True)
class BenchmarkRunConfig:
    """Runtime benchmark settings derived from CLI flags and environment."""

    database: DatabaseConfig
    profile: DatasetProfile
    implementations: tuple[str, ...]
    workloads: tuple[str, ...]
    mode: str = "smoke"
    iterations: int = MODE_DEFAULTS["smoke"]["iterations"]
    warmup_iterations: int = MODE_DEFAULTS["smoke"]["warmup_iterations"]
    concurrency_levels: tuple[int, ...] = (1, 10, 50, 100, 250)
    duration_seconds: int = 60
    bulk_size: int = 100
    seed: int = 42
    output_dir: Path = Path("benchmarks/results")
    allow_large_profile: bool = False
    allow_concurrency_500: bool = False
    run_id: str | None = None
    started_at: str | None = None
    git_commit: str | None = None
    command_options: dict[str, object] | None = None

    @property
    def output_dir_abs(self) -> Path:
        return self.output_dir.resolve()


def parse_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def parse_concurrency_levels(value: str | None, *, allow_500: bool = False) -> tuple[int, ...]:
    raw = parse_csv(value) if value else tuple(str(v) for v in (1, 10, 50, 100, 250))
    levels = tuple(int(part) for part in raw)
    if any(level <= 0 for level in levels):
        raise ValueError("Concurrency levels must be positive integers.")
    if any(level >= 500 for level in levels) and not allow_500:
        raise ValueError("Concurrency level 500 or higher requires --allow-concurrency-500.")
    return levels


def resolve_implementations(value: str) -> tuple[str, ...]:
    requested = parse_csv(value)
    if not requested or "all" in requested:
        return IMPLEMENTATIONS
    unknown = sorted(set(requested) - set(IMPLEMENTATIONS))
    if unknown:
        raise ValueError(f"Unknown implementation(s): {', '.join(unknown)}")
    return requested


def resolve_workloads(value: str | None, *, mode: str = "smoke") -> tuple[str, ...]:
    if not value or value == "all":
        if mode == "soak":
            return ("soak",)
        return DEFAULT_WORKLOADS
    requested = parse_csv(value)
    unknown = sorted(set(requested) - set(WORKLOADS))
    if unknown:
        raise ValueError(f"Unknown workload(s): {', '.join(unknown)}")
    return requested


def resolve_profile(name: str, *, allow_large: bool = False) -> DatasetProfile:
    try:
        profile = DATASET_PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown profile: {name}") from exc
    if profile.name == "large" and not allow_large:
        raise ValueError("The large profile is opt-in. Pass --allow-large-profile to run it.")
    return profile


def resolve_mode(name: str) -> str:
    if name not in BENCHMARK_MODES:
        raise ValueError(f"Unknown benchmark mode: {name}")
    return name


def mode_iteration_defaults(mode: str) -> tuple[int, int]:
    resolved = resolve_mode(mode)
    defaults = MODE_DEFAULTS[resolved]
    return defaults["iterations"], defaults["warmup_iterations"]


def mode_default_profile(mode: str) -> str:
    resolved = resolve_mode(mode)
    return MODE_DEFAULTS[resolved]["profile"]


def assert_safe_database_name(database: str) -> None:
    """Reject obviously unsafe targets before benchmark table resets."""

    unsafe = {"postgres", "template0", "template1", "production", "prod"}
    if database.lower() in unsafe:
        raise ValueError(
            f"Refusing to run destructive benchmark setup against database {database!r}."
        )


async def validate_postgresql_reachable(db_config: DatabaseConfig) -> str:
    """Open a short asyncpg connection and return the PostgreSQL version."""

    import asyncpg

    assert_safe_database_name(db_config.database)
    try:
        conn = await asyncpg.connect(db_config.url)
    except Exception as exc:  # pragma: no cover - exercised only with a live DB
        raise RuntimeError(
            "PostgreSQL is not reachable. Check host, port, database, user, and password "
            f"for {db_config.masked_url}."
        ) from exc
    try:
        return await conn.fetchval("SHOW server_version")
    finally:
        await conn.close()


def format_list(values: Iterable[str]) -> str:
    return "\n".join(f"- {value}" for value in values)
