"""Current principal resolution and reauthorization failure contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from aksara.durable import (
    DurableAction,
    DurableActionRegistry,
    DurableOperationService,
    EffectClass,
    ExternalOperationExecutor,
    OperationState,
    PostgresAtomicExecutor,
    PrincipalReference,
    PrincipalResolution,
    PrincipalResolverRegistry,
    ReadOnlyExecutor,
    ResolutionStatus,
)
from aksara.security.principal import Principal


def _reference(tenant: str) -> PrincipalReference:
    return PrincipalReference(
        resolver_key="current-identity",
        resolver_version="1",
        identity_namespace="tests",
        principal_kind="user",
        subject_id="user-1",
        tenant_id=tenant,
    )


def _runtime(
    durable_db,
    resolver,
    *,
    authorizer=None,
    effect_class: EffectClass = EffectClass.POSTGRES_ATOMIC,
):
    calls: list[dict] = []

    async def handler(_context, command):
        calls.append(command)
        return {"mutated": True}

    actions = DurableActionRegistry()
    actions.register(
        DurableAction(
            name="authorization.mutate",
            version="1",
            handler=handler,
            effect_class=effect_class,
            required_scopes=("operation:write",),
            authorizer=authorizer,
        )
    )
    resolvers = PrincipalResolverRegistry()
    if resolver is not None:
        resolvers.register("current-identity", "1", resolver)
    service = DurableOperationService(
        durable_db,
        application_namespace="authorization-tests",
        actions=actions,
        resolvers=resolvers,
        retention_seconds=60,
        idempotency_seconds=60,
    )
    executor = {
        EffectClass.POSTGRES_ATOMIC: PostgresAtomicExecutor,
        EffectClass.READ_ONLY: ReadOnlyExecutor,
        EffectClass.EXTERNAL_AT_LEAST_ONCE: ExternalOperationExecutor,
    }[effect_class](service)
    return service, executor, calls


async def _execute(service, executor, tenant: str):
    admitted = await service.admit(
        "authorization.mutate", "1", {"value": 1}, _reference(tenant)
    )
    claim = await service.claim(
        tenant_id=tenant,
        worker_id="authorization-worker",
        operation_id=admitted.operation.id,
    )
    assert claim is not None
    return await executor.execute(claim)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        (ResolutionStatus.DELETED, "principal_deleted"),
        (ResolutionStatus.DISABLED, "principal_disabled"),
        (ResolutionStatus.MEMBERSHIP_REMOVED, "tenant_membership_removed"),
        (ResolutionStatus.MALFORMED, "malformed_principal_provenance"),
        (ResolutionStatus.REVOKED, "identity_revoked"),
    ],
)
async def test_permanent_resolution_outcomes_fail_before_effect(
    durable_db, status, expected_code
):
    tenant = str(uuid4())
    service, executor, calls = _runtime(
        durable_db,
        lambda _reference: PrincipalResolution(status, detail="current identity denied"),
    )

    operation = await _execute(service, executor, tenant)

    assert operation.state is OperationState.FAILED
    assert operation.error["code"] == expected_code
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("resolver_mode", ["temporary", "exception"])
async def test_temporary_identity_failure_retries_same_operation(
    durable_db, resolver_mode
):
    tenant = str(uuid4())

    def resolver(_reference):
        if resolver_mode == "exception":
            raise ConnectionError("identity store unavailable")
        return PrincipalResolution(
            ResolutionStatus.TEMPORARILY_UNAVAILABLE,
            detail="identity store unavailable",
        )

    service, executor, calls = _runtime(durable_db, resolver)
    operation = await _execute(service, executor, tenant)

    assert operation.state is OperationState.READY
    assert operation.error["code"] == "identity_resolution_unavailable"
    assert operation.error["retryable"] is True
    assert calls == []


@pytest.mark.asyncio
async def test_missing_resolver_version_fails_closed(durable_db):
    tenant = str(uuid4())
    service, executor, calls = _runtime(durable_db, None)

    operation = await _execute(service, executor, tenant)

    assert operation.state is OperationState.FAILED
    assert operation.error["code"] == "identity_resolver_missing"
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "principal",
    [
        Principal.for_user(
            "user-1",
            tenant_id="wrong-tenant",
            scopes=("operation:write",),
        ),
        Principal.for_user(
            "different-user",
            tenant_id="TENANT",
            scopes=("operation:write",),
        ),
    ],
)
async def test_resolved_identity_must_match_durable_provenance(durable_db, principal):
    tenant = str(uuid4())
    if principal.tenant_id == "TENANT":
        principal = Principal.for_user(
            principal.user_id or "different-user",
            tenant_id=tenant,
            scopes=principal.scopes,
        )
    service, executor, calls = _runtime(
        durable_db,
        lambda _reference: PrincipalResolution.resolved(principal),
    )

    operation = await _execute(service, executor, tenant)

    assert operation.state is OperationState.FAILED
    assert operation.error["code"] == "identity_revoked"
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("denial", ["scope", "expiry", "policy"])
async def test_current_scope_expiry_and_action_policy_are_rechecked(durable_db, denial):
    tenant = str(uuid4())
    scopes = () if denial == "scope" else ("operation:write",)
    expires_at = (
        datetime.now(UTC) - timedelta(seconds=1)
        if denial == "expiry"
        else None
    )
    principal = Principal(
        user_id="user-1",
        tenant_id=tenant,
        scopes=scopes,
        auth_method="jwt",
        is_authenticated=True,
        expires_at=expires_at,
    )
    service, executor, calls = _runtime(
        durable_db,
        lambda _reference: PrincipalResolution.resolved(principal),
        authorizer=(lambda _principal, _command: False)
        if denial == "policy"
        else None,
    )

    operation = await _execute(service, executor, tenant)

    assert operation.state is OperationState.FAILED
    assert operation.error["code"] == "authorization_denied"
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "effect_class",
    [
        EffectClass.POSTGRES_ATOMIC,
        EffectClass.READ_ONLY,
        EffectClass.EXTERNAL_AT_LEAST_ONCE,
    ],
)
async def test_authorizer_exception_closes_attempt_before_handler(
    durable_db, effect_class
):
    tenant = str(uuid4())

    def unavailable_authorizer(_principal, _command):
        raise ConnectionError("authorization service unavailable")

    service, executor, calls = _runtime(
        durable_db,
        lambda _reference: PrincipalResolution.resolved(
            Principal.for_user(
                "user-1", tenant_id=tenant, scopes=("operation:write",)
            )
        ),
        authorizer=unavailable_authorizer,
        effect_class=effect_class,
    )

    operation = await _execute(service, executor, tenant)

    assert operation.state is OperationState.FAILED
    assert operation.error["code"] == "executor_error"
    assert operation.error["message"] == "authorization service unavailable"
    assert calls == []


@pytest.mark.asyncio
async def test_read_only_authorization_is_rechecked_after_lifecycle_boundary(durable_db):
    tenant = str(uuid4())
    authorized = True
    service, _executor, calls = _runtime(
        durable_db,
        lambda _reference: PrincipalResolution.resolved(
            Principal.for_user(
                "user-1", tenant_id=tenant, scopes=("operation:write",)
            )
        ),
        authorizer=lambda _principal, _command: authorized,
        effect_class=EffectClass.READ_ONLY,
    )
    executor = ReadOnlyExecutor(service)

    async def revoke_after_boundary(name: str):
        nonlocal authorized
        if name == "after_lock":
            authorized = False

    executor._identity._boundary_hook = revoke_after_boundary

    operation = await _execute(service, executor, tenant)

    assert operation.state is OperationState.FAILED
    assert operation.error["code"] == "authorization_denied"
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("effect_class", "executor_type"),
    [
        (EffectClass.POSTGRES_ATOMIC, PostgresAtomicExecutor),
        (EffectClass.READ_ONLY, ReadOnlyExecutor),
    ],
)
async def test_identity_is_resolved_again_after_lifecycle_boundary(
    durable_db, effect_class, executor_type
):
    tenant = str(uuid4())
    resolution_count = 0

    def resolver(_reference):
        nonlocal resolution_count
        resolution_count += 1
        scopes = ("operation:write",) if resolution_count == 1 else ()
        return PrincipalResolution.resolved(
            Principal.for_user("user-1", tenant_id=tenant, scopes=scopes)
        )

    service, _executor, calls = _runtime(
        durable_db,
        resolver,
        effect_class=effect_class,
    )
    operation = await _execute(service, executor_type(service), tenant)

    assert operation.state is OperationState.FAILED
    assert operation.error["code"] == "authorization_denied"
    assert resolution_count == 2
    assert calls == []
