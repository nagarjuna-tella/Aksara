"""Transition export failure never changes authoritative operation state."""

from __future__ import annotations

from uuid import uuid4

import pytest

from aksara.durable import (
    DurableAction,
    DurableActionRegistry,
    DurableOperationService,
    DurableOutboxExporter,
    EffectClass,
    OperationState,
    PrincipalReference,
)
from aksara.security.principal import Principal


async def _handler(_context, command):
    return command


@pytest.mark.asyncio
async def test_outbox_retries_sink_failure_without_invalidating_operation(durable_db):
    tenant = str(uuid4())
    actions = DurableActionRegistry()
    actions.register(
        DurableAction(
            name="outbox.action",
            version="1",
            handler=_handler,
            effect_class=EffectClass.READ_ONLY,
        )
    )
    service = DurableOperationService(
        durable_db,
        application_namespace="outbox-tests",
        actions=actions,
        retention_seconds=60,
        idempotency_seconds=60,
    )
    admitted = await service.admit(
        "outbox.action",
        "1",
        {},
        PrincipalReference(
            resolver_key="test",
            resolver_version="1",
            identity_namespace="tests",
            principal_kind="user",
            subject_id="user-1",
            tenant_id=tenant,
        ),
    )
    calls = 0
    exported: list[dict] = []

    async def sink(payload):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("sink unavailable")
        exported.append(payload)

    exporter = DurableOutboxExporter(service, sink, retry_seconds=0)
    assert await exporter.export_once(tenant_id=tenant) is False
    operation = await service.get(
        admitted.operation.id,
        tenant_id=tenant,
        principal=Principal.for_user("user-1", tenant_id=tenant),
    )
    assert operation.state is OperationState.READY

    assert await exporter.export_once(tenant_id=tenant) is True
    assert exported[0]["operation_id"] == str(admitted.operation.id)
