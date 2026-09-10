"""PostgreSQL RLS proof using a real restricted application role."""

from __future__ import annotations

import os
import secrets
from contextlib import contextmanager
from types import SimpleNamespace
from typing import ClassVar
from urllib.parse import quote, urlsplit, urlunsplit
from uuid import uuid4

import asyncpg
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from aksara import TenantModel, fields
from aksara.ai.fastapi import router as ai_router
from aksara.ai.registry import AiToolRegistry, discover_tools_from_viewset
from aksara.api import ModelViewSet, clear_schema_cache, include_viewset
from aksara.context_state import tenant_id_var
from aksara.db import Database
from aksara.db.tenant_context import build_enable_rls_sql
from aksara.exceptions import DatabaseError
from aksara.permissions import IsAuthenticated
from aksara.security.principal import Principal
from aksara.tasks import TASKS_TABLE, TASKS_TABLE_SQL, TaskRecord, TaskWorker, task

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
    token = tenant_id_var.set(str(tenant_id) if tenant_id is not None else None)
    try:
        yield
    finally:
        tenant_id_var.reset(token)


@pytest.mark.asyncio
async def test_restricted_role_enforces_tenancy_across_supported_surfaces():
    """RLS remains authoritative across ORM, API, MCP-described calls, and tasks."""
    admin_url = os.environ["DATABASE_URL"]
    suffix = uuid4().hex[:10]
    role = f"aksara_rls_{suffix}"
    table = f"restricted_records_{suffix}"
    task_name = f"tests.restricted_tenant_probe.{suffix}"
    role_password = secrets.token_urlsafe(24)
    tenant_a = uuid4()
    tenant_b = uuid4()
    record_a = uuid4()
    record_b = uuid4()

    admin = await asyncpg.connect(admin_url)
    application_db = None
    previous_database = Database._instance
    clear_schema_cache()

    class RestrictedRecord(TenantModel):
        __tablename__ = table

        name = fields.String(max_length=40)

    class RestrictedRecordViewSet(ModelViewSet):
        model = RestrictedRecord
        prefix = "/restricted-records"
        permission_classes: ClassVar = [IsAuthenticated]
        stream_enabled = False

    try:
        escaped_password = role_password.replace("'", "''")
        await admin.execute(
            f'''CREATE ROLE "{role}" LOGIN PASSWORD '{escaped_password}' '''
            "NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION"
        )
        role_attributes = await admin.fetchrow(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = $1",
            role,
        )
        assert dict(role_attributes) == {"rolsuper": False, "rolbypassrls": False}

        await admin.execute(
            f'''
            CREATE TABLE "{table}" (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL,
                name VARCHAR(40) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        await admin.execute(build_enable_rls_sql(table))
        await admin.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        await admin.execute(
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "{table}" TO "{role}"'
        )
        await admin.executemany(
            f'INSERT INTO "{table}" (id, tenant_id, name) VALUES ($1, $2, $3)',
            [
                (record_a, tenant_a, "tenant-a-original"),
                (record_b, tenant_b, "tenant-b-original"),
            ],
        )

        # The worker status write is deliberately outside the restored tenant
        # context, so the application role needs only ordinary DML privileges
        # on the framework-owned queue table.
        await admin.execute(TASKS_TABLE_SQL)
        await admin.execute(
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "{TASKS_TABLE}" TO "{role}"'
        )

        application_db = Database(
            _role_dsn(admin_url, role, role_password),
            min_size=1,
            max_size=1,
        )
        await application_db.connect()

        # Direct ORM reads and writes are enforced by PostgreSQL RLS. The same
        # one-connection pool is reused for A, B, and no-tenant scopes.
        backend_pids = []
        with _tenant_scope(tenant_a):
            backend_pids.append(await application_db.fetchval("SELECT pg_backend_pid()"))
            rows = await RestrictedRecord.objects.all()
            assert [(row.tenant_id, row.name) for row in rows] == [
                (tenant_a, "tenant-a-original")
            ]
            created = await RestrictedRecord.objects.create(
                tenant_id=tenant_a,
                name="tenant-a-created",
            )
            assert created.tenant_id == tenant_a
            assert await RestrictedRecord.objects.filter(id=record_b).update(
                name="cross-tenant-update"
            ) == 0
            with pytest.raises(DatabaseError):
                await RestrictedRecord.objects.create(
                    tenant_id=tenant_b,
                    name="cross-tenant-insert",
                )

        with _tenant_scope(tenant_b):
            backend_pids.append(await application_db.fetchval("SELECT pg_backend_pid()"))
            rows = await RestrictedRecord.objects.all()
            assert [(row.tenant_id, row.name) for row in rows] == [
                (tenant_b, "tenant-b-original")
            ]

        with _tenant_scope(None):
            backend_pids.append(await application_db.fetchval("SELECT pg_backend_pid()"))
            assert await RestrictedRecord.objects.all() == []
            setting = await application_db.fetchval(
                "SELECT current_setting('aksara.current_tenant_id', true)"
            )
            assert setting in (None, "")

        assert len(set(backend_pids)) == 1

        # A generated CRUD API receives tenant identity from a server-side
        # token map. The client cannot supply or change tenant_id in its body.
        app = FastAPI()
        include_viewset(app, RestrictedRecordViewSet)
        registry = AiToolRegistry()
        for discovered_tool in discover_tools_from_viewset(RestrictedRecordViewSet):
            registry.register_tool(discovered_tool)
        app.ai_registry = registry
        app.include_router(ai_router)

        @app.middleware("http")
        async def bind_authenticated_tenant(request, call_next):
            token_value = request.headers.get("Authorization", "")
            resolved_tenant = {
                "Bearer tenant-a": tenant_a,
                "Bearer tenant-b": tenant_b,
            }.get(token_value)
            request.state.user = SimpleNamespace(
                id="test-user",
                is_authenticated=resolved_tenant is not None,
                is_staff=False,
                is_superuser=False,
            )
            if request.headers.get("X-Test-Client") == "mcp":
                principal = Principal.for_mcp_agent(
                    human_owner_id="test-user",
                    tenant_id=str(resolved_tenant) if resolved_tenant else None,
                    scopes=["mcp:read:restrictedrecord", "mcp:write:restrictedrecord"],
                )
            elif resolved_tenant is not None:
                principal = Principal.for_user(
                    user_id="test-user",
                    tenant_id=str(resolved_tenant),
                )
            else:
                principal = Principal.anonymous()
            request.state.principal = principal
            request.state.tenant_id = str(resolved_tenant) if resolved_tenant else None
            tenant_token = tenant_id_var.set(request.state.tenant_id)
            try:
                return await call_next(request)
            finally:
                tenant_id_var.reset(tenant_token)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers_a = {"Authorization": "Bearer tenant-a"}
            list_a = await client.get("/restricted-records/", headers=headers_a)
            assert list_a.status_code == 200
            assert {row["tenant_id"] for row in list_a.json()["results"]} == {
                str(tenant_a)
            }

            cross_read = await client.get(
                f"/restricted-records/{record_b}",
                headers=headers_a,
            )
            assert cross_read.status_code == 404
            cross_write = await client.patch(
                f"/restricted-records/{record_b}",
                headers=headers_a,
                json={"name": "api-cross-tenant"},
            )
            assert cross_write.status_code == 404

            created_response = await client.post(
                "/restricted-records/",
                headers=headers_a,
                json={"name": "api-created"},
            )
            assert created_response.status_code == 201
            assert created_response.json()["tenant_id"] == str(tenant_a)
            forged_tenant = await client.post(
                "/restricted-records/",
                headers=headers_a,
                json={"name": "forged", "tenant_id": str(tenant_b)},
            )
            assert forged_tenant.status_code == 422

            mcp_headers = {**headers_a, "X-Test-Client": "mcp"}
            catalog_response = await client.get("/ai/tools/mcp", headers=mcp_headers)
            assert catalog_response.status_code == 200
            update_tool = next(
                item
                for item in catalog_response.json()["tools"]
                if item["name"] == "restrictedrecord_update"
            )
            assert update_tool["metadata"]["http_method"] == "PATCH"
            assert update_tool["metadata"]["path"] == "/restricted-records/{pk}"
            mcp_cross_write = await client.patch(
                update_tool["metadata"]["path"].replace("{pk}", str(record_b)),
                headers=mcp_headers,
                json={"name": "mcp-cross-tenant"},
            )
            assert mcp_cross_write.status_code == 404

            anonymous = await client.get("/restricted-records/")
            assert anonymous.status_code == 403

        # TaskWorker restores the persisted tenant before the callable touches
        # the ORM and clears it before processing the next task.
        observations = []

        @task(name=task_name)
        async def inspect_tenant_rows():
            rows = await RestrictedRecord.objects.all()
            cross_update_count = await RestrictedRecord.objects.filter(
                id=record_b if tenant_id_var.get() == str(tenant_a) else record_a
            ).update(name="task-cross-tenant")
            observations.append(
                {
                    "tenant": tenant_id_var.get(),
                    "names": sorted(row.name for row in rows),
                    "cross_update_count": cross_update_count,
                }
            )
            return observations[-1]

        worker = TaskWorker(db=application_db)
        for tenant in (str(tenant_a), str(tenant_b), None):
            record = TaskRecord(
                id=uuid4(),
                task_name=task_name,
                tenant_id=tenant,
                payload={"args": [], "kwargs": {}},
                status="running",
                attempts=1,
                max_attempts=1,
            )
            await worker._process_task(record)
            assert tenant_id_var.get() is None

        assert observations[0]["tenant"] == str(tenant_a)
        assert "tenant-b-original" not in observations[0]["names"]
        assert observations[0]["cross_update_count"] == 0
        assert observations[1] == {
            "tenant": str(tenant_b),
            "names": ["tenant-b-original"],
            "cross_update_count": 0,
        }
        assert observations[2] == {
            "tenant": None,
            "names": [],
            "cross_update_count": 0,
        }

        persisted_b = await admin.fetchrow(
            f'SELECT tenant_id, name FROM "{table}" WHERE id = $1',
            record_b,
        )
        assert persisted_b["tenant_id"] == tenant_b
        assert persisted_b["name"] == "tenant-b-original"
    finally:
        Database._instance = previous_database
        if application_db is not None:
            await application_db.disconnect()
        await admin.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
        await admin.execute(
            f'REVOKE ALL PRIVILEGES ON TABLE "{TASKS_TABLE}" FROM "{role}"'
        )
        await admin.execute(f'DROP ROLE IF EXISTS "{role}"')
        await admin.close()
        clear_schema_cache()
