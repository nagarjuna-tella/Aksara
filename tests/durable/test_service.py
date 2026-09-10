"""Durable admission, identity, approval and ownership invariants."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from aksara.durable import (
    ApprovalConflict,
    AuthorizationDenied,
    DurableAction,
    DurableActionRegistry,
    DurableOperationService,
    EffectClass,
    IdempotencyConflict,
    OperationNotFound,
    OperationState,
    PrincipalReference,
)
from aksara.durable.errors import OwnershipLost
from aksara.durable.service import _tenant_context
from aksara.durable.types import tenant_scope
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
):
    actions = DurableActionRegistry()
    actions.register(
        DurableAction(
            name="orders.increment",
            version="1",
            handler=_handler,
            effect_class=EffectClass.POSTGRES_ATOMIC,
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
        principal=_principal(tenant),
    )) == 2

    with pytest.raises(OperationNotFound):
        await service.get(
            admitted.operation.id,
            tenant_id=other_tenant,
            principal=_principal(other_tenant),
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
        principal=_principal(tenant),
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
        approver=Principal.for_user("approver-1", tenant_id=tenant),
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
