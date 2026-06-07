"""asyncpg raw SQL implementation setup."""

from __future__ import annotations

from contextvars import ContextVar
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import asyncpg

from benchmarks.config import BenchmarkRunConfig
from benchmarks.implementations.base import BenchmarkImplementation
from benchmarks.implementations.postgres_common import create_common_indexes, drop_prefixed_tables, seed_dataset
from benchmarks.implementations.sql_workload_mixin import SqlWorkloadMixin


class AsyncpgImplementation(SqlWorkloadMixin, BenchmarkImplementation):
    name = "asyncpg"
    table_prefix = "bench_asyncpg_"

    def __init__(self, config: BenchmarkRunConfig):
        super().__init__(config)
        self.pool: asyncpg.Pool | None = None
        self._active_connection: ContextVar[asyncpg.Connection | None] = ContextVar(
            "bench_asyncpg_active_connection",
            default=None,
        )

    async def setup(self) -> None:
        self.pool = await asyncpg.create_pool(
            self.config.database.url,
            min_size=1,
            max_size=self.config.database.pool_size,
        )
        self.postgres_version = await self.fetchval("SHOW server_version")
        async with self.pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
            await drop_prefixed_tables(conn, self.table_prefix)
            schema = Path(__file__).with_name("schema.sql").read_text().format(prefix=self.table_prefix)
            for statement in [part.strip() for part in schema.split(";") if part.strip()]:
                await conn.execute(statement)
            await create_common_indexes(conn, self.table_prefix)
        await seed_dataset(self.pool, self.table_prefix, self.dataset)

    async def teardown(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    @asynccontextmanager
    async def acquire(self):
        active = self._active_connection.get()
        if active is not None:
            yield active
            return
        if self.pool is None:
            raise RuntimeError("asyncpg pool is not connected")
        async with self.pool.acquire() as conn:
            yield conn

    @asynccontextmanager
    async def transaction(self):
        if self.pool is None:
            raise RuntimeError("asyncpg pool is not connected")
        async with self.pool.acquire() as conn:
            token = self._active_connection.set(conn)
            async with conn.transaction():
                try:
                    yield conn
                finally:
                    self._active_connection.reset(token)

    async def execute(self, sql: str, *args: Any) -> Any:
        async with self.acquire() as conn:
            return await conn.execute(sql, *args)

    async def fetch(self, sql: str, *args: Any) -> list[Any]:
        async with self.acquire() as conn:
            return await conn.fetch(sql, *args)

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        async with self.acquire() as conn:
            return await conn.fetchrow(sql, *args)

    async def fetchval(self, sql: str, *args: Any) -> Any:
        async with self.acquire() as conn:
            return await conn.fetchval(sql, *args)
