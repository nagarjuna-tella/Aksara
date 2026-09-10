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
from aksara.durable.service import _tenant_context
from aksara.durable.types import tenant_scope
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


class RecordingIdempotentProvider:
    supports_idempotency = True
    supports_reconciliation = False

    def __init__(self, *, fail_first: bool = False) -> None:
        self.fail_first = fail_first
        self.calls: list[str] = []
        self.effects: dict[str, ExternalEffectResult] = {}

    async def perform(self, request, *, idempotency_key):
        self.calls.append(idempotency_key)
        if self.fail_first and len(self.calls) == 1:
            raise ConnectionError("transient provider failure")
        return self.effects.setdefault(
            idempotency_key,
            ExternalEffectResult(
                {"charged": request["amount"]},
                provider_reference="stable-charge",
            ),
        )

    async def reconcile(self, **_kwargs):
        raise AssertionError("idempotent provider should not reconcile")


class FlakyReconciliationProvider:
    supports_idempotency = False
    supports_reconciliation = True

    def __init__(self) -> None:
        self.perform_calls = 0
        self.reconcile_calls = 0
        self.result = ExternalEffectResult(
            {"sent": "hello"}, provider_reference="message-1"
        )

    async def perform(self, _request, *, idempotency_key):
        self.perform_calls += 1
        raise WorkerKilled(f"lost response for {idempotency_key[:8]}")

    async def reconcile(self, **_kwargs):
        self.reconcile_calls += 1
        if self.reconcile_calls == 1:
            raise ConnectionError("reconciliation service unavailable")
        return ReconciliationResult(ReconciliationStatus.CONFIRMED, self.result)


def _reference(tenant: str) -> PrincipalReference:
    return PrincipalReference(
        resolver_key="test",
        resolver_version="1",
        identity_namespace="tests",
        principal_kind="user",
        subject_id="user-1",
        tenant_id=tenant,
    )


def _runtime(
    durable_db,
    tenant: str,
    provider: Any,
    effect_class: EffectClass,
    *,
    retry_classifier=None,
    boundary_hook=None,
):
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
            retry_classifier=retry_classifier,
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
    return service, ExternalOperationExecutor(service, _boundary_hook=boundary_hook)


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


@pytest.mark.asyncio
async def test_death_after_intent_before_send_reuses_stable_effect_identity(durable_db):
    tenant = str(uuid4())
    provider = RecordingIdempotentProvider()
    killed = False

    async def boundary(name):
        nonlocal killed
        if name == "before_external_send" and not killed:
            killed = True
            raise WorkerKilled("worker died after durable intent and before send")

    service, executor = _runtime(
        durable_db,
        tenant,
        provider,
        EffectClass.EXTERNAL_IDEMPOTENT,
        boundary_hook=boundary,
    )
    admitted, first = await _claim(service, tenant, {"amount": 25})

    with pytest.raises(WorkerKilled):
        await executor.execute(first)
    assert provider.calls == []
    await asyncio.sleep(0.06)
    second = await service.claim(
        tenant_id=tenant,
        worker_id="worker-b",
        operation_id=admitted.operation.id,
    )
    assert second is not None

    completed = await executor.execute(second)

    assert completed.state is OperationState.SUCCEEDED
    assert len(provider.calls) == 1
    with _tenant_context(tenant_scope(tenant)):
        effect = await durable_db.fetchrow(
            """
            SELECT execution_count, downstream_idempotency_key
            FROM aksara_operation_effects WHERE operation_id = $1
            """,
            admitted.operation.id,
        )
    assert effect["execution_count"] == 2
    assert effect["downstream_idempotency_key"] == provider.calls[0]


@pytest.mark.asyncio
async def test_death_after_send_before_confirmation_deduplicates_provider_effect(durable_db):
    tenant = str(uuid4())
    provider = RecordingIdempotentProvider()
    killed = False

    async def boundary(name):
        nonlocal killed
        if name == "after_external_send" and not killed:
            killed = True
            raise WorkerKilled("worker died after send and before local confirmation")

    service, executor = _runtime(
        durable_db,
        tenant,
        provider,
        EffectClass.EXTERNAL_IDEMPOTENT,
        boundary_hook=boundary,
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
    assert len(provider.calls) == 2
    assert provider.calls[0] == provider.calls[1]
    assert len(provider.effects) == 1


@pytest.mark.asyncio
async def test_transient_reconciliation_failure_retries_without_resending(durable_db):
    tenant = str(uuid4())
    provider = FlakyReconciliationProvider()
    service, executor = _runtime(
        durable_db,
        tenant,
        provider,
        EffectClass.EXTERNAL_AT_LEAST_ONCE,
        retry_classifier=lambda error: isinstance(error, ConnectionError),
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
    retry = await executor.execute(second)
    assert retry.state is OperationState.READY

    third = await service.claim(
        tenant_id=tenant,
        worker_id="worker-c",
        operation_id=admitted.operation.id,
    )
    assert third is not None
    completed = await executor.execute(third)

    assert completed.state is OperationState.SUCCEEDED
    assert provider.perform_calls == 1
    assert provider.reconcile_calls == 2


@pytest.mark.asyncio
async def test_idempotent_provider_retry_uses_same_key_after_transient_failure(durable_db):
    tenant = str(uuid4())
    provider = RecordingIdempotentProvider(fail_first=True)
    service, executor = _runtime(
        durable_db,
        tenant,
        provider,
        EffectClass.EXTERNAL_IDEMPOTENT,
    )
    admitted, first = await _claim(service, tenant, {"amount": 25}, lease=1)

    retry = await executor.execute(first)
    assert retry.state is OperationState.READY
    second = await service.claim(
        tenant_id=tenant,
        worker_id="worker-b",
        operation_id=admitted.operation.id,
    )
    assert second is not None
    completed = await executor.execute(second)

    assert completed.state is OperationState.SUCCEEDED
    assert len(provider.calls) == 2
    assert provider.calls[0] == provider.calls[1]
