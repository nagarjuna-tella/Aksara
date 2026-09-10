"""Generated CRUD API abuse invariants against a real PostgreSQL database."""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import ClassVar

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from aksara import Model, fields
from aksara.api import ModelViewSet, clear_schema_cache, include_viewset
from aksara.db import Database
from aksara.permissions import BasePermission
from aksara.security.principal import Principal

pytestmark = [
    pytest.mark.security,
    pytest.mark.fuzz,
    pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set"),
]


class AbuseOwner(Model):
    __tablename__ = "security_openapi_abuse_owners"

    name = fields.String(max_length=30)


class AbuseRecord(Model):
    __tablename__ = "security_openapi_abuse_records"

    name = fields.String(min_length=3, max_length=12)
    quantity = fields.Integer(min_value=1, max_value=10)
    owner = fields.ForeignKey(AbuseOwner, on_delete=fields.RESTRICT)
    protected_note = fields.String(max_length=30, default="server-owned")


# Runtime policy metadata is intentionally independent of generated schemas.
# This field remains present in the schema so the endpoint must explicitly
# reject an attempted mutation rather than silently dropping it.
AbuseRecord._fields["protected_note"].read_only = True


class AuthenticatedWriter(BasePermission):
    """Require authentication and a server-assigned mutation capability."""

    message = "Authenticated mutation permission required."

    def has_permission(self, request, view=None) -> bool:
        user = self.get_user(request)
        if user is None or not getattr(user, "is_authenticated", False):
            return False
        if self.is_safe_method(request):
            return True
        return getattr(request.state, "can_mutate", False) is True


class AbuseRecordViewSet(ModelViewSet):
    model = AbuseRecord
    prefix = "/abuse-records"
    permission_classes: ClassVar = [AuthenticatedWriter]
    stream_enabled = False


@pytest.fixture
async def generated_crud_client():
    """Run a generated ViewSet with real persistence and server-side auth state."""
    database = Database(os.environ["DATABASE_URL"], min_size=1, max_size=3)
    previous_database = Database._instance
    await database.connect()
    clear_schema_cache()

    await database.execute(f'DROP TABLE IF EXISTS "{AbuseRecord.__tablename__}" CASCADE')
    await database.execute(f'DROP TABLE IF EXISTS "{AbuseOwner.__tablename__}" CASCADE')
    await database.execute(AbuseOwner.get_create_table_sql())
    await database.execute(AbuseRecord.get_create_table_sql())
    owner = await AbuseOwner.objects.create(name="valid-owner")
    original = await AbuseRecord.objects.create(
        name="original",
        quantity=4,
        owner=owner.id,
    )

    app = FastAPI()
    include_viewset(app, AbuseRecordViewSet)

    @app.middleware("http")
    async def authenticate(request, call_next):
        token = request.headers.get("Authorization", "")
        authenticated = token in {"Bearer writer", "Bearer reader"}
        request.state.user = SimpleNamespace(
            id="api-test-user",
            is_authenticated=authenticated,
            is_staff=False,
            is_superuser=False,
        )
        request.state.can_mutate = token == "Bearer writer"
        request.state.principal = (
            Principal.for_user(user_id="api-test-user")
            if authenticated
            else Principal.anonymous()
        )
        return await call_next(request)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, owner, original

    await database.execute(f'DROP TABLE IF EXISTS "{AbuseRecord.__tablename__}" CASCADE')
    await database.execute(f'DROP TABLE IF EXISTS "{AbuseOwner.__tablename__}" CASCADE')
    await database.disconnect()
    Database._instance = previous_database
    clear_schema_cache()


@pytest.mark.asyncio
async def test_generated_crud_rejects_invalid_client_input_without_500(
    generated_crud_client,
):
    client, owner, original = generated_crud_client
    writer = {"Authorization": "Bearer writer"}

    invalid_create_cases = [
        ({"name": "valid", "quantity": "not-an-int", "owner_id": str(owner.id)}, 422),
        ({"quantity": 4, "owner_id": str(owner.id)}, 422),
        ({"name": "x" * 100, "quantity": 4, "owner_id": str(owner.id)}, 422),
        ({"name": "valid", "quantity": 0, "owner_id": str(owner.id)}, 422),
        ({"name": "valid", "quantity": 4, "unexpected": True, "owner_id": str(owner.id)}, 422),
        ({"name": "valid", "quantity": 4, "owner_id": "not-a-uuid"}, 422),
        ({"name": "valid", "quantity": 4, "owner_id": "00000000-0000-0000-0000-000000000000"}, 400),
        ({"name": "valid", "quantity": 4, "owner_id": str(owner.id), "protected_note": "overwrite"}, 403),
        ({"name": "valid", "quantity": 4, "owner_id": str(owner.id), "id": str(original.id)}, 422),
        ({"name": "valid", "quantity": 4, "owner_id": str(owner.id), "created_at": "2026-01-01T00:00:00Z"}, 422),
    ]

    before_ids = {row.id for row in await AbuseRecord.objects.all()}
    for payload, expected_status in invalid_create_cases:
        response = await client.post("/abuse-records/", headers=writer, json=payload)
        assert response.status_code == expected_status, response.text
        assert response.status_code < 500
        body = response.json()
        assert "detail" in body
        assert {row.id for row in await AbuseRecord.objects.all()} == before_ids

    malformed = await client.post(
        "/abuse-records/",
        headers={**writer, "Content-Type": "application/json"},
        content=b'{"name":',
    )
    assert malformed.status_code == 422
    assert "detail" in malformed.json()
    assert {row.id for row in await AbuseRecord.objects.all()} == before_ids

    valid = await client.post(
        "/abuse-records/",
        headers=writer,
        json={"name": "created", "quantity": 5, "owner_id": str(owner.id)},
    )
    assert valid.status_code == 201, valid.text
    assert valid.json()["name"] == "created"

    # Invalid update payloads cannot partially mutate the existing record.
    invalid_updates = [
        {"quantity": False},
        {"name": "x" * 100},
        {"owner_id": "not-a-uuid"},
        {"unknown": "value"},
        {"protected_note": "overwrite"},
        {"updated_at": "2026-01-01T00:00:00Z"},
    ]
    for payload in invalid_updates:
        response = await client.patch(
            f"/abuse-records/{original.id}",
            headers=writer,
            json=payload,
        )
        assert response.status_code in {403, 422}, response.text
        assert response.status_code < 500
        persisted = await AbuseRecord.objects.get(id=original.id)
        assert persisted.name == "original"
        assert persisted.quantity == 4
        assert persisted.protected_note == "server-owned"

    # Every error response is structured JSON with an actionable detail field.
    invalid_lookup = await client.get("/abuse-records/not-a-uuid", headers=writer)
    assert invalid_lookup.status_code == 400
    assert "detail" in invalid_lookup.json()


@pytest.mark.asyncio
async def test_generated_crud_denies_unauthorized_and_forbidden_mutations(
    generated_crud_client,
):
    client, owner, original = generated_crud_client
    payload = {"name": "changed"}

    unauthorized = await client.patch(f"/abuse-records/{original.id}", json=payload)
    assert unauthorized.status_code == 403
    assert "detail" in unauthorized.json()

    forbidden = await client.patch(
        f"/abuse-records/{original.id}",
        headers={"Authorization": "Bearer reader"},
        json=payload,
    )
    assert forbidden.status_code == 403
    assert "detail" in forbidden.json()

    unauthorized_create = await client.post(
        "/abuse-records/",
        json={"name": "created", "quantity": 5, "owner_id": str(owner.id)},
    )
    assert unauthorized_create.status_code == 403

    persisted = await AbuseRecord.objects.get(id=original.id)
    assert persisted.name == "original"
    assert len(await AbuseRecord.objects.all()) == 1


@pytest.mark.asyncio
async def test_generated_openapi_declares_closed_input_objects(generated_crud_client):
    client, _, _ = generated_crud_client
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schemas = response.json()["components"]["schemas"]

    create_schema = schemas["AbuseRecordCreate"]
    update_schema = schemas["AbuseRecordUpdate"]
    assert create_schema["additionalProperties"] is False
    assert update_schema["additionalProperties"] is False
    assert set(create_schema["required"]) >= {"name", "quantity", "owner_id"}
    assert "id" not in create_schema["properties"]
    assert "created_at" not in create_schema["properties"]
    assert "updated_at" not in update_schema["properties"]
