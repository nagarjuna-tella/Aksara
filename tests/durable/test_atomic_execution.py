"""Production postgres_atomic execution and failure-boundary tests."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from asyncpg import CheckViolationError

from aksara.context_state import tenant_id_var
from aksara.db import Database
from aksara.db.transaction import TransactionManager, atomic
from aksara.durable import (
    CancellationConflict,
    DurableAction,
    DurableActionRegistry,
    DurableOperationService,
    EffectClass,
    OperationState,
    PostgresAtomicExecutor,
    PrincipalReference,
    PrincipalResolution,
    PrincipalResolverRegistry,
    ReadOnlyExecutor,
)
from aksara.durable.errors import OwnershipLost
from aksara.security.principal import Principal


@contextmanager
def _tenant(tenant_id: str):
    token = tenant_id_var.set(tenant_id)
    try:
        yield
    finally:
        tenant_id_var.reset(token)


def _principal(tenant: str, *, scopes: tuple[str, ...] = ("counter:write",)) -> Principal:
    return Principal.for_user("user-1", tenant_id=tenant, scopes=scopes)


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
    durable_db: Database,
    tenant: str,
    handler: Callable[..., Any],
    *,
    current_principal: Principal | None = None,
    retry_classifier=None,
    authorizer=None,
):
    actions = DurableActionRegistry()
    actions.register(
        DurableAction(
            name="counter.increment",
            version="1",
            handler=handler,
            effect_class=EffectClass.POSTGRES_ATOMIC,
            required_scopes=("counter:write",),
            retry_classifier=retry_classifier,
            authorizer=authorizer,
        )
    )
    resolvers = PrincipalResolverRegistry()
    resolved = current_principal or _principal(tenant)
    resolvers.register("test", "1", lambda _reference: PrincipalResolution.resolved(resolved))
    service = DurableOperationService(
        durable_db,
        application_namespace="atomic-tests",
        actions=actions,
        resolvers=resolvers,
        retention_seconds=60,
        idempotency_seconds=60,
    )
    return service, PostgresAtomicExecutor(service)


async def _insert_counter(db: Database, tenant: str, counter_id: UUID) -> None:
    with _tenant(tenant):
        await db.execute(
            """
            INSERT INTO durable_test_counters (id, tenant_scope, mutation_counter)
            VALUES ($1, $2, 0)
            """,
            counter_id,
            tenant,
        )


async def _counter(db: Database, tenant: str, counter_id: UUID) -> int:
    with _tenant(tenant):
        return int(
            await db.fetchval(
                "SELECT mutation_counter FROM durable_test_counters WHERE id = $1",
                counter_id,
            )
        )


async def _admit_claim(service, tenant: str, counter_id: UUID):
    admitted = await service.admit(
        "counter.increment",
        "1",
        {"counter_id": str(counter_id)},
        _reference(tenant),
        idempotency_key=f"counter:{counter_id}",
    )
    claim = await service.claim(
        tenant_id=tenant,
        worker_id="worker-a",
        operation_id=admitted.operation.id,
    )
    assert claim is not None
    return admitted, claim


@pytest.mark.asyncio
async def test_mutation_attempt_success_and_operation_success_share_commit(durable_db):
    tenant, counter_id = str(uuid4()), uuid4()

    async def handler(context, command):
        await context.database.execute(
            """
            UPDATE durable_test_counters
            SET mutation_counter = mutation_counter + 1
            WHERE id = $1
            """,
            UUID(command["counter_id"]),
        )
        return {"counter": 1}

    service, executor = _runtime(durable_db, tenant, handler)
    await _insert_counter(durable_db, tenant, counter_id)
    _, claim = await _admit_claim(service, tenant, counter_id)

    completed = await executor.execute(claim)

    assert completed.state is OperationState.SUCCEEDED
    assert completed.result == {"counter": 1}
    assert await _counter(durable_db, tenant, counter_id) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "boundary",
    [
        "before_lock",
        "after_lock",
        "before_mutation",
        "after_mutation",
        "after_attempt_success",
        "after_operation_success",
        "before_commit",
    ],
)
async def test_every_precommit_boundary_rolls_back_as_one_unit(durable_db, boundary):
    tenant, counter_id = str(uuid4()), uuid4()

    async def handler(context, command):
        await context.database.execute(
            """
            UPDATE durable_test_counters
            SET mutation_counter = mutation_counter + 1
            WHERE id = $1
            """,
            UUID(command["counter_id"]),
        )
        return {"counter": 1}

    async def inject(name: str):
        if name == boundary:
            raise RuntimeError(f"injected at {name}")

    service, _ = _runtime(durable_db, tenant, handler)
    executor = PostgresAtomicExecutor(service, _boundary_hook=inject)
    await _insert_counter(durable_db, tenant, counter_id)
    _, claim = await _admit_claim(service, tenant, counter_id)

    completed = await executor.execute(claim)

    assert completed.state is OperationState.FAILED
    assert completed.error["code"] == "executor_error"
    assert await _counter(durable_db, tenant, counter_id) == 0


@pytest.mark.asyncio
async def test_handler_failure_rolls_back_mutation_before_terminal_failure(durable_db):
    tenant, counter_id = str(uuid4()), uuid4()

    async def handler(context, command):
        await context.database.execute(
            "UPDATE durable_test_counters SET mutation_counter = mutation_counter + 1 WHERE id = $1",
            UUID(command["counter_id"]),
        )
        raise RuntimeError("injected after mutation")

    service, executor = _runtime(durable_db, tenant, handler)
    await _insert_counter(durable_db, tenant, counter_id)
    _, claim = await _admit_claim(service, tenant, counter_id)

    completed = await executor.execute(claim)

    assert completed.state is OperationState.FAILED
    assert await _counter(durable_db, tenant, counter_id) == 0


@pytest.mark.asyncio
async def test_swallowed_database_error_invalidates_outer_boundary(durable_db):
    tenant, counter_id = str(uuid4()), uuid4()

    async def handler(context, command):
        try:
            await context.database.execute(
                "UPDATE durable_test_counters SET mutation_counter = -1 WHERE id = $1",
                UUID(command["counter_id"]),
            )
        except CheckViolationError:
            pass
        return {"unsafe": True}

    service, executor = _runtime(durable_db, tenant, handler)
    await _insert_counter(durable_db, tenant, counter_id)
    _, claim = await _admit_claim(service, tenant, counter_id)

    completed = await executor.execute(claim)

    assert completed.state is OperationState.FAILED
    assert completed.error["code"] == "internal_error"
    assert await _counter(durable_db, tenant, counter_id) == 0


@pytest.mark.asyncio
async def test_direct_pool_and_child_task_access_invalidate_boundary(durable_db):
    tenant, counter_id = str(uuid4()), uuid4()

    async def handler(context, _command):
        with pytest.raises(RuntimeError, match="direct pool access"):
            _ = context.database.pool

        child = asyncio.create_task(context.database.fetchval("SELECT 1"))
        with pytest.raises(RuntimeError, match="owning asyncio task"):
            await child
        return {"unsafe": True}

    service, executor = _runtime(durable_db, tenant, handler)
    await _insert_counter(durable_db, tenant, counter_id)
    _, claim = await _admit_claim(service, tenant, counter_id)

    completed = await executor.execute(claim)

    assert completed.state is OperationState.FAILED
    assert await _counter(durable_db, tenant, counter_id) == 0


@pytest.mark.asyncio
async def test_worker_thread_access_invalidates_boundary_when_error_is_swallowed(
    durable_db,
):
    tenant, counter_id = str(uuid4()), uuid4()

    async def handler(context, _command):
        def escape_to_thread():
            with pytest.raises(RuntimeError, match="owning asyncio task"):
                _ = context.database.pool

        await asyncio.to_thread(escape_to_thread)
        return {"unsafe": True}

    service, executor = _runtime(durable_db, tenant, handler)
    await _insert_counter(durable_db, tenant, counter_id)
    _, claim = await _admit_claim(service, tenant, counter_id)

    completed = await executor.execute(claim)

    assert completed.state is OperationState.FAILED
    assert completed.error["code"] == "internal_error"


@pytest.mark.asyncio
async def test_different_database_and_swallowed_savepoint_error_invalidate_boundary(
    durable_db,
):
    tenant, counter_id = str(uuid4()), uuid4()
    other_database = Database(durable_db.database_url, min_size=1, max_size=1)
    await other_database.connect()

    async def handler(context, command):
        with pytest.raises(RuntimeError, match="execution context Database"):
            async with atomic(db=other_database):
                pass
        async with atomic(db=context.database):
            try:
                await context.database.execute(
                    "UPDATE durable_test_counters SET mutation_counter = -1 WHERE id = $1",
                    UUID(command["counter_id"]),
                )
            except CheckViolationError:
                pass
        return {"unsafe": True}

    try:
        service, executor = _runtime(durable_db, tenant, handler)
        await _insert_counter(durable_db, tenant, counter_id)
        _, claim = await _admit_claim(service, tenant, counter_id)

        completed = await executor.execute(claim)

        assert completed.state is OperationState.FAILED
        assert completed.error["code"] == "internal_error"
        assert await _counter(durable_db, tenant, counter_id) == 0
    finally:
        await other_database.disconnect()
        Database._instance = durable_db


@pytest.mark.asyncio
async def test_stale_claim_cannot_reach_application_mutation(durable_db):
    tenant, counter_id = str(uuid4()), uuid4()
    calls = 0

    async def handler(context, command):
        nonlocal calls
        calls += 1
        await context.database.execute(
            "UPDATE durable_test_counters SET mutation_counter = mutation_counter + 1 WHERE id = $1",
            UUID(command["counter_id"]),
        )
        return {"ok": True}

    service, executor = _runtime(durable_db, tenant, handler)
    await _insert_counter(durable_db, tenant, counter_id)
    admitted = await service.admit(
        "counter.increment", "1", {"counter_id": str(counter_id)}, _reference(tenant)
    )
    first = await service.claim(
        tenant_id=tenant,
        worker_id="worker-a",
        operation_id=admitted.operation.id,
        lease_seconds=0.03,
    )
    assert first is not None
    await asyncio.sleep(0.05)
    second = await service.claim(
        tenant_id=tenant,
        worker_id="worker-b",
        operation_id=admitted.operation.id,
    )
    assert second is not None

    with pytest.raises(OwnershipLost):
        await executor.execute(first)
    assert calls == 0
    assert await _counter(durable_db, tenant, counter_id) == 0

    completed = await executor.execute(second)
    assert completed.state is OperationState.SUCCEEDED
    assert calls == 1
    assert await _counter(durable_db, tenant, counter_id) == 1


@pytest.mark.asyncio
async def test_current_authorization_is_required_before_mutation(durable_db):
    tenant, counter_id = str(uuid4()), uuid4()
    called = False

    async def handler(_context, _command):
        nonlocal called
        called = True

    service, executor = _runtime(
        durable_db,
        tenant,
        handler,
        current_principal=_principal(tenant, scopes=()),
    )
    await _insert_counter(durable_db, tenant, counter_id)
    _, claim = await _admit_claim(service, tenant, counter_id)

    completed = await executor.execute(claim)

    assert completed.state is OperationState.FAILED
    assert completed.error["code"] == "authorization_denied"
    assert called is False
    assert await _counter(durable_db, tenant, counter_id) == 0


@pytest.mark.asyncio
async def test_authorization_is_rechecked_after_operation_lock(durable_db):
    tenant, counter_id = str(uuid4()), uuid4()
    authorized = True
    called = False

    async def authorize(_principal, _command):
        return authorized

    async def handler(_context, _command):
        nonlocal called
        called = True

    async def revoke_after_lock(name: str):
        nonlocal authorized
        if name == "after_lock":
            authorized = False

    service, _ = _runtime(
        durable_db,
        tenant,
        handler,
        authorizer=authorize,
    )
    executor = PostgresAtomicExecutor(service, _boundary_hook=revoke_after_lock)
    await _insert_counter(durable_db, tenant, counter_id)
    _, claim = await _admit_claim(service, tenant, counter_id)

    completed = await executor.execute(claim)

    assert completed.state is OperationState.FAILED
    assert completed.error["code"] == "authorization_denied"
    assert called is False


@pytest.mark.asyncio
async def test_atomic_success_cannot_commit_after_lease_expires(durable_db):
    tenant, counter_id = str(uuid4()), uuid4()

    async def handler(context, command):
        await context.database.execute(
            """
            UPDATE durable_test_counters
            SET mutation_counter = mutation_counter + 1
            WHERE id = $1
            """,
            UUID(command["counter_id"]),
        )
        await asyncio.sleep(0.05)
        return {"counter": 1}

    service, executor = _runtime(durable_db, tenant, handler)
    await _insert_counter(durable_db, tenant, counter_id)
    admitted = await service.admit(
        "counter.increment",
        "1",
        {"counter_id": str(counter_id)},
        _reference(tenant),
    )
    first = await service.claim(
        tenant_id=tenant,
        worker_id="worker-a",
        operation_id=admitted.operation.id,
        lease_seconds=0.03,
    )
    assert first is not None

    with pytest.raises(OwnershipLost):
        await executor.execute(first)
    assert await _counter(durable_db, tenant, counter_id) == 0

    replacement = await service.claim(
        tenant_id=tenant,
        worker_id="worker-b",
        operation_id=admitted.operation.id,
    )
    assert replacement is not None
    completed = await executor.execute(replacement)
    assert completed.state is OperationState.SUCCEEDED
    assert await _counter(durable_db, tenant, counter_id) == 1


@pytest.mark.asyncio
async def test_lost_commit_acknowledgement_rereads_authoritative_success(
    durable_db, monkeypatch
):
    tenant, counter_id = str(uuid4()), uuid4()

    async def handler(context, command):
        await context.database.execute(
            "UPDATE durable_test_counters SET mutation_counter = mutation_counter + 1 WHERE id = $1",
            UUID(command["counter_id"]),
        )
        return {"counter": 1}

    service, executor = _runtime(durable_db, tenant, handler)
    await _insert_counter(durable_db, tenant, counter_id)
    _, claim = await _admit_claim(service, tenant, counter_id)
    original_exit = TransactionManager.__aexit__
    injected = False

    async def lost_after_commit(manager, exc_type, exc_val, exc_tb):
        nonlocal injected
        await original_exit(manager, exc_type, exc_val, exc_tb)
        if not injected and exc_type is None:
            injected = True
            raise ConnectionError("simulated lost commit acknowledgement")

    monkeypatch.setattr(TransactionManager, "__aexit__", lost_after_commit)

    completed = await executor.execute(claim)

    assert completed.state is OperationState.SUCCEEDED
    assert await _counter(durable_db, tenant, counter_id) == 1


@pytest.mark.asyncio
async def test_read_only_executor_rejects_application_writes(durable_db):
    tenant, counter_id = str(uuid4()), uuid4()

    async def handler(context, command):
        await context.database.execute(
            """
            UPDATE durable_test_counters
            SET mutation_counter = mutation_counter + 1
            WHERE id = $1
            """,
            UUID(command["counter_id"]),
        )
        return {"unsafe": True}

    actions = DurableActionRegistry()
    actions.register(
        DurableAction(
            name="counter.read-only",
            version="1",
            handler=handler,
            effect_class=EffectClass.READ_ONLY,
            required_scopes=("counter:write",),
        )
    )
    resolvers = PrincipalResolverRegistry()
    resolvers.register(
        "test",
        "1",
        lambda _reference: PrincipalResolution.resolved(_principal(tenant)),
    )
    service = DurableOperationService(
        durable_db,
        application_namespace="atomic-tests",
        actions=actions,
        resolvers=resolvers,
        retention_seconds=60,
        idempotency_seconds=60,
    )
    await _insert_counter(durable_db, tenant, counter_id)
    admitted = await service.admit(
        "counter.read-only",
        "1",
        {"counter_id": str(counter_id)},
        _reference(tenant),
    )
    claim = await service.claim(
        tenant_id=tenant,
        worker_id="read-only-worker",
        operation_id=admitted.operation.id,
    )
    assert claim is not None

    completed = await ReadOnlyExecutor(service).execute(claim)

    assert completed.state is OperationState.FAILED
    assert completed.error["code"] == "executor_error"
    assert await _counter(durable_db, tenant, counter_id) == 0


@pytest.mark.asyncio
async def test_read_only_cancellation_wins_before_completion(durable_db):
    tenant = str(uuid4())
    handler_started = asyncio.Event()
    allow_handler_completion = asyncio.Event()

    async def handler(_context, _command):
        handler_started.set()
        await allow_handler_completion.wait()
        return {"read": True}

    actions = DurableActionRegistry()
    actions.register(
        DurableAction(
            name="counter.read-only",
            version="1",
            handler=handler,
            effect_class=EffectClass.READ_ONLY,
            required_scopes=("counter:write",),
        )
    )
    resolvers = PrincipalResolverRegistry()
    resolvers.register(
        "test",
        "1",
        lambda _reference: PrincipalResolution.resolved(_principal(tenant)),
    )
    service = DurableOperationService(
        durable_db,
        application_namespace="atomic-tests",
        actions=actions,
        resolvers=resolvers,
        retention_seconds=60,
        idempotency_seconds=60,
    )
    admitted = await service.admit(
        "counter.read-only", "1", {}, _reference(tenant)
    )
    claim = await service.claim(
        tenant_id=tenant,
        worker_id="read-only-worker",
        operation_id=admitted.operation.id,
    )
    assert claim is not None
    execution = asyncio.create_task(ReadOnlyExecutor(service).execute(claim))
    await handler_started.wait()

    requested = await service.request_cancellation(
        admitted.operation.id,
        tenant_id=tenant,
        principal=_principal(tenant),
        requester_reference=_reference(tenant),
    )
    assert requested.state is OperationState.RUNNING
    allow_handler_completion.set()

    completed = await execution
    assert completed.state is OperationState.CANCELLED


@pytest.mark.asyncio
async def test_success_and_cancellation_race_has_one_database_winner(durable_db):
    tenant, counter_id = str(uuid4()), uuid4()
    mutation_started = asyncio.Event()
    allow_completion = asyncio.Event()

    async def handler(context, command):
        await context.database.execute(
            """
            UPDATE durable_test_counters
            SET mutation_counter = mutation_counter + 1
            WHERE id = $1
            """,
            UUID(command["counter_id"]),
        )
        mutation_started.set()
        await allow_completion.wait()
        return {"counter": 1}

    service, executor = _runtime(durable_db, tenant, handler)
    await _insert_counter(durable_db, tenant, counter_id)
    admitted, claim = await _admit_claim(service, tenant, counter_id)
    execution = asyncio.create_task(executor.execute(claim))
    await mutation_started.wait()
    cancellation = asyncio.create_task(
        service.request_cancellation(
            admitted.operation.id,
            tenant_id=tenant,
            principal=_principal(tenant),
            requester_reference=_reference(tenant),
        )
    )
    await asyncio.sleep(0)
    allow_completion.set()

    completed, cancel_outcome = await asyncio.gather(
        execution, cancellation, return_exceptions=True
    )

    assert completed.state is OperationState.SUCCEEDED
    assert isinstance(cancel_outcome, CancellationConflict)
    assert await _counter(durable_db, tenant, counter_id) == 1


@pytest.mark.asyncio
async def test_cancellation_intent_wins_before_atomic_mutation(durable_db):
    tenant, counter_id = str(uuid4()), uuid4()
    called = False

    async def handler(_context, _command):
        nonlocal called
        called = True

    service, executor = _runtime(durable_db, tenant, handler)
    await _insert_counter(durable_db, tenant, counter_id)
    admitted, claim = await _admit_claim(service, tenant, counter_id)
    requested = await service.request_cancellation(
        admitted.operation.id,
        tenant_id=tenant,
        principal=_principal(tenant),
        requester_reference=_reference(tenant),
    )
    assert requested.state is OperationState.RUNNING

    completed = await executor.execute(claim)

    assert completed.state is OperationState.CANCELLED
    assert called is False
    assert await _counter(durable_db, tenant, counter_id) == 0


@pytest.mark.asyncio
async def test_deadline_after_claim_blocks_mutation_and_retains_expiry_metadata(
    durable_db,
):
    tenant, counter_id = str(uuid4()), uuid4()
    called = False

    async def handler(_context, _command):
        nonlocal called
        called = True

    service, executor = _runtime(durable_db, tenant, handler)
    await _insert_counter(durable_db, tenant, counter_id)
    admitted = await service.admit(
        "counter.increment",
        "1",
        {"counter_id": str(counter_id)},
        _reference(tenant),
        deadline_at=datetime.now(UTC) + timedelta(milliseconds=30),
    )
    claim = await service.claim(
        tenant_id=tenant,
        worker_id="worker-a",
        operation_id=admitted.operation.id,
    )
    assert claim is not None
    await asyncio.sleep(0.05)

    expired = await executor.execute(claim)

    assert expired.state is OperationState.EXPIRED
    assert expired.error["code"] == "deadline_expired"
    assert expired.error_expires_at is not None
    assert called is False
    assert await _counter(durable_db, tenant, counter_id) == 0
