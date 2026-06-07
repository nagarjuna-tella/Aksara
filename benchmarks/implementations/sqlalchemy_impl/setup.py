"""SQLAlchemy async implementation setup."""

from __future__ import annotations

import asyncpg
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from benchmarks.config import BenchmarkRunConfig
from benchmarks.implementations.base import BenchmarkImplementation
from benchmarks.implementations.postgres_common import drop_prefixed_tables, seed_dataset
from benchmarks.implementations.sqlalchemy_impl.models import Base
from benchmarks.implementations.sqlalchemy_impl.operations import SQLAlchemyOperations


class SQLAlchemyImplementation(SQLAlchemyOperations, BenchmarkImplementation):
    name = "sqlalchemy"
    table_prefix = "bench_sqlalchemy_"

    def __init__(self, config: BenchmarkRunConfig):
        super().__init__(config)
        self.engine: AsyncEngine | None = None
        self.session_maker: async_sessionmaker | None = None
        self.raw_pool: asyncpg.Pool | None = None

    async def setup(self) -> None:
        self.raw_pool = await asyncpg.create_pool(
            self.config.database.url,
            min_size=1,
            max_size=self.config.database.pool_size,
        )
        self.postgres_version = await self.fetchval("SHOW server_version")
        async with self.raw_pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
            await drop_prefixed_tables(conn, self.table_prefix)

        self.engine = create_async_engine(
            self.config.database.sqlalchemy_url,
            echo=False,
            pool_size=self.config.database.pool_size,
            max_overflow=0,
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.session_maker = async_sessionmaker(self.engine, expire_on_commit=False)
        await seed_dataset(self.raw_pool, self.table_prefix, self.dataset)

    async def teardown(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()
            self.engine = None
        if self.raw_pool is not None:
            await self.raw_pool.close()
            self.raw_pool = None

