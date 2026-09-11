"""Explicit durable HTTP dispatch, status and cancellation surface."""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, Request

from aksara.durable import (
    DurableAction,
    DurableActionRegistry,
    DurableOperationService,
    EffectClass,
    PrincipalReference,
    create_durable_operations_router,
)
from aksara.durable.api import _reference
from aksara.durable.errors import AuthorizationDenied
from aksara.security.principal import Principal


async def _handler(_context, command):
    return command


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "forged_value"),
    [
        ("principal_kind", "user"),
        ("subject_id", "forged-subject"),
        ("tenant_id", "forged-tenant"),
        ("human_owner_id", "forged-owner"),
        ("agent_id", "forged-agent"),
        ("credential_id", "forged-token"),
    ],
)
async def test_principal_reference_rejects_each_forged_stable_identity_field(
    field,
    forged_value,
):
    principal = Principal.for_ai_agent(
        agent_id="agent-1",
        human_owner_id="owner-1",
        tenant_id="tenant-1",
        token_id="token-1",
    )
    valid = PrincipalReference.from_principal(
        principal,
        resolver_key="test",
        identity_namespace="api-tests",
    )

    async def forged_reference(_principal, _request):
        return replace(valid, **{field: forged_value})

    request = Request({"type": "http", "method": "POST", "path": "/"})
    with pytest.raises(AuthorizationDenied):
        await _reference(forged_reference, principal, request)


@pytest.mark.asyncio
async def test_dispatch_status_duplicate_and_cancel_without_storage_leak(durable_db):
    tenant = str(uuid4())
    actions = DurableActionRegistry()
    actions.register(
        DurableAction(
            name="orders.reserve",
            version="1",
            handler=_handler,
            effect_class=EffectClass.POSTGRES_ATOMIC,
        )
    )
    service = DurableOperationService(
        durable_db,
        application_namespace="api-tests",
        actions=actions,
        retention_seconds=60,
        idempotency_seconds=60,
    )

    async def reference_factory(principal, _request):
        return PrincipalReference.from_principal(
            principal,
            resolver_key="test",
            identity_namespace="api-tests",
        )

    app = FastAPI()

    @app.middleware("http")
    async def trusted_test_identity(request: Request, call_next):
        request.state.principal = Principal.for_user(
            "user-1",
            tenant_id=request.headers.get("x-server-tenant", tenant),
        )
        return await call_next(request)

    app.include_router(
        create_durable_operations_router(
            service,
            principal_reference_factory=reference_factory,
        )
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            "/durable/operations",
            headers={"Idempotency-Key": "reserve-1"},
            json={
                "action": "orders.reserve",
                "action_version": "1",
                "command": {"sku": "A-1", "quantity": 2},
            },
        )
        duplicate = await client.post(
            "/durable/operations",
            headers={"Idempotency-Key": "reserve-1"},
            json={
                "action": "orders.reserve",
                "action_version": "1",
                "command": {"quantity": 2, "sku": "A-1"},
            },
        )
        assert first.status_code == 202
        assert duplicate.status_code == 202
        assert first.json()["created"] is True
        assert duplicate.json()["created"] is False
        operation = first.json()["operation"]
        assert duplicate.json()["operation"]["id"] == operation["id"]
        assert first.headers["location"] == first.json()["status_url"]
        assert "fence" not in operation
        assert "worker_id" not in operation
        assert "command_id" not in operation

        status_response = await client.get(first.json()["status_url"])
        assert status_response.status_code == 200
        assert status_response.json()["state"] == "ready"

        hidden = await client.get(
            first.json()["status_url"],
            headers={"x-server-tenant": str(uuid4())},
        )
        assert hidden.status_code == 404
        unknown = await client.get(f"/durable/operations/{uuid4()}")
        assert hidden.json() == unknown.json() == {
            "detail": {"code": "operation_not_found"}
        }

        cancelled = await client.post(
            f"{first.json()['status_url']}/cancel",
            json={"reason": "customer withdrew request"},
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["state"] == "cancelled"

        terminal_conflict = await client.post(
            f"{first.json()['status_url']}/cancel",
            json={},
        )
        assert terminal_conflict.status_code == 409

        terminal_duplicate = await client.post(
            "/durable/operations",
            headers={"Idempotency-Key": "reserve-1"},
            json={
                "action": "orders.reserve",
                "action_version": "1",
                "command": {"sku": "A-1", "quantity": 2},
            },
        )
        assert terminal_duplicate.status_code == 200
        assert terminal_duplicate.json()["operation"]["state"] == "cancelled"


@pytest.mark.asyncio
async def test_dispatch_rejects_forged_principal_reference(durable_db):
    tenant = str(uuid4())
    actions = DurableActionRegistry()
    actions.register(
        DurableAction(
            name="orders.reserve",
            version="1",
            handler=_handler,
            effect_class=EffectClass.POSTGRES_ATOMIC,
        )
    )
    service = DurableOperationService(
        durable_db,
        application_namespace="api-tests",
        actions=actions,
        retention_seconds=60,
        idempotency_seconds=60,
    )

    async def forged_reference(_principal, _request):
        return PrincipalReference(
            resolver_key="test",
            resolver_version="1",
            identity_namespace="api-tests",
            principal_kind="user",
            subject_id="attacker-selected-subject",
            tenant_id=tenant,
        )

    app = FastAPI()

    @app.middleware("http")
    async def trusted_test_identity(request: Request, call_next):
        request.state.principal = Principal.for_user("user-1", tenant_id=tenant)
        return await call_next(request)

    app.include_router(
        create_durable_operations_router(
            service,
            principal_reference_factory=forged_reference,
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/durable/operations",
            json={
                "action": "orders.reserve",
                "action_version": "1",
                "command": {},
            },
        )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "authorization_denied"
