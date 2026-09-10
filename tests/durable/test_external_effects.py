"""Deterministic external-effect recovery contracts."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest

from aksara.durable import (
    DurableAction,
    DurableActionRegistry,
    DurableOperationService,
    EffectClass,
    ExternalEffectResult,
    ExternalOperationExecutor,
    OperationState,
    PrincipalReference,
    PrincipalResolution,
    PrincipalResolverRegistry,
    ReconciliationResult,
    ReconciliationStatus,
)
from aksara.security.principal import Principal


class WorkerKilled(BaseException):
    pass


class IdempotentCrashOnceProvider:
    supports_idempotency = True
    supports_reconciliation = False

    def __init__(self) -> None:
        self.effects: dict[str, ExternalEffectResult] = {}
        self.calls = 0

    async def perform(self, request, *, idempotency_key):
        self.calls += 1
        result = self.effects.setdefault(
            idempotency_key,
            ExternalEffectResult(
                {"charged": request["amount"]},
                provider_reference="charge-1",
            ),
        )
        if self.calls == 1:
            raise WorkerKilled("worker died after provider accepted request")
        return result

    async def reconcile(self, **_kwargs):
        raise AssertionError("idempotent provider should retry with the same key")


class ReconcilingCrashOnceProvider:
    supports_idempotency = False
    supports_reconciliation = True

    def __init__(self) -> None:
        self.result: ExternalEffectResult | None = None
        self.perform_calls = 0
        self.reconcile_calls = 0

    async def perform(self, request, *, idempotency_key):
        self.perform_calls += 1
        self.result = ExternalEffectResult(
            {"sent": request["message"]},
            provider_reference=f"message:{idempotency_key[:12]}",
        )
        raise WorkerKilled("worker died after provider accepted request")

    async def reconcile(self, **_kwargs):
        self.reconcile_calls += 1
        assert self.result is not None
        return ReconciliationResult(ReconciliationStatus.CONFIRMED, self.result)


class AmbiguousProvider:
    supports_idempotency = False
    supports_reconciliation = False

    def __init__(self) -> None:
        self.calls = 0

    async def perform(self, _request, *, idempotency_key):
        self.calls += 1
        raise ConnectionError(f"response lost for {idempotency_key[:8]}")

    async def reconcile(self, **_kwargs):
        raise AssertionError("provider cannot reconcile")


def _reference(tenant: str) -> PrincipalReference:
    return PrincipalReference(
        resolver_key="test",
        resolver_version="1",
        identity_namespace="tests",
        principal_kind="user",
        subject_id="user-1",
        tenant_id=tenant,
    )


def _runtime(durable_db, tenant: str, provider: Any, effect_class: EffectClass):
    async def handler(context, command):
        return await context.perform("primary", 1, command, provider)

    actions = DurableActionRegistry()
    actions.register(
        DurableAction(
            name="external.perform",
            version="1",
            handler=handler,
            effect_class=effect_class,
            required_scopes=("external:write",),
        )
    )
    resolvers = PrincipalResolverRegistry()
    resolvers.register(
        "test",
        "1",
        lambda _reference: PrincipalResolution.resolved(
            Principal.for_user(
                "user-1",
                tenant_id=tenant,
                scopes=("external:write",),
            )
        ),
    )
    service = DurableOperationService(
        durable_db,
        application_namespace="external-tests",
        actions=actions,
        resolvers=resolvers,
        retention_seconds=60,
        idempotency_seconds=60,
    )
    return service, ExternalOperationExecutor(service)


async def _claim(service, tenant: str, command: dict[str, Any], *, lease=0.04):
    admitted = await service.admit(
        "external.perform", "1", command, _reference(tenant)
    )
    claim = await service.claim(
        tenant_id=tenant,
        worker_id="worker-a",
        operation_id=admitted.operation.id,
        lease_seconds=lease,
    )
    assert claim is not None
    return admitted, claim


@pytest.mark.asyncio
async def test_idempotent_provider_reuses_stable_key_after_worker_death(durable_db):
    tenant = str(uuid4())
    provider = IdempotentCrashOnceProvider()
    service, executor = _runtime(
        durable_db, tenant, provider, EffectClass.EXTERNAL_IDEMPOTENT
    )
    admitted, first = await _claim(service, tenant, {"amount": 25})

    with pytest.raises(WorkerKilled):
        await executor.execute(first)
    await asyncio.sleep(0.06)
    second = await service.claim(
        tenant_id=tenant,
        worker_id="worker-b",
        operation_id=admitted.operation.id,
    )
    assert second is not None

    completed = await executor.execute(second)

    assert completed.state is OperationState.SUCCEEDED
    assert completed.result == {"charged": 25}
    assert provider.calls == 2
    assert len(provider.effects) == 1


@pytest.mark.asyncio
async def test_reconciling_provider_does_not_repeat_effect_after_worker_death(durable_db):
    tenant = str(uuid4())
    provider = ReconcilingCrashOnceProvider()
    service, executor = _runtime(
        durable_db, tenant, provider, EffectClass.EXTERNAL_AT_LEAST_ONCE
    )
    admitted, first = await _claim(service, tenant, {"message": "hello"})

    with pytest.raises(WorkerKilled):
        await executor.execute(first)
    await asyncio.sleep(0.06)
    second = await service.claim(
        tenant_id=tenant,
        worker_id="worker-b",
        operation_id=admitted.operation.id,
    )
    assert second is not None

    completed = await executor.execute(second)

    assert completed.state is OperationState.SUCCEEDED
    assert completed.result == {"sent": "hello"}
    assert provider.perform_calls == 1
    assert provider.reconcile_calls == 1


@pytest.mark.asyncio
async def test_provider_without_recovery_records_unknown_and_never_blindly_retries(
    durable_db,
):
    tenant = str(uuid4())
    provider = AmbiguousProvider()
    service, executor = _runtime(
        durable_db, tenant, provider, EffectClass.EXTERNAL_NONRETRYABLE
    )
    _, claim = await _claim(service, tenant, {"amount": 25})

    completed = await executor.execute(claim)

    assert completed.state is OperationState.FAILED
    assert completed.error["code"] == "external_outcome_unknown"
    assert completed.error["retryable"] is False
    assert provider.calls == 1
