"""Independent-process failure and contention campaign for production operations."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
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
from aksara.tasks import enqueue_operation_task

WORKER = Path(__file__).parents[1] / "prototypes" / "v070_production_worker.py"
ACTION = "multiprocess.counter.increment"


@contextmanager
def _tenant(tenant_id: str):
    token = tenant_id_var.set(tenant_id)
    try:
        yield
    finally:
        tenant_id_var.reset(token)


def _reference(tenant_id: str) -> PrincipalReference:
    return PrincipalReference(
        resolver_key="multiprocess",
        resolver_version="1",
        identity_namespace="tests",
        principal_kind="user",
        subject_id="user-1",
        tenant_id=tenant_id,
    )


def _service(
    durable_db,
    *,
    approval_required: bool = False,
    task_backed: bool = False,
):
    async def handler(context, command):
        await context.database.execute(
            """
            UPDATE durable_test_counters
            SET mutation_counter = mutation_counter + $2
            WHERE id = $1
            """,
            UUID(command["counter_id"]),
            int(command["amount"]),
        )
        return {"mutation_counter": int(command["amount"])}

    actions = DurableActionRegistry()
    actions.register(
        DurableAction(
            name=ACTION,
            version="1",
            handler=handler,
            effect_class=EffectClass.POSTGRES_ATOMIC,
            required_scopes=("counter:write",),
            approval_required=approval_required,
            executor_type="task" if task_backed else "inline",
        )
    )
    resolvers = PrincipalResolverRegistry()
    resolvers.register(
        "multiprocess",
        "1",
        lambda reference: PrincipalResolution.resolved(
            Principal.for_user(
                reference.subject_id or "user-1",
                tenant_id=reference.tenant_id,
                scopes=("counter:write",),
            )
        ),
    )
    return DurableOperationService(
        durable_db,
        application_namespace="multiprocess-tests",
        actions=actions,
        resolvers=resolvers,
        default_lease_seconds=0.2,
        retention_seconds=60,
        idempotency_seconds=60,
    )


def _environment(durable_db) -> dict[str, str]:
    environment = os.environ.copy()
    environment["AKSARA_V070_PRODUCTION_DSN"] = durable_db.database_url
    repository_root = str(WORKER.parents[2])
    environment["PYTHONPATH"] = os.pathsep.join(
        value
        for value in (repository_root, environment.get("PYTHONPATH"))
        if value
    )
    return environment


def _decode_events(output: bytes) -> list[dict]:
    return [json.loads(line) for line in output.decode().splitlines() if line.strip()]


async def _run_worker(durable_db, *arguments: str) -> list[dict]:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(WORKER),
        *arguments,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_environment(durable_db),
    )
    output, error = await asyncio.wait_for(process.communicate(), timeout=15)
    assert process.returncode == 0, error.decode()
    return _decode_events(output)


async def _start_paused_worker(durable_db, *arguments: str):
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(WORKER),
        *arguments,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_environment(durable_db),
    )
    assert process.stdout is not None
    claimed = json.loads(
        (await asyncio.wait_for(process.stdout.readline(), timeout=10)).decode()
    )
    boundary = json.loads(
        (await asyncio.wait_for(process.stdout.readline(), timeout=10)).decode()
    )
    return process, claimed, boundary


async def _start_at_boundary(durable_db, *arguments: str):
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(WORKER),
        *arguments,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_environment(durable_db),
    )
    assert process.stdout is not None
    boundary = json.loads(
        (await asyncio.wait_for(process.stdout.readline(), timeout=10)).decode()
    )
    return process, boundary


async def _insert_counter(durable_db, tenant_id: str, counter_id: UUID) -> None:
    with _tenant(tenant_id):
        await durable_db.execute(
            "INSERT INTO durable_test_counters (id, tenant_scope) VALUES ($1, $2)",
            counter_id,
            tenant_id,
        )


async def _counter(durable_db, tenant_id: str, counter_id: UUID) -> int:
    with _tenant(tenant_id):
        return int(
            await durable_db.fetchval(
                "SELECT mutation_counter FROM durable_test_counters WHERE id = $1",
                counter_id,
            )
        )


def _execute_args(
    tenant_id: str,
    operation_id: UUID | str,
    worker_id: str,
    *,
    lease_seconds: float = 1.0,
) -> list[str]:
    return [
        "execute",
        "--tenant-id",
        tenant_id,
        "--operation-id",
        str(operation_id),
        "--worker-id",
        worker_id,
        "--lease-seconds",
        str(lease_seconds),
    ]


@pytest.mark.asyncio
async def test_processes_contend_on_admission_identity_and_claim(durable_db):
    tenant, counter_id = str(uuid4()), uuid4()
    same = await asyncio.gather(
        *(
            _run_worker(
                durable_db,
                "admit",
                "--tenant-id",
                tenant,
                "--counter-id",
                str(counter_id),
                "--amount",
                "1",
                "--idempotency-key",
                "same-request",
            )
            for _ in range(6)
        )
    )
    admissions = [events[-1] for events in same]
    assert {item["operation_id"] for item in admissions} == {
        admissions[0]["operation_id"]
    }
    assert sum(item["created"] for item in admissions) == 1

    conflicting = await asyncio.gather(
        *(
            _run_worker(
                durable_db,
                "admit",
                "--tenant-id",
                tenant,
                "--counter-id",
                str(uuid4()),
                "--amount",
                str(amount),
                "--idempotency-key",
                "conflicting-request",
            )
            for amount in (1, 2)
        )
    )
    conflict_events = [events[-1] for events in conflicting]
    assert sorted(item["event"] for item in conflict_events) == ["admitted", "error"]
    assert next(item for item in conflict_events if item["event"] == "error")[
        "type"
    ] == "IdempotencyConflict"

    operation_id = admissions[0]["operation_id"]
    claims = await asyncio.gather(
        *(
            _run_worker(
                durable_db,
                "claim",
                "--tenant-id",
                tenant,
                "--operation-id",
                operation_id,
                "--worker-id",
                f"worker-{index}",
                "--lease-seconds",
                "5",
            )
            for index in range(6)
        )
    )
    assert sum(events[-1]["claim"] is not None for events in claims) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "boundary",
    [
        "before_mutation",
        "after_mutation",
        "after_attempt_success",
        "after_operation_success",
        "before_commit",
    ],
)
async def test_hard_process_death_rolls_back_every_precommit_boundary(
    durable_db, boundary
):
    tenant, counter_id = str(uuid4()), uuid4()
    service = _service(durable_db)
    await _insert_counter(durable_db, tenant, counter_id)
    admitted = await service.admit(
        ACTION,
        "1",
        {"counter_id": str(counter_id), "amount": 1},
        _reference(tenant),
    )
    process, claimed, paused = await _start_paused_worker(
        durable_db,
        *_execute_args(
            tenant,
            admitted.operation.id,
            "worker-that-dies",
            lease_seconds=0.15,
        ),
        "--pause-at",
        boundary,
    )
    assert claimed["event"] == "claim"
    assert paused == {"event": "boundary", "name": boundary}
    process.kill()
    await process.wait()

    assert await _counter(durable_db, tenant, counter_id) == 0
    await asyncio.sleep(0.2)
    replacement = await _run_worker(
        durable_db,
        *_execute_args(tenant, admitted.operation.id, "replacement"),
    )
    assert replacement[-1]["event"] == "executed"
    assert replacement[-1]["state"] == "succeeded"
    assert await _counter(durable_db, tenant, counter_id) == 1


@pytest.mark.asyncio
async def test_reclaimed_fence_rejects_stale_process_writes(durable_db):
    tenant, counter_id = str(uuid4()), uuid4()
    service = _service(durable_db)
    await _insert_counter(durable_db, tenant, counter_id)
    admitted = await service.admit(
        ACTION,
        "1",
        {"counter_id": str(counter_id), "amount": 1},
        _reference(tenant),
    )
    first = await _run_worker(
        durable_db,
        "claim",
        "--tenant-id",
        tenant,
        "--operation-id",
        str(admitted.operation.id),
        "--worker-id",
        "worker-n",
        "--lease-seconds",
        "0.1",
    )
    old_claim = first[-1]["claim"]
    await asyncio.sleep(0.15)
    second = await _run_worker(
        durable_db,
        "claim",
        "--tenant-id",
        tenant,
        "--operation-id",
        str(admitted.operation.id),
        "--worker-id",
        "worker-n-plus-one",
        "--lease-seconds",
        "1",
    )
    assert second[-1]["claim"]["fence"] == old_claim["fence"] + 1

    stale_results = await asyncio.gather(
        *(
            _run_worker(
                durable_db,
                "stale",
                "--tenant-id",
                tenant,
                "--claim-json",
                json.dumps(old_claim),
                "--mode",
                mode,
            )
            for mode in ("heartbeat", "fail", "execute")
        )
    )
    assert [events[-1]["type"] for events in stale_results] == [
        "OwnershipLost",
        "OwnershipLost",
        "OwnershipLost",
    ]
    assert await _counter(durable_db, tenant, counter_id) == 0


@pytest.mark.asyncio
async def test_process_recovers_authoritative_success_after_lost_ack(durable_db):
    tenant, counter_id = str(uuid4()), uuid4()
    service = _service(durable_db)
    await _insert_counter(durable_db, tenant, counter_id)
    admitted = await service.admit(
        ACTION,
        "1",
        {"counter_id": str(counter_id), "amount": 1},
        _reference(tenant),
        idempotency_key="lost-ack",
    )

    events = await _run_worker(
        durable_db,
        *_execute_args(tenant, admitted.operation.id, "lost-ack-worker"),
        "--lost-ack",
    )

    assert events[-1]["event"] == "executed"
    assert events[-1]["state"] == "succeeded"
    assert await _counter(durable_db, tenant, counter_id) == 1


@pytest.mark.asyncio
async def test_approval_cancellation_and_reauthorization_survive_processes(durable_db):
    tenant = str(uuid4())
    service = _service(durable_db, approval_required=True)

    approved_counter = uuid4()
    await _insert_counter(durable_db, tenant, approved_counter)
    approved = await service.admit(
        ACTION,
        "1",
        {"counter_id": str(approved_counter), "amount": 1},
        _reference(tenant),
    )
    approval = await _run_worker(
        durable_db,
        "approve",
        "--tenant-id",
        tenant,
        "--operation-id",
        str(approved.operation.id),
        "--approval-required",
    )
    assert approval[-1]["state"] == "ready"
    completed = await _run_worker(
        durable_db,
        *_execute_args(tenant, approved.operation.id, "approved-worker"),
        "--approval-required",
    )
    assert completed[-1]["state"] == "succeeded"
    assert await _counter(durable_db, tenant, approved_counter) == 1

    revoked_counter = uuid4()
    await _insert_counter(durable_db, tenant, revoked_counter)
    revoked = await service.admit(
        ACTION,
        "1",
        {"counter_id": str(revoked_counter), "amount": 1},
        _reference(tenant),
    )
    await _run_worker(
        durable_db,
        "approve",
        "--tenant-id",
        tenant,
        "--operation-id",
        str(revoked.operation.id),
        "--approval-required",
    )
    denied = await _run_worker(
        durable_db,
        *_execute_args(tenant, revoked.operation.id, "revoked-worker"),
        "--approval-required",
        "--no-authorized",
    )
    assert denied[-1]["state"] == "failed"
    assert await _counter(durable_db, tenant, revoked_counter) == 0

    cancelled_counter = uuid4()
    await _insert_counter(durable_db, tenant, cancelled_counter)
    cancellable = await service.admit(
        ACTION,
        "1",
        {"counter_id": str(cancelled_counter), "amount": 1},
        _reference(tenant),
    )
    cancelled = await _run_worker(
        durable_db,
        "cancel",
        "--tenant-id",
        tenant,
        "--operation-id",
        str(cancellable.operation.id),
        "--approval-required",
    )
    assert cancelled[-1]["state"] == "cancelled"
    assert await _counter(durable_db, tenant, cancelled_counter) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "boundary",
    [
        "before_task_claim",
        "after_task_claim",
        "before_operation_claim",
        "after_operation_claim",
        "before_mutation",
        "after_mutation",
        "after_operation_commit",
        "before_task_projection",
    ],
)
async def test_task_worker_death_keeps_operation_authoritative(durable_db, boundary):
    tenant, counter_id = str(uuid4()), uuid4()
    service = _service(durable_db, task_backed=True)
    await _insert_counter(durable_db, tenant, counter_id)
    admitted = await service.admit(
        ACTION,
        "1",
        {"counter_id": str(counter_id), "amount": 1},
        _reference(tenant),
    )
    queued = await enqueue_operation_task(
        admitted.operation.id,
        service=service,
        tenant_id=tenant,
    )
    process, paused = await _start_at_boundary(
        durable_db,
        "task",
        "--tenant-id",
        tenant,
        "--worker-id",
        "task-worker-that-dies",
        "--stale-seconds",
        "0.15",
        "--pause-at",
        boundary,
    )
    assert paused == {"event": "boundary", "name": boundary}
    process.kill()
    await process.wait()

    await asyncio.sleep(0.2)
    replacement = await _run_worker(
        durable_db,
        "task",
        "--tenant-id",
        tenant,
        "--worker-id",
        "replacement-task-worker",
        "--stale-seconds",
        "0.15",
        "--recover",
    )
    assert replacement[-1]["event"] == "task"
    operation = await service.get(
        admitted.operation.id,
        tenant_id=tenant,
        principal=Principal.for_user(
            "user-1", tenant_id=tenant, scopes=("counter:write",)
        ),
    )
    assert operation.state is OperationState.SUCCEEDED
    assert await _counter(durable_db, tenant, counter_id) == 1
    projected = await durable_db.fetchrow(
        "SELECT status, result FROM aksara_tasks WHERE id = $1", queued.id
    )
    assert projected["status"] == "completed"
