"""Implementation adapter registry."""

from __future__ import annotations

from benchmarks.config import BenchmarkRunConfig
from benchmarks.implementations.base import BenchmarkImplementation, UnsupportedOperation


def load_implementation(name: str, config: BenchmarkRunConfig) -> BenchmarkImplementation:
    if name == "aksara":
        from benchmarks.implementations.aksara_impl.setup import AksaraImplementation

        return AksaraImplementation(config)
    if name == "asyncpg":
        from benchmarks.implementations.asyncpg_impl.setup import AsyncpgImplementation

        return AsyncpgImplementation(config)
    if name == "sqlalchemy":
        try:
            from benchmarks.implementations.sqlalchemy_impl.setup import SQLAlchemyImplementation
        except ImportError as exc:
            raise UnsupportedOperation('SQLAlchemy is not installed. Install benchmark extras with `pip install -e ".[benchmarks]"`.') from exc

        return SQLAlchemyImplementation(config)
    raise ValueError(f"Unknown implementation: {name}")
