"""Aksara ORM implementation setup."""

from __future__ import annotations

from aksara.db import Database
from aksara.model.base import finalize_relations

from benchmarks.config import BenchmarkRunConfig
from benchmarks.implementations.aksara_impl.models import MODELS
from benchmarks.implementations.aksara_impl.operations import AksaraOperations
from benchmarks.implementations.base import BenchmarkImplementation
from benchmarks.implementations.postgres_common import create_common_indexes, drop_prefixed_tables, seed_dataset


class AksaraImplementation(AksaraOperations, BenchmarkImplementation):
    name = "aksara"
    table_prefix = "bench_aksara_"

    def __init__(self, config: BenchmarkRunConfig):
        super().__init__(config)
        self.db = Database(
            config.database.url,
            min_size=1,
            max_size=config.database.pool_size,
        )

    async def setup(self) -> None:
        await self.db.connect()
        self.postgres_version = await self.db.fetchval("SHOW server_version")
        await self.db.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        await drop_prefixed_tables(self.db, self.table_prefix)
        for model in MODELS:
            await self.db.execute(model.get_create_table_sql())
        await create_common_indexes(self.db, self.table_prefix)
        await self._create_composite_constraints()
        finalize_relations()
        await seed_dataset(self.db.pool, self.table_prefix, self.dataset)

    async def _create_composite_constraints(self) -> None:
        statements = [
            'CREATE UNIQUE INDEX IF NOT EXISTS "bench_aksara_uq_vendors_company_name" ON "bench_aksara_vendors" (company_id, name)',
            'CREATE UNIQUE INDEX IF NOT EXISTS "bench_aksara_uq_user_roles_user_role" ON "bench_aksara_user_roles" (user_id, role_id)',
            'CREATE UNIQUE INDEX IF NOT EXISTS "bench_aksara_uq_invoice_lines_invoice_line" ON "bench_aksara_invoice_lines" (invoice_id, line_no)',
        ]
        for statement in statements:
            await self.db.execute(statement)

    async def teardown(self) -> None:
        await self.db.disconnect()

