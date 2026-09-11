"""Durable admission, identity, approval and ownership invariants."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from aksara.db import atomic
from aksara.durable import (
    ApprovalConflict,
    AuthorizationDenied,
    DurableAction,
    DurableActionRegistry,
    DurableConfigurationError,
    DurableOperationService,
    EffectClass,
    IdempotencyConflict,
    OperationNotFound,
    OperationState,
    PrincipalReference,
)
from aksara.durable.errors import InvalidDurableCommand, OwnershipLost
from aksara.durable.service import _tenant_context
from aksara.durable.types import GLOBAL_TENANT_SCOPE, tenant_scope
from aksara.security.principal import Principal


async def _handler(_context, command):
    return command


def _principal(tenant: str) -> Principal:
    return Principal.for_user("user-1", tenant_id=tenant, scopes=("orders:write",))


def _reference(tenant: str, subject_id: str = "user-1") -> PrincipalReference:
    return PrincipalReference(
        resolver_key="test",
        resolver_version="1",
        identity_namespace="test-app",
        principal_kind="user",
        subject_id=subject_id,
        tenant_id=tenant,
    )


def _service(
    durable_db,
    *,
    approval: bool = False,
    namespace: str = "tests",
    approval_authorizer=None,
    required_scopes: tuple[str, ...] = (),
    authorizer=None,
):
    actions = DurableActionRegistry()
    actions.register(
        DurableAction(
            name="orders.increment",
            version="1",
            handler=_handler,
            effect_class=EffectClass.POSTGRES_ATOMIC,
            required_scopes=required_scopes,
            authorizer=authorizer,
            approval_required=approval,
            approval_authorizer=approval_authorizer,
        )
    )
    return DurableOperationService(
        durable_db,
        application_namespace=namespace,
        actions=actions,
        idempotency_seconds=60,
        retention_seconds=60,
    )


def test_principal_reference_never_serializes_runtime_authority():
    principal = Principal.for_mcp_agent(
        token_id="revocation-handle",
        human_owner_id="owner-1",
        tenant_id="tenant-1",
        roles=("admin",),
        scopes=("*",),
        agent_id="agent-1",
        metadata={"bearer_token": "secret", "audience": "mcp"},
    )
    reference = PrincipalReference.from_principal(
        principal,
        resolver_key="identity-store",
    )

    stored = reference.to_dict()
    assert stored["credential_id"] == "revocation-handle"
    assert "roles" not in stored
    assert "scopes" not in stored
    assert "metadata" not in stored
    assert "bearer_token" not in str(stored)


def test_global_tenant_storage_sentinel_is_reserved():
    with pytest.raises(ValueError, match="reserved"):
        tenant_scope(GLOBAL_TENANT_SCOPE)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("available_at", datetime(2030, 1, 1, tzinfo=UTC).replace(tzinfo=None)),
        ("deadline_at", datetime(2030, 1, 1, tzinfo=UTC).replace(tzinfo=None)),
        ("deadline_at", datetime.now(UTC) - timedelta(seconds=1)),
    ],
)
async def test_admission_rejects_invalid_operation_timestamps(
    durable_db, field, value
):
    tenant = str(uuid4())
    service = _service(durable_db)

    with pytest.raises(InvalidDurableCommand):
        await service.admit(
            "orders.increment",
            "1",
            {"amount": 1},
            _reference(tenant),
            **{field: value},
        )


@pytest.mark.asyncio
async def test_admission_is_scoped_idempotent_and_conflict_sensitive(durable_db):
    tenant = str(uuid4())
    service = _service(durable_db)
    reference = _reference(tenant)

    first = await service.admit(
        "orders.increment",
        "1",
        {"counter_id": "counter-1", "amount": 1},
        reference,
        idempotency_key="request-1",
    )
    duplicate = await service.admit(
        "orders.increment",
        "1",
        {"amount": 1, "counter_id": "counter-1"},
        reference,
        idempotency_key="request-1",
    )

    assert first.created is True
    assert duplicate.created is False
    assert duplicate.operation.id == first.operation.id
    assert duplicate.operation.attempt_count == 0

    with pytest.raises(IdempotencyConflict):
        await service.admit(
            "orders.increment",
            "1",
            {"counter_id": "counter-1", "amount": 2},
            reference,
            idempotency_key="request-1",
        )

    service.actions.register(
        DurableAction(
            name="orders.increment",
            version="2",
            handler=_handler,
            effect_class=EffectClass.POSTGRES_ATOMIC,
        )
    )
    with pytest.raises(IdempotencyConflict):
        await service.admit(
            "orders.increment",
            "2",
            {"counter_id": "counter-1", "amount": 1},
            reference,
            idempotency_key="request-1",
        )


@pytest.mark.asyncio
async def test_concurrent_identical_admission_creates_one_operation(durable_db):
    tenant = str(uuid4())
    service = _service(durable_db)
    reference = _reference(tenant)

    outcomes = await asyncio.gather(
        *(
            service.admit(
                "orders.increment",
                "1",
                {"counter_id": "counter-1", "amount": 1},
                reference,
                idempotency_key="concurrent-key",
            )
            for _ in range(8)
        )
    )

    assert len({outcome.operation.id for outcome in outcomes}) == 1
    assert sum(outcome.created for outcome in outcomes) == 1


@pytest.mark.asyncio
async def test_expired_idempotency_key_can_create_a_new_operation(durable_db):
    tenant = str(uuid4())
    service = _service(durable_db)
    reference = _reference(tenant)
    first = await service.admit(
        "orders.increment",
        "1",
        {"amount": 1},
        reference,
        idempotency_key="reusable-key",
    )
    scope = tenant_scope(tenant)
    with _tenant_context(scope):
        await durable_db.execute(
            """
            UPDATE aksara_operation_idempotency
            SET expires_at = clock_timestamp() - INTERVAL '1 second'
            WHERE operation_id = $1
            """,
            first.operation.id,
        )

    second = await service.admit(
        "orders.increment",
        "1",
        {"amount": 1},
        reference,
        idempotency_key="reusable-key",
    )

    assert second.created is True
    assert second.operation.id != first.operation.id
    with _tenant_context(scope):
        retained_identity = await durable_db.fetchval(
            "SELECT idempotency_identity_hash FROM aksara_operations WHERE id = $1",
            first.operation.id,
        )
    assert retained_identity is None


@pytest.mark.asyncio
async def test_idempotency_identity_isolated_by_tenant_and_principal(durable_db):
    tenant_a, tenant_b = str(uuid4()), str(uuid4())
    service = _service(durable_db)
    command = {"counter_id": "counter-1", "amount": 1}

    first = await service.admit(
        "orders.increment",
        "1",
        command,
        _reference(tenant_a, "user-1"),
        idempotency_key="shared-client-key",
    )
    other_principal = await service.admit(
        "orders.increment",
        "1",
        command,
        _reference(tenant_a, "user-2"),
        idempotency_key="shared-client-key",
    )
    other_tenant = await service.admit(
        "orders.increment",
        "1",
        command,
        _reference(tenant_b, "user-1"),
        idempotency_key="shared-client-key",
    )

    assert len(
        {
            first.operation.id,
            other_principal.operation.id,
            other_tenant.operation.id,
        }
    ) == 3


@pytest.mark.asyncio
async def test_claim_heartbeat_reclaim_and_stale_owner_fencing(durable_db):
    tenant = str(uuid4())
    service = _service(durable_db)
    admitted = await service.admit(
        "orders.increment",
        "1",
        {"counter_id": "counter-1", "amount": 1},
        _reference(tenant),
    )
    first = await service.claim(
        tenant_id=tenant,
        worker_id="worker-a",
        operation_id=admitted.operation.id,
        lease_seconds=0.05,
    )
    assert first is not None
    renewed = await service.heartbeat(first, lease_seconds=0.05)
    assert renewed > first.lease_expires_at

    await asyncio.sleep(0.08)
    second = await service.claim(
        tenant_id=tenant,
        worker_id="worker-b",
        operation_id=admitted.operation.id,
        lease_seconds=1,
    )
    assert second is not None
    assert second.fence == first.fence + 1
    assert second.ordinal == 2

    with pytest.raises(OwnershipLost):
        await service.heartbeat(first)
    with pytest.raises(OwnershipLost):
        await service.fail_attempt(
            first,
            code="late_failure",
            message="stale",
            retryable=False,
        )


@pytest.mark.asyncio
async def test_zero_attempt_and_lease_values_are_rejected(durable_db):
    tenant = str(uuid4())
    service = _service(durable_db)
    with pytest.raises(ValueError, match="max_attempts must be positive"):
        await service.admit(
            "orders.increment",
            "1",
            {"amount": 1},
            _reference(tenant),
            max_attempts=0,
        )
    admitted = await service.admit(
        "orders.increment", "1", {"amount": 1}, _reference(tenant)
    )
    with pytest.raises(ValueError, match="lease_seconds must be positive"):
        await service.claim(
            tenant_id=tenant,
            worker_id="worker-a",
            operation_id=admitted.operation.id,
            lease_seconds=0,
        )
    claim = await service.claim(
        tenant_id=tenant,
        worker_id="worker-a",
        operation_id=admitted.operation.id,
    )
    assert claim is not None
    with pytest.raises(ValueError, match="lease_seconds must be positive"):
        await service.heartbeat(claim, lease_seconds=0)


@pytest.mark.asyncio
async def test_retryable_failure_returns_operation_to_ready(durable_db):
    tenant = str(uuid4())
    service = _service(durable_db)
    admitted = await service.admit(
        "orders.increment", "1", {"amount": 1}, _reference(tenant)
    )
    claim = await service.claim(
        tenant_id=tenant,
        worker_id="worker-a",
        operation_id=admitted.operation.id,
    )
    assert claim is not None

    operation = await service.fail_attempt(
        claim,
        code="temporary_database_failure",
        message="retry later",
        retryable=True,
    )
    assert operation.state is OperationState.READY
    assert operation.error["retryable"] is True


@pytest.mark.asyncio
async def test_failure_observes_committed_cancellation(durable_db):
    tenant = str(uuid4())
    service = _service(durable_db)
    admitted = await service.admit(
        "orders.increment", "1", {"amount": 1}, _reference(tenant)
    )
    claim = await service.claim(
        tenant_id=tenant,
        worker_id="worker-a",
        operation_id=admitted.operation.id,
    )
    assert claim is not None
    requested = await service.request_cancellation(
        admitted.operation.id,
        tenant_id=tenant,
        principal=_principal(tenant),
        requester_reference=_reference(tenant),
    )
    assert requested.state is OperationState.RUNNING

    completed = await service.fail_attempt(
        claim,
        code="temporary_failure",
        message="retry",
        retryable=True,
    )

    assert completed.state is OperationState.CANCELLED


@pytest.mark.asyncio
async def test_unknown_external_outcome_overrides_committed_cancellation(durable_db):
    tenant = str(uuid4())
    service = _service(durable_db)
    admitted = await service.admit(
        "orders.increment", "1", {"amount": 1}, _reference(tenant)
    )
    claim = await service.claim(
        tenant_id=tenant,
        worker_id="worker-a",
        operation_id=admitted.operation.id,
    )
    assert claim is not None
    await service.request_cancellation(
        admitted.operation.id,
        tenant_id=tenant,
        principal=_principal(tenant),
        requester_reference=_reference(tenant),
    )

    completed = await service.fail_attempt(
        claim,
        code="external_outcome_unknown",
        message="provider result is ambiguous",
        retryable=False,
    )

    assert completed.state is OperationState.FAILED
    assert completed.error["code"] == "external_outcome_unknown"


@pytest.mark.asyncio
async def test_durable_approval_then_claim_and_reject_race(durable_db):
    tenant = str(uuid4())
    service = _service(durable_db, approval=True)
    reference = _reference(tenant)
    admitted = await service.admit(
        "orders.increment", "1", {"amount": 1}, reference
    )
    assert admitted.operation.state is OperationState.WAITING_FOR_APPROVAL
    assert await service.claim(
        tenant_id=tenant,
        worker_id="worker-a",
        operation_id=admitted.operation.id,
    ) is None

    approved = await service.decide_approval(
        admitted.operation.id,
        tenant_id=tenant,
        approver=_principal(tenant),
        approver_reference=reference,
        approve=True,
    )
    assert approved.state is OperationState.READY
    with pytest.raises(ApprovalConflict):
        await service.decide_approval(
            admitted.operation.id,
            tenant_id=tenant,
            approver=_principal(tenant),
            approver_reference=reference,
            approve=False,
        )
    claim = await service.claim(
        tenant_id=tenant,
        worker_id="worker-a",
        operation_id=admitted.operation.id,
    )
    assert claim is not None


@pytest.mark.asyncio
async def test_cancellation_and_tenant_filtered_status_history_outbox(durable_db):
    tenant = str(uuid4())
    other_tenant = str(uuid4())
    service = _service(durable_db)
    reference = _reference(tenant)
    admitted = await service.admit(
        "orders.increment", "1", {"amount": 1}, reference
    )
    cancelled = await service.request_cancellation(
        admitted.operation.id,
        tenant_id=tenant,
        principal=_principal(tenant),
        requester_reference=reference,
        reason="no longer needed",
    )
    assert cancelled.state is OperationState.CANCELLED
    assert len(await service.history(
        admitted.operation.id,
        tenant_id=tenant,
        principal=_principal(tenant),
    )) == 2
    assert len(await service.pending_outbox(
        tenant_id=tenant,
        principal=Principal.system(tenant_id=tenant),
    )) == 2

    with pytest.raises(OperationNotFound):
        await service.get(
            admitted.operation.id,
            tenant_id=other_tenant,
            principal=_principal(other_tenant),
        )


@pytest.mark.asyncio
async def test_cancelling_waiting_operation_supersedes_pending_approval(durable_db):
    tenant = str(uuid4())
    service = _service(durable_db, approval=True)
    admitted = await service.admit(
        "orders.increment", "1", {"amount": 1}, _reference(tenant)
    )

    cancelled = await service.request_cancellation(
        admitted.operation.id,
        tenant_id=tenant,
        principal=_principal(tenant),
        requester_reference=_reference(tenant),
        reason="request withdrawn",
    )

    assert cancelled.state is OperationState.CANCELLED
    with _tenant_context(tenant_scope(tenant)):
        decision = await durable_db.fetchrow(
            """
            SELECT state, reason, decided_at
            FROM aksara_operation_approval_decisions
            WHERE operation_id = $1
            """,
            admitted.operation.id,
        )
    assert decision["state"] == "superseded"
    assert decision["reason"] == "request withdrawn"
    assert decision["decided_at"] is not None


@pytest.mark.asyncio
async def test_anonymous_principal_cannot_read_global_operation_state(durable_db):
    service = _service(durable_db)
    reference = PrincipalReference(
        resolver_key="test",
        resolver_version="1",
        identity_namespace="test-app",
        principal_kind="system",
        subject_id="global-user",
        tenant_id=None,
    )
    admitted = await service.admit(
        "orders.increment", "1", {"amount": 1}, reference
    )
    anonymous = Principal.anonymous()

    with pytest.raises(AuthorizationDenied, match="authenticated principal"):
        await service.get(
            admitted.operation.id, tenant_id=None, principal=anonymous
        )
    with pytest.raises(AuthorizationDenied, match="authenticated principal"):
        await service.history(
            admitted.operation.id, tenant_id=None, principal=anonymous
        )
    with pytest.raises(AuthorizationDenied, match="authenticated principal"):
        await service.pending_outbox(tenant_id=None, principal=anonymous)


@pytest.mark.asyncio
async def test_direct_status_history_and_cancellation_recheck_current_action_authority(
    durable_db,
):
    tenant = str(uuid4())

    def current_authorizer(principal, _command):
        return principal.has_scope("orders:write")

    service = _service(
        durable_db,
        required_scopes=("orders:write",),
        authorizer=current_authorizer,
    )
    reference = _reference(tenant)
    admitted = await service.admit(
        "orders.increment", "1", {"amount": 1}, reference
    )
    denied = Principal.for_user("user-1", tenant_id=tenant, scopes=())

    with pytest.raises(AuthorizationDenied, match="Missing required scopes"):
        await service.get(
            admitted.operation.id,
            tenant_id=tenant,
            principal=denied,
        )
    with pytest.raises(AuthorizationDenied, match="Missing required scopes"):
        await service.history(
            admitted.operation.id,
            tenant_id=tenant,
            principal=denied,
        )
    with pytest.raises(AuthorizationDenied, match="Missing required scopes"):
        await service.request_cancellation(
            admitted.operation.id,
            tenant_id=tenant,
            principal=denied,
            requester_reference=reference,
        )


@pytest.mark.asyncio
async def test_pending_outbox_requires_system_principal(durable_db):
    tenant = str(uuid4())
    service = _service(durable_db)
    await service.admit(
        "orders.increment", "1", {"amount": 1}, _reference(tenant)
    )

    with pytest.raises(AuthorizationDenied, match="system principal"):
        await service.pending_outbox(
            tenant_id=tenant,
            principal=_principal(tenant),
        )


@pytest.mark.asyncio
async def test_direct_approval_rechecks_current_approver_authority(durable_db):
    tenant = str(uuid4())
    service = _service(
        durable_db,
        approval=True,
        required_scopes=("orders:write",),
    )
    admitted = await service.admit(
        "orders.increment", "1", {"amount": 1}, _reference(tenant)
    )

    with pytest.raises(AuthorizationDenied, match="Missing required scopes"):
        await service.decide_approval(
            admitted.operation.id,
            tenant_id=tenant,
            approver=Principal.for_user("user-1", tenant_id=tenant, scopes=()),
            approver_reference=_reference(tenant),
            approve=True,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("column", "value", "expected_code"),
    [
        ("principal_reference", {"resolver_key": "attacker"}, "malformed_principal_provenance"),
        ("effect_class", "external_idempotent", "action_version_unavailable"),
        ("executor_type", "task", "action_version_unavailable"),
    ],
)
async def test_tampered_authority_and_executor_metadata_fail_closed(
    durable_db, column, value, expected_code
):
    tenant = str(uuid4())
    service = _service(durable_db)
    admitted = await service.admit(
        "orders.increment", "1", {"amount": 1}, _reference(tenant)
    )
    scope = tenant_scope(tenant)
    with _tenant_context(scope):
        if column == "principal_reference":
            await durable_db.execute(
                "UPDATE aksara_operations SET principal_reference = $2::jsonb WHERE id = $1",
                admitted.operation.id,
                json.dumps(value),
            )
        else:
            await durable_db.execute(
                f"UPDATE aksara_operations SET {column} = $2 WHERE id = $1",
                admitted.operation.id,
                value,
            )

    assert await service.claim(
        tenant_id=tenant,
        worker_id="worker-a",
        operation_id=admitted.operation.id,
    ) is None
    operation = await service.get(
        admitted.operation.id,
        tenant_id=tenant,
        principal=_principal(tenant),
    )
    assert operation.state is OperationState.FAILED
    assert operation.error["code"] == expected_code


@pytest.mark.asyncio
async def test_registered_approval_mode_must_match_admitted_operation(durable_db):
    tenant = str(uuid4())
    service = _service(durable_db)
    admitted = await service.admit(
        "orders.increment", "1", {"amount": 1}, _reference(tenant)
    )
    service.actions.register(
        DurableAction(
            name="orders.increment",
            version="1",
            handler=_handler,
            effect_class=EffectClass.POSTGRES_ATOMIC,
            approval_required=True,
        ),
        replace=True,
    )

    assert await service.claim(
        tenant_id=tenant,
        worker_id="worker-a",
        operation_id=admitted.operation.id,
    ) is None
    operation = await service.get(
        admitted.operation.id,
        tenant_id=tenant,
        principal=_principal(tenant),
    )
    assert operation.state is OperationState.FAILED
    assert operation.error["code"] == "action_version_unavailable"


@pytest.mark.asyncio
async def test_cross_scope_durable_call_is_rejected_inside_active_transaction(
    durable_db,
):
    tenant = str(uuid4())
    other_tenant = str(uuid4())
    service = _service(durable_db)

    with _tenant_context(tenant_scope(tenant)):
        async with atomic(db=durable_db) as connection:
            assert await service.check_deployment(tenant_id=tenant) == set()
            with pytest.raises(DurableConfigurationError, match="cannot change"):
                await service.check_deployment(tenant_id=other_tenant)
            assert await connection.fetchval(
                "SELECT current_setting('aksara.current_tenant_id', true)"
            ) == tenant_scope(tenant)


@pytest.mark.asyncio
async def test_tampered_command_fails_before_attempt_creation(durable_db):
    tenant = str(uuid4())
    service = _service(durable_db)
    admitted = await service.admit(
        "orders.increment", "1", {"amount": 1}, _reference(tenant)
    )
    scope = tenant_scope(tenant)
    with _tenant_context(scope):
        await durable_db.execute(
            """
            UPDATE aksara_operation_commands
            SET payload = '{"amount": 999}'::jsonb
            WHERE operation_id = $1
            """,
            admitted.operation.id,
        )

    assert await service.claim(
        tenant_id=tenant,
        worker_id="worker-a",
        operation_id=admitted.operation.id,
    ) is None
    operation = await service.get(
        admitted.operation.id,
        tenant_id=tenant,
        principal=_principal(tenant),
    )
    assert operation.state is OperationState.FAILED
    assert operation.error["code"] == "invalid_command"
    assert operation.attempt_count == 0


@pytest.mark.asyncio
async def test_application_namespace_is_an_operation_authority_boundary(durable_db):
    tenant = str(uuid4())
    reference = _reference(tenant)
    owner = _service(durable_db, namespace="application-a")
    outsider = _service(durable_db, namespace="application-b")
    admitted = await owner.admit(
        "orders.increment",
        "1",
        {"amount": 1},
        reference,
        idempotency_key="shared-client-key",
    )

    with pytest.raises(OperationNotFound):
        await outsider.get(
            admitted.operation.id,
            tenant_id=tenant,
            principal=_principal(tenant),
        )
    with pytest.raises(OperationNotFound):
        await outsider.request_cancellation(
            admitted.operation.id,
            tenant_id=tenant,
            principal=_principal(tenant),
            requester_reference=reference,
        )
    assert await outsider.claim(
        tenant_id=tenant,
        worker_id="wrong-application",
        operation_id=admitted.operation.id,
    ) is None
    assert await outsider.pending_outbox(
        tenant_id=tenant,
        principal=Principal.system(tenant_id=tenant),
    ) == []
    assert await outsider.check_deployment(tenant_id=tenant) == set()

    independent = await outsider.admit(
        "orders.increment",
        "1",
        {"amount": 1},
        reference,
        idempotency_key="shared-client-key",
    )
    assert independent.operation.id != admitted.operation.id


@pytest.mark.asyncio
async def test_decision_and_cancellation_provenance_must_match_current_actor(durable_db):
    tenant = str(uuid4())
    service = _service(durable_db, approval=True)
    admitted = await service.admit(
        "orders.increment", "1", {"amount": 1}, _reference(tenant)
    )
    forged = PrincipalReference(
        resolver_key="test",
        resolver_version="1",
        identity_namespace="test-app",
        principal_kind="user",
        subject_id="different-user",
        tenant_id=tenant,
    )

    with pytest.raises(AuthorizationDenied):
        await service.decide_approval(
            admitted.operation.id,
            tenant_id=tenant,
            approver=_principal(tenant),
            approver_reference=forged,
            approve=True,
        )
    with pytest.raises(AuthorizationDenied):
        await service.request_cancellation(
            admitted.operation.id,
            tenant_id=tenant,
            principal=_principal(tenant),
            requester_reference=forged,
        )

    forged_kind = PrincipalReference(
        resolver_key="test",
        resolver_version="1",
        identity_namespace="test-app",
        principal_kind="agent",
        subject_id="user-1",
        tenant_id=tenant,
    )
    with pytest.raises(AuthorizationDenied):
        await service.request_cancellation(
            admitted.operation.id,
            tenant_id=tenant,
            principal=_principal(tenant),
            requester_reference=forged_kind,
        )


@pytest.mark.asyncio
async def test_approval_binding_tamper_fails_closed(durable_db):
    tenant = str(uuid4())
    service = _service(durable_db, approval=True)
    admitted = await service.admit(
        "orders.increment", "1", {"amount": 1}, _reference(tenant)
    )
    scope = tenant_scope(tenant)
    with _tenant_context(scope):
        await durable_db.execute(
            """
            UPDATE aksara_operation_approval_decisions
            SET canonical_input_hash = repeat('0', 64)
            WHERE operation_id = $1
            """,
            admitted.operation.id,
        )

    with pytest.raises(ApprovalConflict, match="immutable operation binding"):
        await service.decide_approval(
            admitted.operation.id,
            tenant_id=tenant,
            approver=_principal(tenant),
            approver_reference=_reference(tenant),
            approve=True,
        )
    operation = await service.get(
        admitted.operation.id,
        tenant_id=tenant,
        principal=_principal(tenant),
    )
    assert operation.state is OperationState.WAITING_FOR_APPROVAL


@pytest.mark.asyncio
async def test_concurrent_approval_decisions_have_one_winner(durable_db):
    tenant = str(uuid4())
    service = _service(durable_db, approval=True)
    admitted = await service.admit(
        "orders.increment", "1", {"amount": 1}, _reference(tenant)
    )

    outcomes = await asyncio.gather(
        service.decide_approval(
            admitted.operation.id,
            tenant_id=tenant,
            approver=_principal(tenant),
            approver_reference=_reference(tenant),
            approve=True,
        ),
        service.decide_approval(
            admitted.operation.id,
            tenant_id=tenant,
            approver=_principal(tenant),
            approver_reference=_reference(tenant),
            approve=False,
        ),
        return_exceptions=True,
    )

    assert sum(isinstance(outcome, ApprovalConflict) for outcome in outcomes) == 1
    winners = [outcome for outcome in outcomes if not isinstance(outcome, Exception)]
    assert len(winners) == 1
    assert winners[0].state in {OperationState.READY, OperationState.CANCELLED}


@pytest.mark.asyncio
async def test_approval_authorizer_uses_current_approver(durable_db):
    tenant = str(uuid4())
    service = _service(
        durable_db,
        approval=True,
        approval_authorizer=lambda principal, _command: principal.user_id == "approver-1",
    )
    admitted = await service.admit(
        "orders.increment", "1", {"amount": 1}, _reference(tenant)
    )

    with pytest.raises(AuthorizationDenied):
        await service.decide_approval(
            admitted.operation.id,
            tenant_id=tenant,
            approver=_principal(tenant),
            approver_reference=_reference(tenant),
            approve=True,
        )
    approver_reference = PrincipalReference(
        resolver_key="test",
        resolver_version="1",
        identity_namespace="test-app",
        principal_kind="user",
        subject_id="approver-1",
        tenant_id=tenant,
    )
    approved = await service.decide_approval(
        admitted.operation.id,
        tenant_id=tenant,
        approver=Principal.for_user(
            "approver-1",
            tenant_id=tenant,
            scopes=("orders:write",),
        ),
        approver_reference=approver_reference,
        approve=True,
    )
    assert approved.state is OperationState.READY


@pytest.mark.asyncio
async def test_consumed_approval_survives_attempt_reclaim_without_second_decision(
    durable_db,
):
    tenant = str(uuid4())
    service = _service(durable_db, approval=True)
    reference = _reference(tenant)
    admitted = await service.admit(
        "orders.increment", "1", {"amount": 1}, reference
    )
    await service.decide_approval(
        admitted.operation.id,
        tenant_id=tenant,
        approver=_principal(tenant),
        approver_reference=reference,
        approve=True,
    )
    first = await service.claim(
        tenant_id=tenant,
        worker_id="worker-a",
        operation_id=admitted.operation.id,
        lease_seconds=0.03,
    )
    assert first is not None
    await asyncio.sleep(0.05)

    replacement = await service.claim(
        tenant_id=tenant,
        worker_id="worker-b",
        operation_id=admitted.operation.id,
    )

    assert replacement is not None
    assert replacement.ordinal == 2
    assert replacement.fence == first.fence + 1
    scope = tenant_scope(tenant)
    with _tenant_context(scope):
        decision = await durable_db.fetchrow(
            """
            SELECT state, consumed_at
            FROM aksara_operation_approval_decisions
            WHERE operation_id = $1
            """,
            admitted.operation.id,
        )
    assert decision["state"] == "approved"
    assert decision["consumed_at"] is not None


@pytest.mark.asyncio
async def test_unconsumed_approval_expiry_closes_operation(durable_db):
    tenant = str(uuid4())
    service = _service(durable_db, approval=True)
    reference = _reference(tenant)
    admitted = await service.admit(
        "orders.increment",
        "1",
        {"amount": 1},
        reference,
        approval_expires_at=datetime.now(UTC) + timedelta(milliseconds=30),
    )
    await service.decide_approval(
        admitted.operation.id,
        tenant_id=tenant,
        approver=_principal(tenant),
        approver_reference=reference,
        approve=True,
    )
    await asyncio.sleep(0.05)

    claim = await service.claim(
        tenant_id=tenant,
        worker_id="worker-a",
        operation_id=admitted.operation.id,
    )

    assert claim is None
    expired = await service.get(
        admitted.operation.id,
        tenant_id=tenant,
        principal=_principal(tenant),
    )
    assert expired.state is OperationState.EXPIRED
    assert expired.error["code"] == "approval_expired"
    history = await service.history(
        admitted.operation.id,
        tenant_id=tenant,
        principal=_principal(tenant),
    )
    assert history[0].event == "approval_expired"


@pytest.mark.asyncio
async def test_operation_deadline_prevents_late_approval(durable_db):
    tenant = str(uuid4())
    service = _service(durable_db, approval=True)
    reference = _reference(tenant)
    admitted = await service.admit(
        "orders.increment", "1", {"amount": 1}, reference
    )
    scope = tenant_scope(tenant)
    with _tenant_context(scope):
        await durable_db.execute(
            """
            UPDATE aksara_operations
            SET deadline_at = created_at + INTERVAL '1 millisecond'
            WHERE id = $1
            """,
            admitted.operation.id,
        )
    await asyncio.sleep(0.01)

    expired = await service.decide_approval(
        admitted.operation.id,
        tenant_id=tenant,
        approver=_principal(tenant),
        approver_reference=reference,
        approve=True,
    )

    assert expired.state is OperationState.EXPIRED
    assert expired.error["code"] == "deadline_expired"


@pytest.mark.asyncio
async def test_claim_sweeps_expired_waiting_approval(durable_db):
    tenant = str(uuid4())
    service = _service(durable_db, approval=True)
    admitted = await service.admit(
        "orders.increment",
        "1",
        {"amount": 1},
        _reference(tenant),
        approval_expires_at=datetime.now(UTC) + timedelta(milliseconds=10),
    )
    await asyncio.sleep(0.03)

    claim = await service.claim(
        tenant_id=tenant,
        worker_id="worker-a",
        operation_id=admitted.operation.id,
    )

    assert claim is None
    expired = await service.get(
        admitted.operation.id,
        tenant_id=tenant,
        principal=_principal(tenant),
    )
    assert expired.state is OperationState.EXPIRED
    assert expired.error["code"] == "approval_expired"


@pytest.mark.asyncio
async def test_attempt_budget_survives_retry_and_closes_at_limit(durable_db):
    tenant = str(uuid4())
    service = _service(durable_db)
    admitted = await service.admit(
        "orders.increment",
        "1",
        {"amount": 1},
        _reference(tenant),
        max_attempts=2,
    )
    first = await service.claim(
        tenant_id=tenant,
        worker_id="worker-a",
        operation_id=admitted.operation.id,
    )
    assert first is not None
    retry = await service.fail_attempt(
        first,
        code="temporary_failure",
        message="retry",
        retryable=True,
    )
    assert retry.state is OperationState.READY
    second = await service.claim(
        tenant_id=tenant,
        worker_id="worker-b",
        operation_id=admitted.operation.id,
    )
    assert second is not None

    terminal = await service.fail_attempt(
        second,
        code="temporary_failure",
        message="retry",
        retryable=True,
    )

    assert terminal.state is OperationState.FAILED
    assert terminal.attempt_count == 2
    assert terminal.error["retryable"] is False
    assert await service.claim(
        tenant_id=tenant,
        worker_id="worker-c",
        operation_id=admitted.operation.id,
    ) is None
