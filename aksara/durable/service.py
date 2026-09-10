"""Durable operation admission, ownership and lifecycle services."""

from __future__ import annotations

import json
from collections.abc import Mapping
from contextlib import contextmanager
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from aksara.context_state import tenant_id_var
from aksara.db import Database, atomic
from aksara.durable.errors import (
    ApprovalConflict,
    AuthorizationDenied,
    CancellationConflict,
    IdempotencyConflict,
    IdempotencyIdentityExpired,
    OperationNotFound,
    OwnershipLost,
)
from aksara.durable.registry import (
    DurableAction,
    DurableActionRegistry,
    PrincipalResolverRegistry,
    default_action_registry,
    default_principal_resolver_registry,
)
from aksara.durable.repository import DurableOperationRepository
from aksara.durable.states import (
    FailureReason,
    OperationEvent,
    OperationState,
    TERMINAL_OPERATION_STATES,
)
from aksara.durable.types import (
    OperationAdmission,
    OperationClaim,
    OperationRecord,
    OutboxRecord,
    PrincipalReference,
    TransitionRecord,
    stable_hash,
    tenant_scope,
)
from aksara.security.policy import default_policy
from aksara.security.principal import Principal


DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_LEASE_SECONDS = 30.0
DEFAULT_RETENTION_SECONDS = 7 * 24 * 60 * 60
DEFAULT_IDEMPOTENCY_SECONDS = 24 * 60 * 60
DEFAULT_APPROVAL_SECONDS = 24 * 60 * 60
MAX_HISTORY_PAGE = 200
MAX_OUTBOX_PAGE = 500


@contextmanager
def _tenant_context(scope: str):
    token = tenant_id_var.set(scope)
    try:
        yield
    finally:
        tenant_id_var.reset(token)


async def _call_authorizer(
    authorizer: Any,
    principal: Principal,
    command: Mapping[str, Any],
) -> bool:
    import inspect

    decision = authorizer(principal, command)
    if inspect.isawaitable(decision):
        decision = await decision
    if hasattr(decision, "allowed"):
        return bool(decision.allowed)
    return bool(decision)


def _error_envelope(code: str, detail: str, *, retryable: bool) -> dict[str, Any]:
    return {
        "category": "transient" if retryable else "authorization"
        if code.startswith("authorization")
        else "internal",
        "code": code,
        "message": detail[:2000],
        "retryable": retryable,
    }


class DurableOperationService:
    """Application-facing semantic service for durable operations."""

    def __init__(
        self,
        db: Database,
        *,
        application_namespace: str,
        actions: DurableActionRegistry | None = None,
        resolvers: PrincipalResolverRegistry | None = None,
        repository: DurableOperationRepository | None = None,
        default_max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        default_lease_seconds: float = DEFAULT_LEASE_SECONDS,
        retention_seconds: float = DEFAULT_RETENTION_SECONDS,
        idempotency_seconds: float = DEFAULT_IDEMPOTENCY_SECONDS,
    ) -> None:
        if not application_namespace:
            raise ValueError("application_namespace is required")
        if default_max_attempts < 1:
            raise ValueError("default_max_attempts must be positive")
        if default_lease_seconds <= 0:
            raise ValueError("default_lease_seconds must be positive")
        if retention_seconds <= 0 or idempotency_seconds <= 0:
            raise ValueError("retention windows must be positive")
        self.db = db
        self.application_namespace = application_namespace
        self.actions = actions or default_action_registry
        self.resolvers = resolvers or default_principal_resolver_registry
        self.repository = repository or DurableOperationRepository()
        self.default_max_attempts = default_max_attempts
        self.default_lease_seconds = default_lease_seconds
        self.retention_seconds = retention_seconds
        self.idempotency_seconds = idempotency_seconds

    async def admit(
        self,
        action_name: str,
        action_version: str,
        command: Mapping[str, Any],
        principal_reference: PrincipalReference,
        *,
        idempotency_key: str | None = None,
        available_at: datetime | None = None,
        deadline_at: datetime | None = None,
        max_attempts: int | None = None,
        correlation: Mapping[str, Any] | None = None,
        approval_expires_at: datetime | None = None,
    ) -> OperationAdmission:
        """Create or resolve one logical operation atomically."""

        action = self.actions.get(action_name, action_version)
        normalized = action.normalize_command(command)
        input_hash = stable_hash(normalized)
        scope = tenant_scope(principal_reference.tenant_id)
        attempts = max_attempts or self.default_max_attempts
        if attempts < 1:
            raise ValueError("max_attempts must be positive")
        if idempotency_key is not None and not idempotency_key:
            raise ValueError("idempotency_key cannot be empty")

        identity_hash: str | None = None
        semantic_scope_hash: str | None = None
        if idempotency_key is not None:
            identity_hash = stable_hash(
                {
                    "application_namespace": self.application_namespace,
                    "tenant_scope": scope,
                    "principal_reference_hash": principal_reference.integrity_hash,
                    "client_key": idempotency_key,
                }
            )
            semantic_scope_hash = stable_hash(
                {
                    "application_namespace": self.application_namespace,
                    "tenant_scope": scope,
                    "principal_reference_hash": principal_reference.integrity_hash,
                    "action": action.name,
                    "action_version": action.version,
                    "client_key": idempotency_key,
                }
            )

        operation_id = uuid4()
        command_id = uuid4()
        initial_state = (
            OperationState.WAITING_FOR_APPROVAL
            if action.approval_required
            else OperationState.READY
        )
        correlation_json = json.dumps(dict(correlation or {}))

        with _tenant_context(scope):
            async with atomic(db=self.db) as connection:
                if identity_hash is not None:
                    inserted = await connection.fetchval(
                        """
                        INSERT INTO aksara_operation_idempotency (
                            identity_hash, scope_hash, tenant_scope, operation_id,
                            action_name, action_version, canonical_input_hash, expires_at
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7,
                            clock_timestamp() + ($8::double precision * INTERVAL '1 second')
                        )
                        ON CONFLICT (identity_hash) DO NOTHING
                        RETURNING operation_id
                        """,
                        identity_hash,
                        semantic_scope_hash,
                        scope,
                        operation_id,
                        action.name,
                        action.version,
                        input_hash,
                        self.idempotency_seconds,
                    )
                    if inserted is None:
                        return await self._resolve_duplicate(
                            connection,
                            identity_hash=identity_hash,
                            semantic_scope_hash=semantic_scope_hash,
                            action=action,
                            input_hash=input_hash,
                            scope=scope,
                        )

                await connection.execute(
                    """
                    INSERT INTO aksara_operations (
                        id, application_namespace, tenant_id, tenant_scope,
                        action_name, action_version, executor_type, effect_class,
                        command_id, resolver_key, resolver_version, principal_reference,
                        provenance_version, principal_reference_hash, canonical_input_hash,
                        idempotency_identity_hash, idempotency_scope_hash, state,
                        available_at, deadline_at, max_attempts, approval_required,
                        correlation, retain_until
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                        $12::jsonb, $13, $14, $15, $16, $17, $18,
                        COALESCE($19, clock_timestamp()), $20, $21, $22,
                        $23::jsonb,
                        clock_timestamp() + ($24::double precision * INTERVAL '1 second')
                    )
                    """,
                    operation_id,
                    self.application_namespace,
                    principal_reference.tenant_id,
                    scope,
                    action.name,
                    action.version,
                    action.executor_type,
                    action.effect_class.value,
                    command_id,
                    principal_reference.resolver_key,
                    principal_reference.resolver_version,
                    json.dumps(principal_reference.to_dict()),
                    principal_reference.version,
                    principal_reference.integrity_hash,
                    input_hash,
                    identity_hash,
                    semantic_scope_hash,
                    initial_state.value,
                    available_at,
                    deadline_at,
                    attempts,
                    action.approval_required,
                    correlation_json,
                    self.retention_seconds,
                )
                await connection.execute(
                    """
                    INSERT INTO aksara_operation_commands (
                        id, operation_id, tenant_scope, payload, canonical_input_hash
                    ) VALUES ($1, $2, $3, $4::jsonb, $5)
                    """,
                    command_id,
                    operation_id,
                    scope,
                    json.dumps(normalized),
                    input_hash,
                )
                if action.approval_required:
                    await connection.execute(
                        """
                        INSERT INTO aksara_operation_approval_decisions (
                            operation_id, tenant_scope, state, action_name, action_version,
                            canonical_input_hash, requester_reference_hash, expires_at
                        ) VALUES (
                            $1, $2, 'pending', $3, $4, $5, $6,
                            COALESCE(
                                $7,
                                clock_timestamp() + ($8::double precision * INTERVAL '1 second')
                            )
                        )
                        """,
                        operation_id,
                        scope,
                        action.name,
                        action.version,
                        input_hash,
                        principal_reference.integrity_hash,
                        approval_expires_at,
                        DEFAULT_APPROVAL_SECONDS,
                    )
                await self.repository.insert_transition(
                    connection,
                    operation_id=operation_id,
                    tenant_scope=scope,
                    state_version=1,
                    from_state=None,
                    event=OperationEvent.ADMITTED.value,
                    to_state=initial_state.value,
                    actor_reference_hash=principal_reference.integrity_hash,
                    correlation=correlation,
                )
                row = await self.repository.get_operation(
                    connection, operation_id, scope
                )
                assert row is not None
                return OperationAdmission(
                    operation=self.repository.public_operation(row),
                    created=True,
                )

    async def _resolve_duplicate(
        self,
        connection: Any,
        *,
        identity_hash: str,
        semantic_scope_hash: str,
        action: DurableAction,
        input_hash: str,
        scope: str,
    ) -> OperationAdmission:
        identity = await connection.fetchrow(
            """
            SELECT * FROM aksara_operation_idempotency
            WHERE identity_hash = $1 AND tenant_scope = $2
            """,
            identity_hash,
            scope,
        )
        if identity is None:
            raise IdempotencyConflict("idempotency identity was not visible in tenant scope")
        if (
            identity["scope_hash"] != semantic_scope_hash
            or identity["action_name"] != action.name
            or identity["action_version"] != action.version
            or identity["canonical_input_hash"] != input_hash
        ):
            raise IdempotencyConflict(
                "idempotency key is already bound to different semantic input or action version"
            )
        row = await self.repository.get_operation(
            connection, identity["operation_id"], scope
        )
        if row is None:
            raise IdempotencyIdentityExpired(
                "idempotency tombstone is retained but operation detail has expired"
            )
        return OperationAdmission(
            operation=self.repository.public_operation(row),
            created=False,
        )

    async def claim(
        self,
        *,
        tenant_id: str | None,
        worker_id: str,
        operation_id: UUID | None = None,
        lease_seconds: float | None = None,
    ) -> OperationClaim | None:
        """Claim eligible work or fence and reclaim an expired owner."""

        if not worker_id:
            raise ValueError("worker_id is required")
        lease = lease_seconds or self.default_lease_seconds
        if lease <= 0:
            raise ValueError("lease_seconds must be positive")
        scope = tenant_scope(tenant_id)
        with _tenant_context(scope):
            async with atomic(db=self.db) as connection:
                row = await self.repository.claim_row(
                    connection, scope, operation_id=operation_id
                )
                if row is None:
                    return None

                action_key = (row["action_name"], row["action_version"])
                action_available = self.actions.contains(*action_key)
                deadline_expired = bool(
                    await connection.fetchval(
                        "SELECT $1::timestamptz IS NOT NULL AND $1 <= clock_timestamp()",
                        row["deadline_at"],
                    )
                )
                if deadline_expired or row["cancellation_requested_at"] is not None:
                    await self._close_unclaimable(
                        connection,
                        row,
                        state=(
                            OperationState.CANCELLED
                            if row["cancellation_requested_at"] is not None
                            else OperationState.EXPIRED
                        ),
                        reason=(
                            FailureReason.CANCELLED
                            if row["cancellation_requested_at"] is not None
                            else FailureReason.DEADLINE_EXPIRED
                        ),
                    )
                    return None
                if int(row["attempt_count"]) >= int(row["max_attempts"]):
                    await self._close_unclaimable(
                        connection,
                        row,
                        state=OperationState.FAILED,
                        reason=FailureReason.ATTEMPTS_EXHAUSTED,
                    )
                    return None
                if not action_available:
                    await self._close_unclaimable(
                        connection,
                        row,
                        state=OperationState.FAILED,
                        reason=FailureReason.ACTION_VERSION_UNAVAILABLE,
                    )
                    return None

                old_state = OperationState(row["state"])
                if old_state is OperationState.RUNNING:
                    await connection.execute(
                        """
                        UPDATE aksara_operation_attempts
                        SET state = 'abandoned', completed_at = clock_timestamp(),
                            retryable = TRUE, error_code = $5,
                            error = $6::jsonb
                        WHERE id = $1 AND operation_id = $2 AND tenant_scope = $3
                          AND fence = $4 AND state = 'running'
                        """,
                        row["current_attempt_id"],
                        row["id"],
                        scope,
                        row["fence"],
                        FailureReason.LEASE_EXPIRED.value,
                        json.dumps(
                            _error_envelope(
                                FailureReason.LEASE_EXPIRED.value,
                                "attempt lease expired and ownership was reclaimed",
                                retryable=True,
                            )
                        ),
                    )

                if row["approval_required"] and row["approval_consumed_at"] is None:
                    approval = await connection.fetchrow(
                        """
                        SELECT * FROM aksara_operation_approval_decisions
                        WHERE operation_id = $1 AND tenant_scope = $2 AND state = 'approved'
                        FOR UPDATE
                        """,
                        row["id"],
                        scope,
                    )
                    valid = bool(
                        approval
                        and approval["canonical_input_hash"] == row["canonical_input_hash"]
                        and approval["action_name"] == row["action_name"]
                        and approval["action_version"] == row["action_version"]
                        and await connection.fetchval(
                            "SELECT $1::timestamptz > clock_timestamp()",
                            approval["expires_at"],
                        )
                    )
                    if not valid:
                        await self._close_unclaimable(
                            connection,
                            row,
                            state=OperationState.EXPIRED,
                            reason=FailureReason.APPROVAL_EXPIRED,
                        )
                        return None
                    await connection.execute(
                        """
                        UPDATE aksara_operation_approval_decisions
                        SET consumed_at = clock_timestamp()
                        WHERE id = $1 AND state = 'approved' AND consumed_at IS NULL
                        """,
                        approval["id"],
                    )

                attempt_id = uuid4()
                fence = int(row["fence"]) + 1
                ordinal = int(row["attempt_count"]) + 1
                attempt = await connection.fetchrow(
                    """
                    INSERT INTO aksara_operation_attempts (
                        id, operation_id, tenant_scope, ordinal, fence, worker_id,
                        state, lease_expires_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, 'running',
                        clock_timestamp() + ($7::double precision * INTERVAL '1 second')
                    ) RETURNING *
                    """,
                    attempt_id,
                    row["id"],
                    scope,
                    ordinal,
                    fence,
                    worker_id,
                    lease,
                )
                state_version = int(row["state_version"]) + 1
                updated = await connection.fetchrow(
                    """
                    UPDATE aksara_operations
                    SET state = 'running', state_version = $2,
                        current_attempt_id = $3, fence = $4, worker_id = $5,
                        lease_expires_at = $6, attempt_count = $7,
                        approval_consumed_at = CASE
                            WHEN approval_required AND approval_consumed_at IS NULL
                            THEN clock_timestamp() ELSE approval_consumed_at END,
                        updated_at = clock_timestamp()
                    WHERE id = $1 AND tenant_scope = $8
                    RETURNING *
                    """,
                    row["id"],
                    state_version,
                    attempt_id,
                    fence,
                    worker_id,
                    attempt["lease_expires_at"],
                    ordinal,
                    scope,
                )
                event = (
                    OperationEvent.LEASE_RECLAIMED
                    if old_state is OperationState.RUNNING
                    else OperationEvent.CLAIMED
                )
                await self.repository.insert_transition(
                    connection,
                    operation_id=row["id"],
                    tenant_scope=scope,
                    state_version=state_version,
                    from_state=old_state.value,
                    event=event.value,
                    to_state=OperationState.RUNNING.value,
                    attempt_id=attempt_id,
                    metadata={"ordinal": ordinal},
                )
                command = await self.repository.get_command(connection, row["id"], scope)
                assert updated is not None and attempt is not None and command is not None
                return self.repository.claim(updated, attempt, command)

    async def _close_unclaimable(
        self,
        connection: Any,
        row: Mapping[str, Any],
        *,
        state: OperationState,
        reason: FailureReason,
    ) -> None:
        if row["state"] == OperationState.RUNNING.value and row["current_attempt_id"]:
            attempt_state = (
                "cancelled" if state is OperationState.CANCELLED else "abandoned"
            )
            await connection.execute(
                """
                UPDATE aksara_operation_attempts
                SET state = $2, completed_at = clock_timestamp(), retryable = FALSE,
                    error_code = $3, error = $4::jsonb
                WHERE id = $1 AND state = 'running'
                """,
                row["current_attempt_id"],
                attempt_state,
                reason.value,
                json.dumps(_error_envelope(reason.value, reason.value, retryable=False)),
            )
        version = int(row["state_version"]) + 1
        error = _error_envelope(reason.value, reason.value, retryable=False)
        await connection.execute(
            """
            UPDATE aksara_operations
            SET state = $2, state_version = $3, error = $4::jsonb,
                worker_id = NULL, lease_expires_at = NULL,
                completed_at = clock_timestamp(), updated_at = clock_timestamp()
            WHERE id = $1
            """,
            row["id"],
            state.value,
            version,
            json.dumps(error),
        )
        event = (
            OperationEvent.CANCELLATION_OBSERVED
            if state is OperationState.CANCELLED and row["state"] == "running"
            else OperationEvent.CANCELLATION_REQUESTED
            if state is OperationState.CANCELLED
            else OperationEvent.DEADLINE_EXPIRED
            if state is OperationState.EXPIRED
            else OperationEvent.TERMINAL_FAILURE
        )
        await self.repository.insert_transition(
            connection,
            operation_id=row["id"],
            tenant_scope=row["tenant_scope"],
            state_version=version,
            from_state=row["state"],
            event=event.value,
            to_state=state.value,
            reason_code=reason.value,
            attempt_id=row["current_attempt_id"],
        )

    async def heartbeat(
        self,
        claim: OperationClaim,
        *,
        lease_seconds: float | None = None,
        usage_summary: Mapping[str, Any] | None = None,
    ) -> datetime:
        """Renew a lease only while the complete ownership tuple is current."""

        lease = lease_seconds or self.default_lease_seconds
        if lease <= 0:
            raise ValueError("lease_seconds must be positive")
        with _tenant_context(claim.tenant_scope):
            async with atomic(db=self.db) as connection:
                renewed = await connection.fetchrow(
                    """
                    WITH current_owner AS (
                        SELECT id
                        FROM aksara_operations
                        WHERE id = $1 AND tenant_scope = $2 AND state = 'running'
                          AND current_attempt_id = $3 AND fence = $4 AND worker_id = $5
                          AND lease_expires_at > clock_timestamp()
                          AND cancellation_requested_at IS NULL
                        FOR UPDATE
                    ), renewed_attempt AS (
                        UPDATE aksara_operation_attempts
                        SET lease_expires_at = clock_timestamp()
                                + ($6::double precision * INTERVAL '1 second'),
                            heartbeat_at = clock_timestamp(),
                            usage_summary = COALESCE($7::jsonb, usage_summary)
                        WHERE id = $3 AND operation_id IN (SELECT id FROM current_owner)
                          AND tenant_scope = $2 AND fence = $4 AND worker_id = $5
                          AND state = 'running'
                        RETURNING lease_expires_at
                    )
                    UPDATE aksara_operations
                    SET lease_expires_at = renewed_attempt.lease_expires_at,
                        updated_at = clock_timestamp()
                    FROM renewed_attempt
                    WHERE id IN (SELECT id FROM current_owner)
                    RETURNING aksara_operations.lease_expires_at
                    """,
                    claim.operation_id,
                    claim.tenant_scope,
                    claim.attempt_id,
                    claim.fence,
                    claim.worker_id,
                    lease,
                    json.dumps(dict(usage_summary)) if usage_summary is not None else None,
                )
                if renewed is None:
                    raise OwnershipLost("attempt no longer owns an unexpired operation lease")
                return renewed["lease_expires_at"]

    async def fail_attempt(
        self,
        claim: OperationClaim,
        *,
        code: str,
        message: str,
        retryable: bool,
        retry_delay_seconds: float = 0.0,
        usage_summary: Mapping[str, Any] | None = None,
    ) -> OperationRecord:
        """Record an owned failure and either retry or close terminally."""

        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds cannot be negative")
        with _tenant_context(claim.tenant_scope):
            async with atomic(db=self.db) as connection:
                row = await self._lock_owned(connection, claim)
                has_budget = int(row["attempt_count"]) < int(row["max_attempts"])
                before_deadline = bool(
                    await connection.fetchval(
                        "SELECT $1::timestamptz IS NULL OR $1 > clock_timestamp()",
                        row["deadline_at"],
                    )
                )
                will_retry = retryable and has_budget and before_deadline
                target = OperationState.READY if will_retry else OperationState.FAILED
                error = _error_envelope(code, message, retryable=will_retry)
                await connection.execute(
                    """
                    UPDATE aksara_operation_attempts
                    SET state = 'failed', completed_at = clock_timestamp(),
                        retryable = $6, error_code = $7, error = $8::jsonb,
                        usage_summary = COALESCE($9::jsonb, usage_summary)
                    WHERE id = $1 AND operation_id = $2 AND tenant_scope = $3
                      AND fence = $4 AND worker_id = $5 AND state = 'running'
                    """,
                    claim.attempt_id,
                    claim.operation_id,
                    claim.tenant_scope,
                    claim.fence,
                    claim.worker_id,
                    will_retry,
                    code,
                    json.dumps(error),
                    json.dumps(dict(usage_summary)) if usage_summary is not None else None,
                )
                version = int(row["state_version"]) + 1
                updated = await connection.fetchrow(
                    """
                    UPDATE aksara_operations
                    SET state = $6, state_version = $7, error = $8::jsonb,
                        available_at = CASE WHEN $9 THEN clock_timestamp()
                            + ($10::double precision * INTERVAL '1 second')
                            ELSE available_at END,
                        worker_id = NULL, lease_expires_at = NULL,
                        completed_at = CASE WHEN $9 THEN NULL ELSE clock_timestamp() END,
                        updated_at = clock_timestamp()
                    WHERE id = $1 AND tenant_scope = $2 AND state = 'running'
                      AND current_attempt_id = $3 AND fence = $4 AND worker_id = $5
                    RETURNING *
                    """,
                    claim.operation_id,
                    claim.tenant_scope,
                    claim.attempt_id,
                    claim.fence,
                    claim.worker_id,
                    target.value,
                    version,
                    json.dumps(error),
                    will_retry,
                    retry_delay_seconds,
                )
                if updated is None:
                    raise OwnershipLost("failure finalization lost ownership")
                await self.repository.insert_transition(
                    connection,
                    operation_id=claim.operation_id,
                    tenant_scope=claim.tenant_scope,
                    state_version=version,
                    from_state=OperationState.RUNNING.value,
                    event=(
                        OperationEvent.RETRY_SCHEDULED.value
                        if will_retry
                        else OperationEvent.TERMINAL_FAILURE.value
                    ),
                    to_state=target.value,
                    reason_code=code,
                    attempt_id=claim.attempt_id,
                )
                return self.repository.public_operation(updated)

    async def _lock_owned(self, connection: Any, claim: OperationClaim) -> Any:
        row = await connection.fetchrow(
            """
            SELECT * FROM aksara_operations
            WHERE id = $1 AND tenant_scope = $2 AND state = 'running'
              AND current_attempt_id = $3 AND fence = $4 AND worker_id = $5
              AND lease_expires_at > clock_timestamp()
            FOR UPDATE
            """,
            claim.operation_id,
            claim.tenant_scope,
            claim.attempt_id,
            claim.fence,
            claim.worker_id,
        )
        if row is None:
            raise OwnershipLost("attempt does not own the current unexpired lease")
        return row

    async def request_cancellation(
        self,
        operation_id: UUID,
        *,
        tenant_id: str | None,
        principal: Principal,
        requester_reference: PrincipalReference,
        reason: str | None = None,
    ) -> OperationRecord:
        """Persist cancellation intent; terminal success always wins."""

        scope = tenant_scope(tenant_id)
        self._authorize_read(principal, tenant_id, action="cancel")
        with _tenant_context(scope):
            async with atomic(db=self.db) as connection:
                row = await self.repository.get_operation(
                    connection, operation_id, scope, for_update=True
                )
                if row is None:
                    raise OperationNotFound("operation was not found")
                state = OperationState(row["state"])
                if state in TERMINAL_OPERATION_STATES:
                    raise CancellationConflict(
                        f"cannot cancel terminal operation in state {state.value}"
                    )
                version = int(row["state_version"]) + 1
                target = (
                    OperationState.RUNNING
                    if state is OperationState.RUNNING
                    else OperationState.CANCELLED
                )
                updated = await connection.fetchrow(
                    """
                    UPDATE aksara_operations
                    SET cancellation_requested_at = clock_timestamp(),
                        cancellation_requester = $2::jsonb,
                        cancellation_reason = $3,
                        state = $4::varchar, state_version = $5,
                        completed_at = CASE WHEN $4::varchar = 'cancelled'
                            THEN clock_timestamp() ELSE completed_at END,
                        updated_at = clock_timestamp()
                    WHERE id = $1 AND tenant_scope = $6 AND state = $7
                    RETURNING *
                    """,
                    operation_id,
                    json.dumps(requester_reference.to_dict()),
                    (reason or "")[:500] or None,
                    target.value,
                    version,
                    scope,
                    state.value,
                )
                if updated is None:
                    raise CancellationConflict("operation state changed during cancellation")
                await self.repository.insert_transition(
                    connection,
                    operation_id=operation_id,
                    tenant_scope=scope,
                    state_version=version,
                    from_state=state.value,
                    event=OperationEvent.CANCELLATION_REQUESTED.value,
                    to_state=target.value,
                    actor_reference_hash=requester_reference.integrity_hash,
                    reason_code=FailureReason.CANCELLED.value,
                    attempt_id=row["current_attempt_id"],
                )
                return self.repository.public_operation(updated)

    async def decide_approval(
        self,
        operation_id: UUID,
        *,
        tenant_id: str | None,
        approver: Principal,
        approver_reference: PrincipalReference,
        approve: bool,
        reason: str | None = None,
    ) -> OperationRecord:
        """Bind one current human decision to an exact logical operation."""

        scope = tenant_scope(tenant_id)
        with _tenant_context(scope):
            async with atomic(db=self.db) as connection:
                row = await self.repository.get_operation(
                    connection, operation_id, scope, for_update=True
                )
                if row is None:
                    raise OperationNotFound("operation was not found")
                if row["state"] != OperationState.WAITING_FOR_APPROVAL.value:
                    raise ApprovalConflict("operation is not waiting for approval")
                action = self.actions.get(row["action_name"], row["action_version"])
                command = await self.repository.get_command(connection, operation_id, scope)
                assert command is not None
                self._authorize_read(approver, tenant_id, action="approve")
                if action.approval_authorizer is not None and not await _call_authorizer(
                    action.approval_authorizer, approver, command
                ):
                    raise AuthorizationDenied("approver is not currently authorized")
                decision = await connection.fetchrow(
                    """
                    SELECT * FROM aksara_operation_approval_decisions
                    WHERE operation_id = $1 AND tenant_scope = $2 AND state = 'pending'
                    FOR UPDATE
                    """,
                    operation_id,
                    scope,
                )
                if decision is None:
                    raise ApprovalConflict("active approval decision is missing")
                unexpired = await connection.fetchval(
                    "SELECT $1::timestamptz > clock_timestamp()",
                    decision["expires_at"],
                )
                version = int(row["state_version"]) + 1
                if not unexpired:
                    decision_state = "expired"
                    target = OperationState.EXPIRED
                    event = OperationEvent.DEADLINE_EXPIRED
                    code = FailureReason.APPROVAL_EXPIRED.value
                elif approve:
                    decision_state = "approved"
                    target = OperationState.READY
                    event = OperationEvent.APPROVED
                    code = None
                else:
                    decision_state = "rejected"
                    target = OperationState.CANCELLED
                    event = OperationEvent.REJECTED
                    code = FailureReason.APPROVAL_REJECTED.value
                await connection.execute(
                    """
                    UPDATE aksara_operation_approval_decisions
                    SET state = $2, approver_reference = $3::jsonb,
                        approver_reference_hash = $4, reason = $5,
                        decided_at = clock_timestamp()
                    WHERE id = $1 AND state = 'pending'
                    """,
                    decision["id"],
                    decision_state,
                    json.dumps(approver_reference.to_dict()),
                    approver_reference.integrity_hash,
                    (reason or "")[:1000] or None,
                )
                updated = await connection.fetchrow(
                    """
                    UPDATE aksara_operations
                    SET state = $2::varchar, state_version = $3,
                        error = CASE WHEN $4::text IS NULL THEN NULL ELSE $5::jsonb END,
                        completed_at = CASE WHEN $2::varchar IN ('cancelled', 'expired')
                            THEN clock_timestamp() ELSE NULL END,
                        updated_at = clock_timestamp()
                    WHERE id = $1 AND tenant_scope = $6
                      AND state = 'waiting_for_approval'
                    RETURNING *
                    """,
                    operation_id,
                    target.value,
                    version,
                    code,
                    json.dumps(_error_envelope(code, code, retryable=False))
                    if code is not None
                    else None,
                    scope,
                )
                if updated is None:
                    raise ApprovalConflict("approval decision lost its state race")
                await self.repository.insert_transition(
                    connection,
                    operation_id=operation_id,
                    tenant_scope=scope,
                    state_version=version,
                    from_state=OperationState.WAITING_FOR_APPROVAL.value,
                    event=event.value,
                    to_state=target.value,
                    reason_code=code,
                    actor_reference_hash=approver_reference.integrity_hash,
                )
                return self.repository.public_operation(updated)

    async def get(
        self,
        operation_id: UUID,
        *,
        tenant_id: str | None,
        principal: Principal,
    ) -> OperationRecord:
        self._authorize_read(principal, tenant_id, action="read")
        scope = tenant_scope(tenant_id)
        with _tenant_context(scope):
            async with self.db.acquire() as connection:
                row = await self.repository.get_public_operation(
                    connection, operation_id, scope
                )
        if row is None:
            raise OperationNotFound("operation was not found")
        return row

    async def history(
        self,
        operation_id: UUID,
        *,
        tenant_id: str | None,
        principal: Principal,
        limit: int = 50,
    ) -> list[TransitionRecord]:
        self._authorize_read(principal, tenant_id, action="read")
        if limit < 1 or limit > MAX_HISTORY_PAGE:
            raise ValueError(f"limit must be between 1 and {MAX_HISTORY_PAGE}")
        scope = tenant_scope(tenant_id)
        with _tenant_context(scope):
            async with self.db.acquire() as connection:
                if await self.repository.get_operation(connection, operation_id, scope) is None:
                    raise OperationNotFound("operation was not found")
                return await self.repository.history(
                    connection, operation_id, scope, limit=limit
                )

    async def pending_outbox(
        self,
        *,
        tenant_id: str | None,
        principal: Principal,
        limit: int = 100,
    ) -> list[OutboxRecord]:
        self._authorize_read(principal, tenant_id, action="read")
        if limit < 1 or limit > MAX_OUTBOX_PAGE:
            raise ValueError(f"limit must be between 1 and {MAX_OUTBOX_PAGE}")
        scope = tenant_scope(tenant_id)
        with _tenant_context(scope):
            async with self.db.acquire() as connection:
                return await self.repository.pending_outbox(
                    connection, scope, limit=limit
                )

    async def check_deployment(self, *, tenant_id: str | None) -> set[tuple[str, str]]:
        """Return nonterminal persisted action versions missing from this deployment."""

        scope = tenant_scope(tenant_id)
        with _tenant_context(scope):
            async with self.db.acquire() as connection:
                deployed = await self.repository.nonterminal_action_versions(connection)
        return deployed - self.actions.versions()

    async def prune(
        self,
        *,
        tenant_id: str | None,
        history_per_operation: int = 100,
    ) -> dict[str, int]:
        """Bound exported history and expired terminal detail without active-row loss."""

        if history_per_operation < 1:
            raise ValueError("history_per_operation must be positive")
        scope = tenant_scope(tenant_id)
        with _tenant_context(scope):
            async with atomic(db=self.db) as connection:
                deleted_outbox = await connection.fetchval(
                    """
                    WITH deleted AS (
                        DELETE FROM aksara_operation_outbox
                        WHERE tenant_scope = $1 AND exported_at IS NOT NULL
                          AND exported_at < clock_timestamp() - INTERVAL '1 day'
                        RETURNING id
                    ) SELECT COUNT(*) FROM deleted
                    """,
                    scope,
                )
                deleted_transitions = await connection.fetchval(
                    """
                    WITH ranked AS (
                        SELECT t.id, row_number() OVER (
                            PARTITION BY t.operation_id ORDER BY t.id DESC
                        ) AS position
                        FROM aksara_operation_transitions t
                        WHERE t.tenant_scope = $1
                          AND NOT EXISTS (
                              SELECT 1 FROM aksara_operation_outbox o
                              WHERE o.transition_id = t.id AND o.exported_at IS NULL
                          )
                    ), deleted AS (
                        DELETE FROM aksara_operation_transitions t
                        USING ranked r
                        WHERE t.id = r.id AND r.position > $2
                        RETURNING t.id
                    ) SELECT COUNT(*) FROM deleted
                    """,
                    scope,
                    history_per_operation,
                )
                deleted_operations = await connection.fetchval(
                    """
                    WITH deleted AS (
                        DELETE FROM aksara_operations o
                        WHERE o.tenant_scope = $1
                          AND o.state IN ('succeeded', 'failed', 'cancelled', 'expired')
                          AND o.retain_until <= clock_timestamp()
                          AND NOT EXISTS (
                              SELECT 1 FROM aksara_operation_idempotency i
                              WHERE i.operation_id = o.id AND i.expires_at > clock_timestamp()
                          )
                        RETURNING o.id
                    ) SELECT COUNT(*) FROM deleted
                    """,
                    scope,
                )
                deleted_idempotency = await connection.fetchval(
                    """
                    WITH deleted AS (
                        DELETE FROM aksara_operation_idempotency
                        WHERE tenant_scope = $1 AND expires_at <= clock_timestamp()
                        RETURNING identity_hash
                    ) SELECT COUNT(*) FROM deleted
                    """,
                    scope,
                )
        return {
            "outbox": int(deleted_outbox),
            "transitions": int(deleted_transitions),
            "operations": int(deleted_operations),
            "idempotency": int(deleted_idempotency),
        }

    @staticmethod
    def _authorize_read(principal: Principal, tenant_id: str | None, *, action: str) -> None:
        if not principal.is_system and principal.tenant_id != tenant_id:
            raise AuthorizationDenied("principal tenant does not match operation tenant")
        decision = default_policy.can(
            principal,
            action,
            tenant_id=tenant_id,
            tenant_required=tenant_id is not None,
        )
        if decision.denied:
            raise AuthorizationDenied(decision.reason)


__all__ = ["DurableOperationService"]
