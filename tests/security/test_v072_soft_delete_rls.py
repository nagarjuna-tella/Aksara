"""Restricted-role proof for SOFTDELETE001 query preservation."""

from __future__ import annotations

import os
import secrets
from contextlib import contextmanager
from urllib.parse import quote, urlsplit, urlunsplit
from uuid import uuid4

import asyncpg
import pytest

from aksara import TenantModel, fields
from aksara.contrib.soft_delete import SoftDeleteModel, only_deleted, with_deleted
from aksara.context_state import tenant_id_var
from aksara.db import Database
from aksara.db.tenant_context import build_enable_rls_sql
from aksara.registry import ModelRegistry

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set",
)


def _role_dsn(database_url: str, role: str, password: str) -> str:
    parsed = urlsplit(database_url)
    host = parsed.hostname or "localhost"
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{quote(role)}:{quote(password)}@{host}{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


@contextmanager
def _tenant_scope(tenant_id):
    token = tenant_id_var.set(str(tenant_id))
    try:
        yield
    finally:
        tenant_id_var.reset(token)


@pytest.mark.asyncio
async def test_visibility_transform_preserves_predicates_under_restricted_rls():
    admin_url = os.environ["DATABASE_URL"]
    suffix = uuid4().hex[:10]
    role = f"aksara_soft_delete_{suffix}"
    table = f"soft_delete_records_{suffix}"
    password = secrets.token_urlsafe(24)
    tenant_a = uuid4()
    tenant_b = uuid4()
    target_id = uuid4()
    other_a_id = uuid4()
    other_b_id = uuid4()
    admin = await asyncpg.connect(admin_url)
    application_db = None
    previous_database = Database._instance
    registry_snapshot = ModelRegistry.snapshot()

    class RestrictedDocument(SoftDeleteModel, TenantModel):
        __tablename__ = table

        title = fields.String(max_length=40)

    try:
        escaped_password = password.replace("'", "''")
        await admin.execute(
            f'''CREATE ROLE "{role}" LOGIN PASSWORD '{escaped_password}' '''
            "NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION"
        )
        await admin.execute(
            f'''
            CREATE TABLE "{table}" (
                id UUID PRIMARY KEY,
                tenant_id UUID NOT NULL,
                title VARCHAR(40) NOT NULL,
                deleted_at TIMESTAMPTZ
            )
            '''
        )
        await admin.execute(build_enable_rls_sql(table))
        await admin.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        await admin.execute(
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "{table}" TO "{role}"'
        )
        await admin.executemany(
            f'INSERT INTO "{table}" (id, tenant_id, title, deleted_at) '
            "VALUES ($1, $2, $3, CURRENT_TIMESTAMP)",
            [
                (target_id, tenant_a, "target"),
                (other_a_id, tenant_a, "other-a"),
                (other_b_id, tenant_b, "other-b"),
            ],
        )

        application_db = Database(
            _role_dsn(admin_url, role, password),
            min_size=1,
            max_size=1,
        )
        await application_db.connect()
        Database._instance = application_db

        restricted = RestrictedDocument.objects.filter(
            id=target_id,
            tenant_id=tenant_a,
        )
        with _tenant_scope(tenant_a):
            including = await with_deleted(restricted).all()
            deleted = await only_deleted(restricted).all()
            assert [record.id for record in including] == [target_id]
            assert [record.id for record in deleted] == [target_id]

        with _tenant_scope(tenant_b):
            assert await with_deleted(restricted).all() == []
            assert await only_deleted(restricted).all() == []
    finally:
        Database._instance = previous_database
        if application_db is not None:
            await application_db.disconnect()
        await admin.execute(f'DROP TABLE IF EXISTS "{table}"')
        await admin.execute(f'DROP ROLE IF EXISTS "{role}"')
        await admin.close()
        ModelRegistry.clear()
        for model in registry_snapshot.values():
            ModelRegistry.register(model)
