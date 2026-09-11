"""Existing tasks remain compatible and may execute linked Operations."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest

import aksara.tasks as tasks_module
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


def _runtime(durable_db, tenant: str, *, namespace: str = "task-tests"):
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
        application_namespace=namespace,
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
    assert queued.operation_application_namespace == service.application_namespace

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
        principal=Principal.for_user(
            "user-1", tenant_id=tenant, scopes=("counter:write",)
        ),
    )
    assert operation.state is OperationState.SUCCEEDED
    assert operation.attempt_count == 1
    with _tenant(tenant):
        assert await durable_db.fetchval(
            "SELECT mutation_counter FROM durable_test_counters WHERE id = $1",
            counter_id,
        ) == 1


@pytest.mark.asyncio
async def test_task_backed_external_operation_renews_its_operation_lease(
    durable_db,
    monkeypatch,
):
    tenant = str(uuid4())
    heartbeat_seen = asyncio.Event()

    async def handler(_context, _command):
        await asyncio.wait_for(heartbeat_seen.wait(), timeout=1)
        return {"renewed": True}

    service = _runtime(durable_db, tenant)
    service.actions.register(
        DurableAction(
            name="external.task_wait",
            version="1",
            handler=handler,
            effect_class=EffectClass.EXTERNAL_IDEMPOTENT,
            executor_type="task",
            required_scopes=("counter:write",),
        )
    )
    admitted = await service.admit(
        "external.task_wait", "1", {"value": 1}, _reference(tenant)
    )
    await enqueue_operation_task(
        admitted.operation.id,
        service=service,
        tenant_id=tenant,
    )
    original_heartbeat = service.heartbeat

    async def observe_heartbeat(claim, *, lease_seconds=None):
        operation = await original_heartbeat(claim, lease_seconds=lease_seconds)
        heartbeat_seen.set()
        return operation

    monkeypatch.setattr(service, "heartbeat", observe_heartbeat)
    worker = TaskWorker(
        durable_db,
        durable_service=service,
        worker_id="external-task-worker",
        stale_lock_timeout_seconds=0.03,
    )

    completed_task = await asyncio.wait_for(worker.poll_once(), timeout=1)

    assert heartbeat_seen.is_set()
    assert completed_task is not None
    assert completed_task.status == "completed"
    assert completed_task.result == {"renewed": True}


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
async def test_worker_without_durable_service_leaves_linked_task_pending(durable_db):
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

    assert await TaskWorker(durable_db).poll_once() is None
    retained = await durable_db.fetchrow(
        "SELECT status, attempts, locked_at FROM aksara_tasks WHERE id = $1",
        queued.id,
    )
    assert retained["status"] == "pending"
    assert retained["attempts"] == 0
    assert retained["locked_at"] is None


@pytest.mark.asyncio
async def test_worker_leaves_another_application_namespace_task_pending(durable_db):
    tenant, counter_id = str(uuid4()), uuid4()
    owner = _runtime(durable_db, tenant, namespace="application-b")
    other = _runtime(durable_db, tenant, namespace="application-a")
    with _tenant(tenant):
        await durable_db.execute(
            "INSERT INTO durable_test_counters (id, tenant_scope) VALUES ($1, $2)",
            counter_id,
            tenant,
        )
    admitted = await owner.admit(
        "counter.task_increment",
        "1",
        {"counter_id": str(counter_id)},
        _reference(tenant),
    )
    queued = await enqueue_operation_task(
        admitted.operation.id,
        service=owner,
        tenant_id=tenant,
    )

    assert await TaskWorker(durable_db, durable_service=other).poll_once() is None
    retained = await durable_db.fetchrow(
        "SELECT status, attempts, locked_at FROM aksara_tasks WHERE id = $1",
        queued.id,
    )
    assert retained["status"] == "pending"
    assert retained["attempts"] == 0
    assert retained["locked_at"] is None

    completed = await TaskWorker(durable_db, durable_service=owner).poll_once()
    assert completed is not None
    assert completed.id == queued.id
    assert completed.status == "completed"


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
async def test_stale_linked_task_recovery_processes_bounded_batches(
    durable_db, monkeypatch
):
    tenant = str(uuid4())
    service = _runtime(durable_db, tenant)
    task_ids = []
    for _ in range(3):
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
        task_ids.append(queued.id)
    await durable_db.execute(
        """
        UPDATE aksara_tasks SET status = 'running',
            locked_at = clock_timestamp() - INTERVAL '10 seconds'
        WHERE id = ANY($1::uuid[])
        """,
        task_ids,
    )
    monkeypatch.setattr(tasks_module, "_STALE_OPERATION_RECOVERY_BATCH_SIZE", 2)
    worker = TaskWorker(
        durable_db,
        durable_service=service,
        stale_lock_timeout_seconds=1,
    )

    assert await worker.recover_stale_locks() == 3
    rows = await durable_db.fetch(
        "SELECT status, locked_at FROM aksara_tasks WHERE id = ANY($1::uuid[])",
        task_ids,
    )
    assert len(rows) == 3
    assert all(row["status"] == "pending" for row in rows)
    assert all(row["locked_at"] is None for row in rows)


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
        principal=Principal.for_user(
            "user-1", tenant_id=tenant, scopes=("counter:write",)
        ),
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


@pytest.mark.asyncio
async def test_prune_preserves_terminal_operation_until_task_projection(durable_db):
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
        principal=Principal.for_user(
            "user-1", tenant_id=tenant, scopes=("counter:write",)
        ),
        requester_reference=_reference(tenant),
    )
    with _tenant(tenant):
        await durable_db.execute(
            """
            UPDATE aksara_operations
            SET retain_until = clock_timestamp() - INTERVAL '1 second'
            WHERE id = $1
            """,
            admitted.operation.id,
        )
        await durable_db.execute(
            """
            UPDATE aksara_operation_outbox
            SET exported_at = clock_timestamp()
            WHERE operation_id = $1
            """,
            admitted.operation.id,
        )

    first = await service.prune(tenant_id=tenant)
    assert first["operations"] == 0

    completed = await TaskWorker(
        durable_db, durable_service=service, worker_id="projection-worker"
    ).poll_once()
    assert completed is not None
    assert completed.status == "failed"

    second = await service.prune(tenant_id=tenant)
    assert second["operations"] == 1
    retained_task = await durable_db.fetchrow(
        "SELECT status, operation_id FROM aksara_tasks WHERE id = $1", queued.id
    )
    assert retained_task["status"] == "failed"
    assert retained_task["operation_id"] is None


@pytest.mark.asyncio
async def test_stale_task_projection_cannot_overwrite_new_task_claim(durable_db):
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
    worker = TaskWorker(durable_db, durable_service=service)
    stale_claim = await worker._claim_task()
    assert stale_claim is not None
    await durable_db.execute(
        """
        UPDATE aksara_tasks
        SET status = 'pending', locked_at = NULL, available_at = clock_timestamp()
        WHERE id = $1
        """,
        queued.id,
    )
    current_claim = await worker._claim_task()
    assert current_claim is not None
    assert current_claim.id == queued.id
    assert current_claim.attempts == stale_claim.attempts + 1

    await worker._project_operation_task(stale_claim, admitted.operation)

    retained = await durable_db.fetchrow(
        "SELECT status, attempts, locked_at FROM aksara_tasks WHERE id = $1",
        queued.id,
    )
    assert retained["status"] == "running"
    assert retained["attempts"] == current_claim.attempts
    assert retained["locked_at"] == current_claim.locked_at
