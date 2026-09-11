"""Restricted-role tenant isolation and durable-state abuse invariants."""

from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

import pytest

from aksara.context_state import tenant_id_var
from aksara.durable import (
    DurableAction,
    DurableActionRegistry,
    DurableOperationService,
    EffectClass,
    OperationNotFound,
    OperationState,
    PrincipalReference,
)
from aksara.durable.service import _tenant_context
from aksara.security.principal import Principal


@contextmanager
def _no_tenant():
    token = tenant_id_var.set(None)
    try:
        yield
    finally:
        tenant_id_var.reset(token)


def _reference(tenant: str) -> PrincipalReference:
    return PrincipalReference(
        resolver_key="security",
        resolver_version="1",
        identity_namespace="tests",
        principal_kind="user",
        subject_id="user-1",
        tenant_id=tenant,
    )


def _principal(tenant: str) -> Principal:
    return Principal.for_user("user-1", tenant_id=tenant)


def _service(durable_db):
    async def handler(_context, command):
        return command

    actions = DurableActionRegistry()
    actions.register(
        DurableAction(
            name="security.noop",
            version="1",
            handler=handler,
            effect_class=EffectClass.READ_ONLY,
        )
    )
    return DurableOperationService(
        durable_db,
        application_namespace="security-tests",
        actions=actions,
        retention_seconds=60,
        idempotency_seconds=60,
    )


@pytest.mark.asyncio
async def test_forced_rls_survives_two_tenants_and_pool_reuse(durable_db):
    tenant_a, tenant_b = str(uuid4()), str(uuid4())
    service = _service(durable_db)
    operation_a = await service.admit(
        "security.noop", "1", {"tenant": "a"}, _reference(tenant_a)
    )
    operation_b = await service.admit(
        "security.noop", "1", {"tenant": "b"}, _reference(tenant_b)
    )

    for _ in range(12):
        with _tenant_context(tenant_a):
            visible_a = await durable_db.fetch(
                "SELECT id, tenant_scope FROM aksara_operations ORDER BY id"
            )
        with _tenant_context(tenant_b):
            visible_b = await durable_db.fetch(
                "SELECT id, tenant_scope FROM aksara_operations ORDER BY id"
            )
        assert {(row["id"], row["tenant_scope"]) for row in visible_a} == {
            (operation_a.operation.id, tenant_a)
        }
        assert {(row["id"], row["tenant_scope"]) for row in visible_b} == {
            (operation_b.operation.id, tenant_b)
        }

    with _no_tenant():
        assert await durable_db.fetchval("SELECT COUNT(*) FROM aksara_operations") == 0


@pytest.mark.asyncio
async def test_cross_tenant_read_cancel_history_outbox_and_write_are_hidden(durable_db):
    tenant_a, tenant_b = str(uuid4()), str(uuid4())
    service = _service(durable_db)
    admitted = await service.admit(
        "security.noop", "1", {}, _reference(tenant_a)
    )

    with pytest.raises(OperationNotFound):
        await service.get(
            admitted.operation.id,
            tenant_id=tenant_b,
            principal=_principal(tenant_b),
        )
    with pytest.raises(OperationNotFound):
        await service.history(
            admitted.operation.id,
            tenant_id=tenant_b,
            principal=_principal(tenant_b),
        )
    with pytest.raises(OperationNotFound):
        await service.request_cancellation(
            admitted.operation.id,
            tenant_id=tenant_b,
            principal=_principal(tenant_b),
            requester_reference=_reference(tenant_b),
        )
    assert await service.pending_outbox(
        tenant_id=tenant_b,
        principal=Principal.system(tenant_id=tenant_b),
    ) == []
    with _tenant_context(tenant_b):
        status = await durable_db.execute(
            "UPDATE aksara_operations SET state_version = state_version + 1 WHERE id = $1",
            admitted.operation.id,
        )
    assert status == "UPDATE 0"


@pytest.mark.asyncio
async def test_transition_or_outbox_tampering_cannot_rewrite_operation_truth(durable_db):
    tenant = str(uuid4())
    service = _service(durable_db)
    admitted = await service.admit(
        "security.noop", "1", {"value": 1}, _reference(tenant)
    )
    with _tenant_context(tenant):
        await durable_db.execute(
            """
            UPDATE aksara_operation_transitions
            SET event = 'succeeded', to_state = 'succeeded'
            WHERE operation_id = $1
            """,
            admitted.operation.id,
        )
        await durable_db.execute(
            "DELETE FROM aksara_operation_outbox WHERE operation_id = $1",
            admitted.operation.id,
        )

    operation = await service.get(
        admitted.operation.id,
        tenant_id=tenant,
        principal=_principal(tenant),
    )
    assert operation.state is OperationState.READY
    assert await service.pending_outbox(
        tenant_id=tenant,
        principal=Principal.system(tenant_id=tenant),
    ) == []
