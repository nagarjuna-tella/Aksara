"""Execution boundaries for Durable Authorized Operations."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from aksara.db import Database, atomic
from aksara.db.durable_guard import durable_database_guard
from aksara.durable.errors import (
    AmbiguousCommitOutcome,
    AtomicBoundaryViolation,
    DurableConfigurationError,
    OwnershipLost,
    ResolverNotRegistered,
)
from aksara.durable.registry import (
    DurableAction,
    ResolutionStatus,
)
from aksara.durable.service import (
    DurableOperationService,
    _principal_matches_reference,
    _tenant_context,
)
from aksara.durable.states import FailureReason, OperationEvent, OperationState
from aksara.durable.types import EffectClass, OperationClaim, OperationRecord
from aksara.security.policy import default_policy
from aksara.security.principal import Principal


@dataclass(frozen=True)
class PostgresAtomicExecutionContext:
    """Narrow application contract for one guarded PostgreSQL mutation.

    Database and ORM calls must use ``database`` from the owning asyncio task.
    Direct pool access, child-task database work and alternate Database
    instances invalidate the enclosing durable boundary.
    """

    database: Database
    operation_id: Any
    attempt_id: Any
    principal: Principal
    tenant_id: str | None
    fence: int


_PERMANENT_RESOLUTION_CODES = {
    ResolutionStatus.DELETED: FailureReason.PRINCIPAL_DELETED,
    ResolutionStatus.DISABLED: FailureReason.PRINCIPAL_DISABLED,
    ResolutionStatus.MEMBERSHIP_REMOVED: FailureReason.TENANT_MEMBERSHIP_REMOVED,
    ResolutionStatus.MALFORMED: FailureReason.MALFORMED_PROVENANCE,
    ResolutionStatus.REVOKED: FailureReason.IDENTITY_REVOKED,
}


class PostgresAtomicExecutor:
    """Execute one claimed same-database action and finalize in one commit."""

    def __init__(
        self,
        service: DurableOperationService,
        *,
        _boundary_hook: Callable[[str], None | Awaitable[None]] | None = None,
    ) -> None:
        self.service = service
        self._boundary_hook = _boundary_hook

    async def _at_boundary(self, name: str) -> None:
        """Invoke the private failure-campaign seam, when configured."""

        if self._boundary_hook is None:
            return
        result = self._boundary_hook(name)
        if inspect.isawaitable(result):
            await result

    async def execute(self, claim: OperationClaim) -> OperationRecord:
        action = self.service.actions.get(claim.action_name, claim.action_version)
        if action.effect_class is not EffectClass.POSTGRES_ATOMIC:
            raise DurableConfigurationError(
                f"{action.name}@{action.version} is {action.effect_class.value}, "
                "not postgres_atomic"
            )

        principal = await self._resolve_or_fail(claim)
        if principal is None:
            return await self._read_authoritative(claim)

        finalized_before_commit = False
        guard_state = None
        try:
            if not await self._authorize(action, principal, claim):
                await self.service.fail_attempt(
                    claim,
                    code=FailureReason.AUTHORIZATION_DENIED.value,
                    message="current authorization denied the durable action",
                    retryable=False,
                )
                return await self._read_authoritative(claim)
            with _tenant_context(claim.tenant_scope):
                async with atomic(db=self.service.db) as connection:
                    await self._at_boundary("before_lock")
                    operation = await self.service._lock_owned(connection, claim)
                    await self._at_boundary("after_lock")
                    if operation["cancellation_requested_at"] is not None:
                        return await self._cancel_under_lock(connection, operation, claim)
                    deadline_valid = await connection.fetchval(
                        "SELECT $1::timestamptz IS NULL OR $1 > clock_timestamp()",
                        operation["deadline_at"],
                    )
                    if not deadline_valid:
                        return await self._expire_under_lock(connection, operation, claim)
                    if operation["approval_required"] and operation["approval_consumed_at"] is None:
                        raise AtomicBoundaryViolation(
                            "required durable approval was not consumed by claim"
                        )

                    context = PostgresAtomicExecutionContext(
                        database=self.service.db,
                        operation_id=claim.operation_id,
                        attempt_id=claim.attempt_id,
                        principal=principal,
                        tenant_id=claim.tenant_id,
                        fence=claim.fence,
                    )
                    await self._at_boundary("before_mutation")
                    with durable_database_guard(self.service.db, connection) as guard:
                        guard_state = guard
                        result = action.handler(context, dict(claim.command))
                        if inspect.isawaitable(result):
                            result = await result
                        if guard.invalid_reason is not None:
                            raise AtomicBoundaryViolation(
                                "postgres_atomic boundary was invalidated: "
                                f"{guard.invalid_reason}"
                            )
                        normalized_result = action.normalize_result(result)
                    await self._at_boundary("after_mutation")

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
                        raise OwnershipLost("attempt success lost ownership")
                    await self._at_boundary("after_attempt_success")

                    version = int(operation["state_version"]) + 1
                    updated = await connection.fetchrow(
                        """
                        UPDATE aksara_operations
                        SET state = 'succeeded', state_version = $6,
                            result = $7::jsonb,
                            result_expires_at = clock_timestamp()
                                + ($9::double precision * INTERVAL '1 second'),
                            error = NULL, error_expires_at = NULL,
                            worker_id = NULL, lease_expires_at = NULL,
                            completed_at = clock_timestamp(), updated_at = clock_timestamp()
                        WHERE id = $1 AND tenant_scope = $2 AND state = 'running'
                          AND current_attempt_id = $3 AND fence = $4 AND worker_id = $5
                          AND application_namespace = $8
                          AND cancellation_requested_at IS NULL
                          AND (deadline_at IS NULL OR deadline_at > clock_timestamp())
                        RETURNING *
                        """,
                        claim.operation_id,
                        claim.tenant_scope,
                        claim.attempt_id,
                        claim.fence,
                        claim.worker_id,
                        version,
                        json.dumps(normalized_result),
                        self.service.application_namespace,
                        self.service.result_retention_seconds,
                    )
                    if updated is None:
                        raise OwnershipLost("operation success lost ownership")
                    await self._at_boundary("after_operation_success")
                    await self.service.repository.insert_transition(
                        connection,
                        operation_id=claim.operation_id,
                        tenant_scope=claim.tenant_scope,
                        state_version=version,
                        from_state=OperationState.RUNNING.value,
                        event=OperationEvent.SUCCEEDED.value,
                        to_state=OperationState.SUCCEEDED.value,
                        attempt_id=claim.attempt_id,
                    )
                    await self._at_boundary("before_commit")
                    finalized_before_commit = True
                    result_record = self.service.repository.public_operation(updated)
            return result_record
        except asyncio.CancelledError:
            await self._record_interrupted_cancellation(claim)
            raise
        except BaseException as exc:
            if finalized_before_commit:
                authoritative = await self._read_authoritative(claim)
                if authoritative.state is OperationState.SUCCEEDED:
                    return authoritative
                raise AmbiguousCommitOutcome(
                    "commit acknowledgement was ambiguous; authoritative operation "
                    f"state is {authoritative.state.value}"
                ) from exc
            if isinstance(exc, OwnershipLost):
                raise
            retryable = action.is_retryable(exc)
            code = (
                FailureReason.INTERNAL_ERROR.value
                if isinstance(exc, AtomicBoundaryViolation)
                or (guard_state is not None and guard_state.invalid_reason is not None)
                else FailureReason.EXECUTOR_ERROR.value
            )
            try:
                return await self.service.fail_attempt(
                    claim,
                    code=code,
                    message=str(exc) or type(exc).__name__,
                    retryable=retryable,
                )
            except OwnershipLost:
                raise exc

    async def _resolve_or_fail(self, claim: OperationClaim) -> Principal | None:
        try:
            outcome = await self.service.resolvers.resolve(claim.principal_reference)
        except ResolverNotRegistered as exc:
            await self.service.fail_attempt(
                claim,
                code=FailureReason.RESOLVER_MISSING.value,
                message=str(exc),
                retryable=False,
            )
            return None
        except Exception as exc:  # noqa: BLE001 - resolver failures are operation data
            await self.service.fail_attempt(
                claim,
                code=FailureReason.RESOLVER_UNAVAILABLE.value,
                message=str(exc) or "principal resolver unavailable",
                retryable=True,
            )
            return None

        if outcome.status is ResolutionStatus.TEMPORARILY_UNAVAILABLE:
            await self.service.fail_attempt(
                claim,
                code=FailureReason.RESOLVER_UNAVAILABLE.value,
                message=outcome.detail or "principal resolver temporarily unavailable",
                retryable=True,
            )
            return None
        if outcome.status is not ResolutionStatus.RESOLVED:
            reason = _PERMANENT_RESOLUTION_CODES[outcome.status]
            await self.service.fail_attempt(
                claim,
                code=reason.value,
                message=outcome.detail or reason.value,
                retryable=False,
            )
            return None
        principal = outcome.principal
        assert principal is not None
        if not self._matches_reference(principal, claim):
            await self.service.fail_attempt(
                claim,
                code=FailureReason.IDENTITY_REVOKED.value,
                message="resolved principal does not match durable identity provenance",
                retryable=False,
            )
            return None
        return principal

    @staticmethod
    def _matches_reference(principal: Principal, claim: OperationClaim) -> bool:
        return _principal_matches_reference(principal, claim.principal_reference)

    async def _authorize(
        self,
        action: DurableAction,
        principal: Principal,
        claim: OperationClaim,
    ) -> bool:
        decision = default_policy.can(
            principal,
            action.name,
            required_scopes=action.required_scopes,
            tenant_id=claim.tenant_id,
            tenant_required=claim.tenant_id is not None,
        )
        if decision.denied:
            return False
        if action.authorizer is None:
            return True
        from aksara.durable.service import _call_authorizer

        return await _call_authorizer(action.authorizer, principal, claim.command)

    async def _cancel_under_lock(
        self,
        connection: Any,
        operation: Mapping[str, Any],
        claim: OperationClaim,
    ) -> OperationRecord:
        version = int(operation["state_version"]) + 1
        await connection.execute(
            """
            UPDATE aksara_operation_attempts
            SET state = 'cancelled', completed_at = clock_timestamp(), retryable = FALSE,
                error_code = 'cancelled'
            WHERE id = $1 AND operation_id = $2 AND fence = $3
              AND worker_id = $4 AND state = 'running'
            """,
            claim.attempt_id,
            claim.operation_id,
            claim.fence,
            claim.worker_id,
        )
        updated = await connection.fetchrow(
            """
            UPDATE aksara_operations
            SET state = 'cancelled', state_version = $6,
                worker_id = NULL, lease_expires_at = NULL,
                completed_at = clock_timestamp(), updated_at = clock_timestamp()
            WHERE id = $1 AND tenant_scope = $2 AND state = 'running'
              AND current_attempt_id = $3 AND fence = $4 AND worker_id = $5
              AND application_namespace = $7
              AND cancellation_requested_at IS NOT NULL
            RETURNING *
            """,
            claim.operation_id,
            claim.tenant_scope,
            claim.attempt_id,
            claim.fence,
            claim.worker_id,
            version,
            self.service.application_namespace,
        )
        if updated is None:
            raise OwnershipLost("cancellation observation lost ownership")
        await self.service.repository.insert_transition(
            connection,
            operation_id=claim.operation_id,
            tenant_scope=claim.tenant_scope,
            state_version=version,
            from_state=OperationState.RUNNING.value,
            event=OperationEvent.CANCELLATION_OBSERVED.value,
            to_state=OperationState.CANCELLED.value,
            reason_code=FailureReason.CANCELLED.value,
            attempt_id=claim.attempt_id,
        )
        return self.service.repository.public_operation(updated)

    async def _expire_under_lock(
        self,
        connection: Any,
        operation: Mapping[str, Any],
        claim: OperationClaim,
    ) -> OperationRecord:
        version = int(operation["state_version"]) + 1
        await connection.execute(
            """
            UPDATE aksara_operation_attempts
            SET state = 'failed', completed_at = clock_timestamp(), retryable = FALSE,
                error_code = 'deadline_expired'
            WHERE id = $1 AND operation_id = $2 AND fence = $3
              AND worker_id = $4 AND state = 'running'
            """,
            claim.attempt_id,
            claim.operation_id,
            claim.fence,
            claim.worker_id,
        )
        error = {
            "category": "client",
            "code": FailureReason.DEADLINE_EXPIRED.value,
            "message": "operation deadline expired before its effect boundary",
            "retryable": False,
        }
        updated = await connection.fetchrow(
            """
            UPDATE aksara_operations
            SET state = 'expired', state_version = $6, error = $7::jsonb,
                error_expires_at = clock_timestamp()
                    + ($9::double precision * INTERVAL '1 second'),
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
            json.dumps(error),
            self.service.application_namespace,
            self.service.error_retention_seconds,
        )
        if updated is None:
            raise OwnershipLost("deadline expiration lost ownership")
        await self.service.repository.insert_transition(
            connection,
            operation_id=claim.operation_id,
            tenant_scope=claim.tenant_scope,
            state_version=version,
            from_state=OperationState.RUNNING.value,
            event=OperationEvent.DEADLINE_EXPIRED.value,
            to_state=OperationState.EXPIRED.value,
            reason_code=FailureReason.DEADLINE_EXPIRED.value,
            attempt_id=claim.attempt_id,
        )
        return self.service.repository.public_operation(updated)

    async def _record_interrupted_cancellation(self, claim: OperationClaim) -> None:
        async def record() -> None:
            try:
                await self.service.fail_attempt(
                    claim,
                    code=FailureReason.CANCELLED.value,
                    message="executor coroutine was cancelled before commit",
                    retryable=True,
                )
            except Exception:  # noqa: BLE001,S110 - best-effort recovery record
                # Ownership recovery remains authoritative if interruption also
                # prevents this best-effort attempt update.
                pass

        try:
            await asyncio.shield(record())
        except asyncio.CancelledError:
            pass

    async def _read_authoritative(self, claim: OperationClaim) -> OperationRecord:
        with _tenant_context(claim.tenant_scope):
            async with self.service.db.acquire() as connection:
                operation = await self.service.repository.get_public_operation(
                    connection,
                    claim.operation_id,
                    claim.tenant_scope,
                    self.service.application_namespace,
                )
        if operation is None:
            raise OwnershipLost("authoritative operation row is no longer available")
        return operation


class ReadOnlyExecutor:
    """Execute an allowlisted action inside a PostgreSQL read-only transaction."""

    def __init__(self, service: DurableOperationService) -> None:
        self.service = service
        self._identity = PostgresAtomicExecutor(service)

    async def execute(self, claim: OperationClaim) -> OperationRecord:
        action = self.service.actions.get(claim.action_name, claim.action_version)
        if action.effect_class is not EffectClass.READ_ONLY:
            raise DurableConfigurationError(
                f"{action.name}@{action.version} is not a read_only action"
            )
        principal = await self._identity._resolve_or_fail(claim)
        if principal is None:
            return await self._identity._read_authoritative(claim)
        try:
            if not await self._identity._authorize(action, principal, claim):
                return await self.service.fail_attempt(
                    claim,
                    code=FailureReason.AUTHORIZATION_DENIED.value,
                    message="current authorization denied the read-only action",
                    retryable=False,
                )
            with _tenant_context(claim.tenant_scope):
                async with atomic(db=self.service.db) as connection:
                    await connection.execute("SET TRANSACTION READ ONLY")
                    executable = await connection.fetchval(
                        """
                        SELECT EXISTS (
                            SELECT 1 FROM aksara_operations
                            WHERE id = $1 AND tenant_scope = $2 AND state = 'running'
                              AND current_attempt_id = $3 AND fence = $4
                              AND worker_id = $5 AND lease_expires_at > clock_timestamp()
                              AND application_namespace = $6
                              AND cancellation_requested_at IS NULL
                              AND (deadline_at IS NULL OR deadline_at > clock_timestamp())
                        )
                        """,
                        claim.operation_id,
                        claim.tenant_scope,
                        claim.attempt_id,
                        claim.fence,
                        claim.worker_id,
                        self.service.application_namespace,
                    )
                    if not executable:
                        break_for_lifecycle = True
                    else:
                        break_for_lifecycle = False
                    context = PostgresAtomicExecutionContext(
                        database=self.service.db,
                        operation_id=claim.operation_id,
                        attempt_id=claim.attempt_id,
                        principal=principal,
                        tenant_id=claim.tenant_id,
                        fence=claim.fence,
                    )
                    if not break_for_lifecycle:
                        with durable_database_guard(self.service.db, connection) as guard:
                            result = action.handler(context, dict(claim.command))
                            if inspect.isawaitable(result):
                                result = await result
                            if guard.invalid_reason is not None:
                                raise AtomicBoundaryViolation(
                                    "read_only boundary was invalidated: "
                                    f"{guard.invalid_reason}"
                                )
                            normalized = action.normalize_result(result)
            if break_for_lifecycle:
                with _tenant_context(claim.tenant_scope):
                    async with atomic(db=self.service.db) as connection:
                        operation = await self.service._lock_owned(connection, claim)
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
                raise OwnershipLost("read-only attempt is no longer executable")
            from aksara.durable.external import ExternalOperationExecutor

            return await ExternalOperationExecutor(self.service)._complete(
                claim,
                normalized,
                respect_lifecycle=True,
            )
        except Exception as exc:
            if isinstance(exc, OwnershipLost):
                raise
            return await self.service.fail_attempt(
                claim,
                code=FailureReason.EXECUTOR_ERROR.value,
                message=str(exc) or type(exc).__name__,
                retryable=action.is_retryable(exc),
            )


__all__ = [
    "PostgresAtomicExecutionContext",
    "PostgresAtomicExecutor",
    "ReadOnlyExecutor",
]
