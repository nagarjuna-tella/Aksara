"""Bounded pruning preserves active work and idempotency windows."""

from __future__ import annotations

from uuid import uuid4

import pytest

from aksara.durable import (
    DurableAction,
    DurableActionRegistry,
    DurableOperationService,
    EffectClass,
    OperationState,
    PrincipalReference,
    PrincipalResolution,
    PrincipalResolverRegistry,
    ReadOnlyExecutor,
)
from aksara.durable.service import _tenant_context
from aksara.durable.types import tenant_scope
from aksara.security.principal import Principal


def _runtime(durable_db, tenant: str):
    async def handler(_context, _command):
        return {"large": "result"}

    actions = DurableActionRegistry()
    actions.register(
        DurableAction(
            name="retention.read",
            version="1",
            handler=handler,
            effect_class=EffectClass.READ_ONLY,
        )
    )
    resolvers = PrincipalResolverRegistry()
    resolvers.register(
        "test",
        "1",
        lambda _reference: PrincipalResolution.resolved(
            Principal.for_user("user-1", tenant_id=tenant)
        ),
    )
    return DurableOperationService(
        durable_db,
        application_namespace="retention-tests",
        actions=actions,
        resolvers=resolvers,
        retention_seconds=60,
        idempotency_seconds=60,
        result_retention_seconds=1,
        error_retention_seconds=1,
    )


def _reference(tenant: str) -> PrincipalReference:
    return PrincipalReference(
        resolver_key="test",
        resolver_version="1",
        identity_namespace="tests",
        principal_kind="user",
        subject_id="user-1",
        tenant_id=tenant,
    )


@pytest.mark.asyncio
async def test_pruning_keeps_active_and_unexpired_idempotency_truth(durable_db):
    tenant = str(uuid4())
    service = _runtime(durable_db, tenant)
    active = await service.admit("retention.read", "1", {}, _reference(tenant))
    terminal = await service.admit(
        "retention.read",
        "1",
        {"terminal": True},
        _reference(tenant),
        idempotency_key="retained-key",
    )
    await service.request_cancellation(
        terminal.operation.id,
        tenant_id=tenant,
        principal=Principal.for_user("user-1", tenant_id=tenant),
        requester_reference=_reference(tenant),
    )
    scope = tenant_scope(tenant)
    with _tenant_context(scope):
        await durable_db.execute(
            "UPDATE aksara_operations SET retain_until = clock_timestamp() - INTERVAL '1 second'"
        )

    first = await service.prune(tenant_id=tenant, batch_size=10)
    assert first["operations"] == 0
    assert await service.get(
        active.operation.id,
        tenant_id=tenant,
        principal=Principal.for_user("user-1", tenant_id=tenant),
    )
    assert await service.get(
        terminal.operation.id,
        tenant_id=tenant,
        principal=Principal.for_user("user-1", tenant_id=tenant),
    )

    with _tenant_context(scope):
        await durable_db.execute(
            """
            UPDATE aksara_operation_idempotency
            SET expires_at = clock_timestamp() - INTERVAL '1 second'
            WHERE operation_id = $1
            """,
            terminal.operation.id,
        )
        await durable_db.execute(
            """
            UPDATE aksara_operation_outbox
            SET exported_at = clock_timestamp()
            WHERE operation_id = $1
            """,
            terminal.operation.id,
        )
    second = await service.prune(tenant_id=tenant, batch_size=10)
    assert second["operations"] == 1
    assert second["idempotency"] == 1
    remaining = await service.get(
        active.operation.id,
        tenant_id=tenant,
        principal=Principal.for_user("user-1", tenant_id=tenant),
    )
    assert remaining.state is OperationState.READY


@pytest.mark.asyncio
async def test_result_body_expires_before_terminal_operation_truth(durable_db):
    tenant = str(uuid4())
    service = _runtime(durable_db, tenant)
    admitted = await service.admit("retention.read", "1", {}, _reference(tenant))
    claim = await service.claim(
        tenant_id=tenant,
        worker_id="reader",
        operation_id=admitted.operation.id,
    )
    assert claim is not None
    completed = await ReadOnlyExecutor(service).execute(claim)
    assert completed.result == {"large": "result"}
    scope = tenant_scope(tenant)
    with _tenant_context(scope):
        await durable_db.execute(
            """
            UPDATE aksara_operations
            SET completed_at = clock_timestamp() - INTERVAL '2 seconds',
                result_expires_at = clock_timestamp() - INTERVAL '1 second'
            WHERE id = $1
            """,
            admitted.operation.id,
        )

    result = await service.prune(tenant_id=tenant, batch_size=10)

    assert result["results"] == 1
    retained = await service.get(
        admitted.operation.id,
        tenant_id=tenant,
        principal=Principal.for_user("user-1", tenant_id=tenant),
    )
    assert retained.state is OperationState.SUCCEEDED
    assert retained.result is None
