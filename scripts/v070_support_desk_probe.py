"""Exercise v0.7 durable operations from an isolated installed wheel."""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import contextmanager
from uuid import UUID, uuid4

from aksara.context_state import tenant_id_var
from aksara.db import Database
from aksara.durable import (
    DurableAction,
    DurableActionRegistry,
    DurableOperationService,
    DurableOutboxExporter,
    EffectClass,
    IdempotencyConflict,
    OperationNotFound,
    OperationState,
    PostgresAtomicExecutor,
    PrincipalReference,
    PrincipalResolution,
    PrincipalResolverRegistry,
    check_durable_operations,
)
from aksara.durable.errors import OwnershipLost
from aksara.security.principal import Principal
from aksara.tasks import TaskWorker, enqueue_operation_task


@contextmanager
def _tenant(tenant_id: str):
    token = tenant_id_var.set(tenant_id)
    try:
        yield
    finally:
        tenant_id_var.reset(token)


def _reference(tenant_id: str, subject_id: str = "support-user-a") -> PrincipalReference:
    return PrincipalReference(
        resolver_key="support-desk-current-identity",
        resolver_version="1",
        identity_namespace="support-desk",
        principal_kind="user",
        subject_id=subject_id,
        tenant_id=tenant_id,
    )


def _principal(tenant_id: str, subject_id: str = "support-user-a") -> Principal:
    return Principal.for_user(
        subject_id,
        tenant_id=tenant_id,
        roles=("agent",),
        scopes=("ticket:resolve",),
    )


async def _insert_ticket(database: Database, tenant_id: str, subject: str) -> UUID:
    ticket_id = uuid4()
    with _tenant(tenant_id):
        await database.execute(
            """
            INSERT INTO support_tickets (
                id, tenant_id, subject, description, status, priority,
                created_at, updated_at
            ) VALUES (
                $1, $2::uuid, $3, 'v0.7 installed-wheel probe', 'open', 'normal',
                clock_timestamp(), clock_timestamp()
            )
            """,
            ticket_id,
            tenant_id,
            subject,
        )
    return ticket_id


async def _ticket_status(database: Database, tenant_id: str, ticket_id: UUID) -> str:
    with _tenant(tenant_id):
        return str(
            await database.fetchval(
                "SELECT status FROM support_tickets WHERE id = $1", ticket_id
            )
        )


async def main() -> None:
    dsn, tenant_a, tenant_b = sys.argv[1:4]
    database = Database(dsn, min_size=1, max_size=4)
    await database.connect()
    checks: dict[str, bool] = {}
    authorization = {"enabled": True}

    async def resolve_ticket(context, command):
        await context.database.execute(
            """
            UPDATE support_tickets
            SET status = 'resolved', updated_at = clock_timestamp()
            WHERE id = $1 AND tenant_id = $2::uuid
            """,
            UUID(command["ticket_id"]),
            context.tenant_id,
        )
        return {"ticket_id": command["ticket_id"], "status": "resolved"}

    actions = DurableActionRegistry()
    for name, approval_required, executor_type in (
        ("support.ticket.resolve", False, "inline"),
        ("support.ticket.resolve-approved", True, "inline"),
        ("support.ticket.resolve-task", False, "task"),
    ):
        actions.register(
            DurableAction(
                name=name,
                version="1",
                handler=resolve_ticket,
                effect_class=EffectClass.POSTGRES_ATOMIC,
                required_scopes=("ticket:resolve",),
                approval_required=approval_required,
                executor_type=executor_type,
            )
        )
    resolvers = PrincipalResolverRegistry()

    def current_identity(reference: PrincipalReference) -> PrincipalResolution:
        scopes = ("ticket:resolve",) if authorization["enabled"] else ()
        return PrincipalResolution.resolved(
            Principal.for_user(
                reference.subject_id or "support-user-a",
                tenant_id=reference.tenant_id,
                roles=("agent",),
                scopes=scopes,
            )
        )

    resolvers.register("support-desk-current-identity", "1", current_identity)
    service = DurableOperationService(
        database,
        application_namespace="support-desk-v070",
        actions=actions,
        resolvers=resolvers,
        default_lease_seconds=0.05,
        retention_seconds=60,
        idempotency_seconds=60,
    )

    try:
        ticket = await _insert_ticket(database, tenant_a, "Durable status and recovery")
        admitted = await service.admit(
            "support.ticket.resolve",
            "1",
            {"ticket_id": str(ticket)},
            _reference(tenant_a),
            idempotency_key="installed-wheel-request",
        )
        checks["register_and_dispatch"] = (
            admitted.created and admitted.operation.state is OperationState.READY
        )
        queried = await service.get(
            admitted.operation.id,
            tenant_id=tenant_a,
            principal=_principal(tenant_a),
        )
        checks["status_query"] = queried.id == admitted.operation.id
        try:
            await service.get(
                admitted.operation.id,
                tenant_id=tenant_b,
                principal=_principal(tenant_b, "support-user-b"),
            )
        except OperationNotFound:
            checks["tenant_isolation"] = True
        else:
            checks["tenant_isolation"] = False

        claim = await service.claim(
            tenant_id=tenant_a,
            worker_id="installed-worker-a",
            operation_id=admitted.operation.id,
        )
        assert claim is not None
        await PostgresAtomicExecutor(service).execute(claim)
        recovered = await service.get(
            admitted.operation.id,
            tenant_id=tenant_a,
            principal=_principal(tenant_a),
        )
        checks["atomic_mutation_and_lost_response_recovery"] = (
            recovered.state is OperationState.SUCCEEDED
            and await _ticket_status(database, tenant_a, ticket) == "resolved"
        )
        duplicate = await service.admit(
            "support.ticket.resolve",
            "1",
            {"ticket_id": str(ticket)},
            _reference(tenant_a),
            idempotency_key="installed-wheel-request",
        )
        checks["duplicate_returns_same_operation"] = (
            not duplicate.created and duplicate.operation.id == admitted.operation.id
        )
        try:
            await service.admit(
                "support.ticket.resolve",
                "1",
                {"ticket_id": str(uuid4())},
                _reference(tenant_a),
                idempotency_key="installed-wheel-request",
            )
        except IdempotencyConflict:
            checks["conflicting_submission_rejected"] = True
        else:
            checks["conflicting_submission_rejected"] = False

        reclaim_ticket = await _insert_ticket(database, tenant_a, "Worker reclaim")
        reclaim_admission = await service.admit(
            "support.ticket.resolve",
            "1",
            {"ticket_id": str(reclaim_ticket)},
            _reference(tenant_a),
        )
        stale = await service.claim(
            tenant_id=tenant_a,
            worker_id="installed-worker-stale",
            operation_id=reclaim_admission.operation.id,
            lease_seconds=0.03,
        )
        assert stale is not None
        await asyncio.sleep(0.05)
        replacement = await service.claim(
            tenant_id=tenant_a,
            worker_id="installed-worker-replacement",
            operation_id=reclaim_admission.operation.id,
        )
        assert replacement is not None
        try:
            await PostgresAtomicExecutor(service).execute(stale)
        except OwnershipLost:
            stale_fenced = True
        else:
            stale_fenced = False
        replacement_result = await PostgresAtomicExecutor(service).execute(replacement)
        checks["worker_reclaim_and_stale_fence"] = (
            stale_fenced
            and replacement.fence == stale.fence + 1
            and replacement_result.state is OperationState.SUCCEEDED
        )

        cancel_ticket = await _insert_ticket(database, tenant_a, "Cancellation")
        cancellable = await service.admit(
            "support.ticket.resolve",
            "1",
            {"ticket_id": str(cancel_ticket)},
            _reference(tenant_a),
        )
        cancelled = await service.request_cancellation(
            cancellable.operation.id,
            tenant_id=tenant_a,
            principal=_principal(tenant_a),
            requester_reference=_reference(tenant_a),
        )
        checks["cancellation"] = (
            cancelled.state is OperationState.CANCELLED
            and await _ticket_status(database, tenant_a, cancel_ticket) == "open"
        )

        approved_ticket = await _insert_ticket(database, tenant_a, "Approval")
        waiting = await service.admit(
            "support.ticket.resolve-approved",
            "1",
            {"ticket_id": str(approved_ticket)},
            _reference(tenant_a),
        )
        approved = await service.decide_approval(
            waiting.operation.id,
            tenant_id=tenant_a,
            approver=_principal(tenant_a, "support-approver"),
            approver_reference=_reference(tenant_a, "support-approver"),
            approve=True,
        )
        approved_claim = await service.claim(
            tenant_id=tenant_a,
            worker_id="installed-approved-worker",
            operation_id=waiting.operation.id,
        )
        assert approved_claim is not None
        approved_result = await PostgresAtomicExecutor(service).execute(approved_claim)
        checks["approval_required_action"] = (
            approved.state is OperationState.READY
            and approved_result.state is OperationState.SUCCEEDED
        )

        revoked_ticket = await _insert_ticket(database, tenant_a, "Revoked after approval")
        revoked_waiting = await service.admit(
            "support.ticket.resolve-approved",
            "1",
            {"ticket_id": str(revoked_ticket)},
            _reference(tenant_a),
        )
        await service.decide_approval(
            revoked_waiting.operation.id,
            tenant_id=tenant_a,
            approver=_principal(tenant_a, "support-approver"),
            approver_reference=_reference(tenant_a, "support-approver"),
            approve=True,
        )
        revoked_claim = await service.claim(
            tenant_id=tenant_a,
            worker_id="installed-revoked-worker",
            operation_id=revoked_waiting.operation.id,
        )
        assert revoked_claim is not None
        authorization["enabled"] = False
        revoked_result = await PostgresAtomicExecutor(service).execute(revoked_claim)
        authorization["enabled"] = True
        checks["authorization_revoked_while_waiting"] = (
            revoked_result.state is OperationState.FAILED
            and revoked_result.error["code"] == "authorization_denied"
            and await _ticket_status(database, tenant_a, revoked_ticket) == "open"
        )

        task_ticket = await _insert_ticket(database, tenant_a, "Task-backed operation")
        task_admission = await service.admit(
            "support.ticket.resolve-task",
            "1",
            {"ticket_id": str(task_ticket)},
            _reference(tenant_a),
        )
        task = await enqueue_operation_task(
            task_admission.operation.id,
            service=service,
            tenant_id=tenant_a,
            queue="v070-installed",
        )
        task_worker = TaskWorker(
            database,
            durable_service=service,
            worker_id="installed-task-worker",
            queues=["v070-installed"],
            poll_interval=0,
        )
        projected = await task_worker.poll_once()
        task_result = await service.get(
            task_admission.operation.id,
            tenant_id=tenant_a,
            principal=_principal(tenant_a),
        )
        checks["task_backed_operation"] = (
            projected is not None
            and projected.id == task.id
            and projected.status == "completed"
            and task_result.state is OperationState.SUCCEEDED
        )

        exported: list[dict] = []
        exporter = DurableOutboxExporter(service, exported.append, retry_seconds=0)
        while await exporter.export_once(tenant_id=tenant_a):
            pass
        checks["transition_outbox_export"] = bool(exported) and all(
            "operation_id" in event and "event" in event for event in exported
        )

        diagnostic = await check_durable_operations(service, tenant_id=tenant_a)
        checks["durable_diagnostics"] = diagnostic.release_ready

        prune_ticket = await _insert_ticket(database, tenant_a, "Retention")
        prune_service = DurableOperationService(
            database,
            application_namespace="support-desk-v070-prune",
            actions=actions,
            resolvers=resolvers,
            retention_seconds=0.05,
            idempotency_seconds=0.1,
            result_retention_seconds=0.02,
            error_retention_seconds=0.02,
        )
        prune_admission = await prune_service.admit(
            "support.ticket.resolve",
            "1",
            {"ticket_id": str(prune_ticket)},
            _reference(tenant_a),
            idempotency_key="prune-window",
        )
        prune_claim = await prune_service.claim(
            tenant_id=tenant_a,
            worker_id="installed-prune-worker",
            operation_id=prune_admission.operation.id,
        )
        assert prune_claim is not None
        await PostgresAtomicExecutor(prune_service).execute(prune_claim)
        prune_exporter = DurableOutboxExporter(
            prune_service, lambda _event: None, retry_seconds=0
        )
        while await prune_exporter.export_once(tenant_id=tenant_a):
            pass
        await asyncio.sleep(0.03)
        first_prune = await prune_service.prune(tenant_id=tenant_a, batch_size=20)
        retained = await prune_service.get(
            prune_admission.operation.id,
            tenant_id=tenant_a,
            principal=_principal(tenant_a),
        )
        await asyncio.sleep(0.08)
        second_prune = await prune_service.prune(tenant_id=tenant_a, batch_size=20)
        try:
            await prune_service.get(
                prune_admission.operation.id,
                tenant_id=tenant_a,
                principal=_principal(tenant_a),
            )
        except OperationNotFound:
            removed = True
        else:
            removed = False
        checks["pruning_and_tombstone"] = (
            first_prune["results"] == 1
            and retained.result is None
            and second_prune["idempotency"] == 1
            and second_prune["operations"] == 1
            and removed
        )
    finally:
        await database.disconnect()

    try:
        database.pool
    except RuntimeError:
        checks["clean_pool_shutdown"] = True
    else:
        checks["clean_pool_shutdown"] = False
    print(json.dumps({"checks": checks, "passed": all(checks.values())}, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
