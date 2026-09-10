"""Explicit recovery semantics for non-PostgreSQL durable effects."""

from __future__ import annotations

import inspect
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol
from uuid import UUID

from aksara.db import atomic
from aksara.durable.errors import (
    AtomicBoundaryViolation,
    DurableConfigurationError,
    OwnershipLost,
)
from aksara.durable.execution import PostgresAtomicExecutor
from aksara.durable.service import DurableOperationService, _tenant_context
from aksara.durable.states import FailureReason, OperationEvent, OperationState
from aksara.durable.types import (
    EffectClass,
    OperationClaim,
    OperationRecord,
    normalize_json,
    stable_hash,
)


class ReconciliationStatus(str, Enum):
    CONFIRMED = "confirmed"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ExternalEffectResult:
    value: Any
    provider_reference: str | None = None


@dataclass(frozen=True)
class ReconciliationResult:
    status: ReconciliationStatus
    result: ExternalEffectResult | None = None

    def __post_init__(self) -> None:
        if self.status is ReconciliationStatus.CONFIRMED and self.result is None:
            raise ValueError("confirmed reconciliation requires a result")


class ExternalEffectAdapter(Protocol):
    """Provider adapter with explicit idempotency/reconciliation capability."""

    supports_idempotency: bool
    supports_reconciliation: bool

    async def perform(
        self,
        request: Mapping[str, Any],
        *,
        idempotency_key: str,
    ) -> ExternalEffectResult: ...

    async def reconcile(
        self,
        *,
        idempotency_key: str,
        provider_reference: str | None,
    ) -> ReconciliationResult: ...


class ExternalOutcomeUnknown(RuntimeError):
    """The provider outcome cannot be established without risking duplication."""


class _OperationClosed(RuntimeError):
    pass


class ExternalEffectContext:
    """The only supported network-effect path for an external durable action."""

    def __init__(
        self,
        executor: ExternalOperationExecutor,
        claim: OperationClaim,
    ) -> None:
        self._executor = executor
        self.claim = claim

    @property
    def operation_id(self) -> UUID:
        return self.claim.operation_id

    @property
    def tenant_id(self) -> str | None:
        return self.claim.tenant_id

    async def perform(
        self,
        effect_name: str,
        ordinal: int,
        request: Mapping[str, Any],
        adapter: ExternalEffectAdapter,
    ) -> Any:
        """Persist intent, call or reconcile the provider, then confirm."""

        if not effect_name or ordinal < 1:
            raise ValueError("effect_name and a positive ordinal are required")
        normalized_request = normalize_json(dict(request))
        request_hash = stable_hash(normalized_request)
        downstream_key = stable_hash(
            {
                "operation_id": str(self.claim.operation_id),
                "effect_name": effect_name,
                "ordinal": ordinal,
            }
        )

        principal = await self._executor._identity._resolve_or_fail(self.claim)
        if principal is None:
            raise _OperationClosed("current principal could not be established")
        action = self._executor.service.actions.get(
            self.claim.action_name, self.claim.action_version
        )
        if not await self._executor._identity._authorize(action, principal, self.claim):
            await self._executor.service.fail_attempt(
                self.claim,
                code=FailureReason.AUTHORIZATION_DENIED.value,
                message="current authorization denied the external effect",
                retryable=False,
            )
            raise _OperationClosed("current authorization denied the external effect")

        effect = await self._record_or_load_intent(
            effect_name,
            ordinal,
            request_hash,
            downstream_key,
        )
        await self._executor._reach_boundary("after_effect_intent")
        state = effect["state"]
        if state == "confirmed":
            response = effect["response"]
            return json.loads(response) if isinstance(response, str) else response
        if state == "outcome_unknown":
            raise ExternalOutcomeUnknown("external effect outcome is already unknown")

        is_recovery = int(effect["execution_count"]) > 0
        if is_recovery and not adapter.supports_idempotency:
            if adapter.supports_reconciliation:
                await self._executor._reach_boundary("before_reconciliation")
                reconciliation = await adapter.reconcile(
                    idempotency_key=downstream_key,
                    provider_reference=effect["provider_reference"],
                )
                await self._executor._reach_boundary("after_reconciliation")
                if reconciliation.status is ReconciliationStatus.CONFIRMED:
                    assert reconciliation.result is not None
                    await self._confirm(
                        effect["id"],
                        reconciliation.result,
                    )
                    return normalize_json(reconciliation.result.value)
                if reconciliation.status is ReconciliationStatus.UNKNOWN:
                    await self._mark_unknown(
                        effect["id"], "provider reconciliation was inconclusive"
                    )
                    raise ExternalOutcomeUnknown(
                        "provider reconciliation could not establish the external outcome"
                    )
            else:
                await self._mark_unknown(
                    effect["id"], "provider supports neither idempotency nor reconciliation"
                )
                raise ExternalOutcomeUnknown(
                    "external outcome cannot be reconciled and will not be blindly retried"
                )

        await self._mark_execution_started(effect["id"])
        await self._executor._reach_boundary("before_external_send")
        try:
            performed: Any = adapter.perform(
                normalized_request,
                idempotency_key=downstream_key,
            )
            if inspect.isawaitable(performed):
                performed = await performed
            result = (
                performed
                if isinstance(performed, ExternalEffectResult)
                else ExternalEffectResult(performed)
            )
        except Exception as exc:
            if not adapter.supports_idempotency and not adapter.supports_reconciliation:
                await self._mark_unknown(effect["id"], str(exc) or type(exc).__name__)
                raise ExternalOutcomeUnknown(
                    "external provider failed without a safe recovery mechanism"
                ) from exc
            raise
        await self._executor._reach_boundary("after_external_send")
        await self._confirm(effect["id"], result)
        await self._executor._reach_boundary("after_effect_confirmation")
        return normalize_json(result.value)

    async def _record_or_load_intent(
        self,
        effect_name: str,
        ordinal: int,
        request_hash: str,
        downstream_key: str,
    ) -> Any:
        with _tenant_context(self.claim.tenant_scope):
            async with atomic(db=self._executor.service.db) as connection:
                operation = await self._executor.service._lock_owned(connection, self.claim)
                if operation["cancellation_requested_at"] is not None:
                    await self._executor._identity._cancel_under_lock(
                        connection, operation, self.claim
                    )
                    raise _OperationClosed("cancellation won before the external effect")
                deadline_valid = await connection.fetchval(
                    "SELECT $1::timestamptz IS NULL OR $1 > clock_timestamp()",
                    operation["deadline_at"],
                )
                if not deadline_valid:
                    await self._executor._identity._expire_under_lock(
                        connection, operation, self.claim
                    )
                    raise _OperationClosed("deadline expired before the external effect")
                effect = await connection.fetchrow(
                    """
                    SELECT * FROM aksara_operation_effects
                    WHERE operation_id = $1 AND tenant_scope = $2
                      AND effect_name = $3 AND ordinal = $4
                    FOR UPDATE
                    """,
                    self.claim.operation_id,
                    self.claim.tenant_scope,
                    effect_name,
                    ordinal,
                )
                if effect is not None:
                    if effect["request_hash"] != request_hash:
                        raise AtomicBoundaryViolation(
                            "external effect identity was reused with different semantic input"
                        )
                    return effect
                return await connection.fetchrow(
                    """
                    INSERT INTO aksara_operation_effects (
                        operation_id, tenant_scope, effect_name, ordinal, effect_class,
                        state, request_hash, downstream_idempotency_key,
                        last_attempt_id, last_fence
                    ) VALUES (
                        $1, $2, $3, $4, $5, 'intent_recorded', $6, $7, $8, $9
                    ) RETURNING *
                    """,
                    self.claim.operation_id,
                    self.claim.tenant_scope,
                    effect_name,
                    ordinal,
                    self.claim.effect_class.value,
                    request_hash,
                    downstream_key,
                    self.claim.attempt_id,
                    self.claim.fence,
                )

    async def _mark_execution_started(self, effect_id: UUID) -> None:
        with _tenant_context(self.claim.tenant_scope):
            async with atomic(db=self._executor.service.db) as connection:
                await self._executor.service._lock_owned(connection, self.claim)
                status = await connection.execute(
                    """
                    UPDATE aksara_operation_effects
                    SET execution_count = execution_count + 1,
                        last_attempt_id = $2, last_fence = $3,
                        updated_at = clock_timestamp()
                    WHERE id = $1 AND operation_id = $4 AND tenant_scope = $5
                      AND state = 'intent_recorded'
                    """,
                    effect_id,
                    self.claim.attempt_id,
                    self.claim.fence,
                    self.claim.operation_id,
                    self.claim.tenant_scope,
                )
                if status != "UPDATE 1":
                    raise OwnershipLost("external effect intent is no longer executable")

    async def _confirm(self, effect_id: UUID, result: ExternalEffectResult) -> None:
        normalized = normalize_json(result.value)
        with _tenant_context(self.claim.tenant_scope):
            async with atomic(db=self._executor.service.db) as connection:
                await self._executor.service._lock_owned(connection, self.claim)
                status = await connection.execute(
                    """
                    UPDATE aksara_operation_effects
                    SET state = 'confirmed', response = $2::jsonb,
                        provider_reference = $3, last_attempt_id = $4, last_fence = $5,
                        confirmed_at = clock_timestamp(), updated_at = clock_timestamp()
                    WHERE id = $1 AND operation_id = $6 AND tenant_scope = $7
                      AND state = 'intent_recorded'
                    """,
                    effect_id,
                    json.dumps(normalized),
                    result.provider_reference,
                    self.claim.attempt_id,
                    self.claim.fence,
                    self.claim.operation_id,
                    self.claim.tenant_scope,
                )
                if status != "UPDATE 1":
                    raise OwnershipLost("external effect confirmation lost ownership")

    async def _mark_unknown(self, effect_id: UUID, message: str) -> None:
        error = {
            "category": "external",
            "code": FailureReason.EXTERNAL_OUTCOME_UNKNOWN.value,
            "message": message[:2000],
            "retryable": False,
        }
        with _tenant_context(self.claim.tenant_scope):
            async with atomic(db=self._executor.service.db) as connection:
                await self._executor.service._lock_owned(connection, self.claim)
                await connection.execute(
                    """
                    UPDATE aksara_operation_effects
                    SET state = 'outcome_unknown', error = $2::jsonb,
                        last_attempt_id = $3, last_fence = $4,
                        updated_at = clock_timestamp()
                    WHERE id = $1 AND operation_id = $5 AND tenant_scope = $6
                      AND state = 'intent_recorded'
                    """,
                    effect_id,
                    json.dumps(error),
                    self.claim.attempt_id,
                    self.claim.fence,
                    self.claim.operation_id,
                    self.claim.tenant_scope,
                )


class ExternalOperationExecutor:
    """Execute actions whose effects cannot share PostgreSQL's transaction."""

    def __init__(
        self,
        service: DurableOperationService,
        *,
        _boundary_hook: Any | None = None,
    ) -> None:
        self.service = service
        self._identity = PostgresAtomicExecutor(service)
        self._boundary_hook = _boundary_hook

    async def _reach_boundary(self, name: str) -> None:
        """Invoke the private deterministic crash-test seam when configured."""

        if self._boundary_hook is None:
            return
        result = self._boundary_hook(name)
        if inspect.isawaitable(result):
            await result

    async def execute(self, claim: OperationClaim) -> OperationRecord:
        action = self.service.actions.get(claim.action_name, claim.action_version)
        if action.effect_class not in {
            EffectClass.EXTERNAL_IDEMPOTENT,
            EffectClass.EXTERNAL_AT_LEAST_ONCE,
            EffectClass.EXTERNAL_NONRETRYABLE,
        }:
            raise DurableConfigurationError(
                f"{action.name}@{action.version} is not an external effect action"
            )
        principal = await self._identity._resolve_or_fail(claim)
        if principal is None:
            return await self._identity._read_authoritative(claim)

        context = ExternalEffectContext(self, claim)
        try:
            if not await self._identity._authorize(action, principal, claim):
                return await self.service.fail_attempt(
                    claim,
                    code=FailureReason.AUTHORIZATION_DENIED.value,
                    message="current authorization denied the durable action",
                    retryable=False,
                )
            result = action.handler(context, dict(claim.command))
            if inspect.isawaitable(result):
                result = await result
            normalized = action.normalize_result(result)
            return await self._complete(claim, normalized)
        except _OperationClosed:
            return await self._identity._read_authoritative(claim)
        except ExternalOutcomeUnknown as exc:
            return await self.service.fail_attempt(
                claim,
                code=FailureReason.EXTERNAL_OUTCOME_UNKNOWN.value,
                message=str(exc),
                retryable=False,
            )
        except Exception as exc:  # noqa: BLE001 - handlers define application failures
            retryable = action.is_retryable(exc)
            if action.effect_class is EffectClass.EXTERNAL_IDEMPOTENT:
                retryable = True
            return await self.service.fail_attempt(
                claim,
                code=FailureReason.EXECUTOR_ERROR.value,
                message=str(exc) or type(exc).__name__,
                retryable=retryable,
            )

    async def _complete(
        self,
        claim: OperationClaim,
        result: Any,
        *,
        respect_lifecycle: bool = False,
    ) -> OperationRecord:
        with _tenant_context(claim.tenant_scope):
            async with atomic(db=self.service.db) as connection:
                operation = await self.service._lock_owned(connection, claim)
                if respect_lifecycle:
                    if operation["cancellation_requested_at"] is not None:
                        return await self._identity._cancel_under_lock(
                            connection, operation, claim
                        )
                    deadline_valid = await connection.fetchval(
                        "SELECT $1::timestamptz IS NULL OR $1 > clock_timestamp()",
                        operation["deadline_at"],
                    )
                    if not deadline_valid:
                        return await self._identity._expire_under_lock(
                            connection, operation, claim
                        )
                attempt_status = await connection.execute(
                    """
                    UPDATE aksara_operation_attempts
                    SET state = 'succeeded', completed_at = clock_timestamp(),
                        retryable = FALSE, error_code = NULL, error = NULL
                    WHERE id = $1 AND operation_id = $2 AND tenant_scope = $3
                      AND fence = $4 AND worker_id = $5 AND state = 'running'
                    """,
                    claim.attempt_id,
                    claim.operation_id,
                    claim.tenant_scope,
                    claim.fence,
                    claim.worker_id,
                )
                if attempt_status != "UPDATE 1":
                    raise OwnershipLost("external attempt success lost ownership")
                version = int(operation["state_version"]) + 1
                updated = await connection.fetchrow(
                    """
                    UPDATE aksara_operations
                    SET state = 'succeeded', state_version = $6, result = $7::jsonb,
                        result_expires_at = clock_timestamp()
                            + ($9::double precision * INTERVAL '1 second'),
                        error = NULL, error_expires_at = NULL,
                        worker_id = NULL, lease_expires_at = NULL,
                        completed_at = clock_timestamp(), updated_at = clock_timestamp()
                    WHERE id = $1 AND tenant_scope = $2 AND state = 'running'
                      AND current_attempt_id = $3 AND fence = $4 AND worker_id = $5
                      AND application_namespace = $8
                    RETURNING *
                    """,
                    claim.operation_id,
                    claim.tenant_scope,
                    claim.attempt_id,
                    claim.fence,
                    claim.worker_id,
                    version,
                    json.dumps(result),
                    self.service.application_namespace,
                    self.service.result_retention_seconds,
                )
                if updated is None:
                    raise OwnershipLost("external operation success lost ownership")
                await self.service.repository.insert_transition(
                    connection,
                    operation_id=claim.operation_id,
                    tenant_scope=claim.tenant_scope,
                    state_version=version,
                    from_state=OperationState.RUNNING.value,
                    event=OperationEvent.SUCCEEDED.value,
                    to_state=OperationState.SUCCEEDED.value,
                    attempt_id=claim.attempt_id,
                    metadata={"effect_class": claim.effect_class.value},
                )
                return self.service.repository.public_operation(updated)


__all__ = [
    "ExternalEffectAdapter",
    "ExternalEffectContext",
    "ExternalEffectResult",
    "ExternalOperationExecutor",
    "ExternalOutcomeUnknown",
    "ReconciliationResult",
    "ReconciliationStatus",
]
