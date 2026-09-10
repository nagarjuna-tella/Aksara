"""Existing tasks remain compatible and may execute linked Operations."""

from __future__ import annotations

from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest

from aksara.context_state import tenant_id_var
from aksara.durable import (
    DurableAction,
    DurableActionRegistry,
    DurableOperationService,
    EffectClass,
    OperationState,
    PrincipalReference,
    PrincipalResolution,
    PrincipalResolverRegistry,
)
from aksara.security.principal import Principal
from aksara.tasks import (
    TaskWorker,
    clear_task_registry,
    enqueue_operation_task,
    task,
)


@contextmanager
def _tenant(tenant_id: str):
    token = tenant_id_var.set(tenant_id)
    try:
        yield
    finally:
        tenant_id_var.reset(token)


def _runtime(durable_db, tenant: str):
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

    actions = DurableActionRegistry()
    actions.register(
        DurableAction(
            name="counter.task_increment",
            version="1",
            handler=handler,
            effect_class=EffectClass.POSTGRES_ATOMIC,
            executor_type="task",
            required_scopes=("counter:write",),
        )
    )
    resolvers = PrincipalResolverRegistry()
    resolvers.register(
        "test",
        "1",
        lambda _reference: PrincipalResolution.resolved(
            Principal.for_user(
                "user-1", tenant_id=tenant, scopes=("counter:write",)
            )
        ),
    )
    return DurableOperationService(
        durable_db,
        application_namespace="task-tests",
        actions=actions,
        resolvers=resolvers,
        retention_seconds=60,
        idempotency_seconds=60,
    )


def _reference(tenant: str) -> PrincipalReference:
    return PrincipalReference(
        resolver_key="test",
        resolver_version="1",
        identity_namespace="tests",
        principal_kind="user",
        subject_id="user-1",
        tenant_id=tenant,
    )


@pytest.mark.asyncio
async def test_task_backed_operation_uses_operation_attempt_as_authority(durable_db):
    tenant, counter_id = str(uuid4()), uuid4()
    service = _runtime(durable_db, tenant)
    with _tenant(tenant):
        await durable_db.execute(
            "INSERT INTO durable_test_counters (id, tenant_scope) VALUES ($1, $2)",
            counter_id,
            tenant,
        )
    admitted = await service.admit(
        "counter.task_increment",
        "1",
        {"counter_id": str(counter_id)},
        _reference(tenant),
    )
    queued = await enqueue_operation_task(
        admitted.operation.id,
        service=service,
        tenant_id=tenant,
    )
    duplicate = await enqueue_operation_task(
        admitted.operation.id,
        service=service,
        tenant_id=tenant,
    )
    assert duplicate.id == queued.id
    assert queued.operation_id == admitted.operation.id

    worker = TaskWorker(
        durable_db,
        durable_service=service,
        worker_id="durable-task-worker",
    )
    completed_task = await worker.poll_once()

    assert completed_task is not None
    assert completed_task.status == "completed"
    assert completed_task.result == {"counter": 1}
    operation = await service.get(
        admitted.operation.id,
        tenant_id=tenant,
        principal=Principal.for_user("user-1", tenant_id=tenant),
    )
    assert operation.state is OperationState.SUCCEEDED
    assert operation.attempt_count == 1
    with _tenant(tenant):
        assert await durable_db.fetchval(
            "SELECT mutation_counter FROM durable_test_counters WHERE id = $1",
            counter_id,
        ) == 1


@pytest.mark.asyncio
async def test_unlinked_task_behavior_is_unchanged_with_durable_schema(durable_db):
    clear_task_registry()

    @task(name="tests.v070.unlinked")
    async def unlinked(value: str):
        return {"value": value}

    try:
        queued = await unlinked.enqueue("unchanged", db=durable_db)
        assert queued.operation_id is None
        completed = await TaskWorker(durable_db).poll_once()
        assert completed is not None
        assert completed.id == queued.id
        assert completed.status == "completed"
        assert completed.result == {"value": "unchanged"}
    finally:
        clear_task_registry()


@pytest.mark.asyncio
async def test_stale_linked_task_recovery_restores_operation_tenant_scope(durable_db):
    tenant = str(uuid4())
    service = _runtime(durable_db, tenant)
    admitted = await service.admit(
        "counter.task_increment",
        "1",
        {"counter_id": str(uuid4())},
        _reference(tenant),
    )
    queued = await enqueue_operation_task(
        admitted.operation.id,
        service=service,
        tenant_id=tenant,
    )
    await durable_db.execute(
        """
        UPDATE aksara_tasks SET status = 'running',
            locked_at = clock_timestamp() - INTERVAL '10 seconds'
        WHERE id = $1
        """,
        queued.id,
    )
    worker = TaskWorker(
        durable_db,
        durable_service=service,
        stale_lock_timeout_seconds=1,
    )

    assert await worker.recover_stale_locks() == 1
    recovered = await durable_db.fetchrow(
        "SELECT status, locked_at FROM aksara_tasks WHERE id = $1", queued.id
    )
    assert recovered["status"] == "pending"
    assert recovered["locked_at"] is None


@pytest.mark.asyncio
async def test_stale_linked_task_projects_terminal_operation(durable_db):
    tenant = str(uuid4())
    service = _runtime(durable_db, tenant)
    admitted = await service.admit(
        "counter.task_increment",
        "1",
        {"counter_id": str(uuid4())},
        _reference(tenant),
    )
    queued = await enqueue_operation_task(
        admitted.operation.id,
        service=service,
        tenant_id=tenant,
    )
    await service.request_cancellation(
        admitted.operation.id,
        tenant_id=tenant,
        principal=Principal.for_user("user-1", tenant_id=tenant),
        requester_reference=_reference(tenant),
    )
    await durable_db.execute(
        """
        UPDATE aksara_tasks SET status = 'running',
            locked_at = clock_timestamp() - INTERVAL '10 seconds'
        WHERE id = $1
        """,
        queued.id,
    )
    worker = TaskWorker(
        durable_db,
        durable_service=service,
        stale_lock_timeout_seconds=1,
    )

    assert await worker.recover_stale_locks() == 1
    recovered = await durable_db.fetchrow(
        "SELECT status, last_error FROM aksara_tasks WHERE id = $1", queued.id
    )
    assert recovered["status"] == "failed"
    assert recovered["last_error"] == "cancelled"
