"""Independent-process driver for production durable-operation invariants."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime
from typing import Any
from uuid import UUID

from aksara.db import Database
from aksara.db.transaction import TransactionManager
from aksara.durable import (
    DurableAction,
    DurableActionRegistry,
    DurableOperationService,
    EffectClass,
    PostgresAtomicExecutor,
    PrincipalReference,
    PrincipalResolution,
    PrincipalResolverRegistry,
)
from aksara.durable.types import OperationClaim
from aksara.security.principal import Principal
from aksara.tasks import TaskWorker

ACTION = "multiprocess.counter.increment"
ACTION_VERSION = "1"
APPLICATION_NAMESPACE = "multiprocess-tests"


def _emit(event: str, **values: Any) -> None:
    print(json.dumps({"event": event, **values}, default=str, sort_keys=True), flush=True)


def _reference(tenant_id: str, *, subject_id: str = "user-1") -> PrincipalReference:
    return PrincipalReference(
        resolver_key="multiprocess",
        resolver_version="1",
        identity_namespace="tests",
        principal_kind="user",
        subject_id=subject_id,
        tenant_id=tenant_id,
    )


def _runtime(
    database: Database,
    *,
    approval_required: bool,
    authorized: bool,
    task_backed: bool = False,
) -> DurableOperationService:
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
            version=ACTION_VERSION,
            handler=handler,
            effect_class=EffectClass.POSTGRES_ATOMIC,
            required_scopes=("counter:write",),
            approval_required=approval_required,
            executor_type="task" if task_backed else "inline",
        )
    )
    resolvers = PrincipalResolverRegistry()

    def resolve(reference: PrincipalReference) -> PrincipalResolution:
        return PrincipalResolution.resolved(
            Principal.for_user(
                reference.subject_id or "user-1",
                tenant_id=reference.tenant_id,
                scopes=("counter:write",) if authorized else (),
            )
        )

    resolvers.register("multiprocess", "1", resolve)
    return DurableOperationService(
        database,
        application_namespace=APPLICATION_NAMESPACE,
        actions=actions,
        resolvers=resolvers,
        default_lease_seconds=0.2,
        retention_seconds=60,
        idempotency_seconds=60,
    )


def _claim_dict(claim: OperationClaim) -> dict[str, Any]:
    return {
        "operation_id": str(claim.operation_id),
        "attempt_id": str(claim.attempt_id),
        "tenant_id": claim.tenant_id,
        "tenant_scope": claim.tenant_scope,
        "action_name": claim.action_name,
        "action_version": claim.action_version,
        "effect_class": claim.effect_class.value,
        "worker_id": claim.worker_id,
        "fence": claim.fence,
        "ordinal": claim.ordinal,
        "lease_expires_at": claim.lease_expires_at.isoformat(),
        "command": dict(claim.command),
        "principal_reference": claim.principal_reference.to_dict(),
    }


def _restore_claim(value: str) -> OperationClaim:
    payload = json.loads(value)
    return OperationClaim(
        operation_id=UUID(payload["operation_id"]),
        attempt_id=UUID(payload["attempt_id"]),
        tenant_id=payload["tenant_id"],
        tenant_scope=payload["tenant_scope"],
        action_name=payload["action_name"],
        action_version=payload["action_version"],
        effect_class=EffectClass(payload["effect_class"]),
        worker_id=payload["worker_id"],
        fence=int(payload["fence"]),
        ordinal=int(payload["ordinal"]),
        lease_expires_at=datetime.fromisoformat(payload["lease_expires_at"]),
        command=dict(payload["command"]),
        principal_reference=PrincipalReference(**payload["principal_reference"]),
    )


async def _run(args: argparse.Namespace) -> int:
    database = Database(os.environ["AKSARA_V070_PRODUCTION_DSN"], min_size=1, max_size=2)
    await database.connect()
    service = _runtime(
        database,
        approval_required=args.approval_required,
        authorized=args.authorized,
        task_backed=args.action == "task",
    )
    try:
        if args.action == "admit":
            admitted = await service.admit(
                ACTION,
                ACTION_VERSION,
                {"counter_id": args.counter_id, "amount": args.amount},
                _reference(args.tenant_id),
                idempotency_key=args.idempotency_key,
            )
            _emit(
                "admitted",
                operation_id=str(admitted.operation.id),
                created=admitted.created,
                state=admitted.operation.state.value,
            )
            return 0

        if args.action == "approve":
            operation = await service.decide_approval(
                UUID(args.operation_id),
                tenant_id=args.tenant_id,
                approver=Principal.for_user("approver-1", tenant_id=args.tenant_id),
                approver_reference=_reference(args.tenant_id, subject_id="approver-1"),
                approve=True,
            )
            _emit("approved", state=operation.state.value)
            return 0

        if args.action == "cancel":
            operation = await service.request_cancellation(
                UUID(args.operation_id),
                tenant_id=args.tenant_id,
                principal=Principal.for_user("user-1", tenant_id=args.tenant_id),
                requester_reference=_reference(args.tenant_id),
            )
            _emit("cancelled", state=operation.state.value)
            return 0

        if args.action == "stale":
            claim = _restore_claim(args.claim_json)
            if args.mode == "heartbeat":
                await service.heartbeat(claim)
                _emit("stale-heartbeat-unexpectedly-succeeded")
            elif args.mode == "fail":
                await service.fail_attempt(
                    claim,
                    code="stale_failure",
                    message="stale failure",
                    retryable=False,
                )
                _emit("stale-failure-unexpectedly-succeeded")
            else:
                await PostgresAtomicExecutor(service).execute(claim)
                _emit("stale-execute-unexpectedly-succeeded")
            return 0

        if args.action == "task":
            async def task_boundary(name: str) -> None:
                if name == args.pause_at:
                    _emit("boundary", name=name)
                    await asyncio.sleep(3600)

            worker = TaskWorker(
                database,
                durable_service=service,
                worker_id=args.worker_id,
                stale_lock_timeout_seconds=args.stale_seconds,
                poll_interval=0,
                _boundary_hook=task_boundary if args.pause_at else None,
            )
            recovered = await worker.recover_stale_locks() if args.recover else 0
            task_record = await worker.poll_once()
            _emit(
                "task",
                recovered=recovered,
                task_id=str(task_record.id) if task_record else None,
                status=task_record.status if task_record else None,
            )
            return 0

        claim = await service.claim(
            tenant_id=args.tenant_id,
            worker_id=args.worker_id,
            operation_id=UUID(args.operation_id),
            lease_seconds=args.lease_seconds,
        )
        if claim is None:
            _emit("claim", claim=None)
            return 0
        _emit("claim", claim=_claim_dict(claim))
        if args.action == "claim":
            if args.hold_seconds:
                await asyncio.sleep(args.hold_seconds)
            return 0

        if args.lost_ack:
            original_exit = TransactionManager.__aexit__
            injected = False

            async def lose_ack(manager, exc_type, exc_val, exc_tb):
                nonlocal injected
                await original_exit(manager, exc_type, exc_val, exc_tb)
                if exc_type is None and not injected:
                    injected = True
                    raise ConnectionError("simulated lost commit acknowledgement")

            TransactionManager.__aexit__ = lose_ack

        async def boundary_hook(name: str) -> None:
            if name == args.pause_at:
                _emit("boundary", name=name)
                await asyncio.sleep(3600)

        executor = PostgresAtomicExecutor(
            service,
            _boundary_hook=boundary_hook if args.pause_at else None,
        )
        operation = await executor.execute(claim)
        _emit("executed", state=operation.state.value, result=operation.result)
        return 0
    except Exception as exc:  # noqa: BLE001 - subprocess protocol reports all failures
        _emit("error", type=type(exc).__name__, message=str(exc))
        return 0
    finally:
        await database.disconnect()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--tenant-id", required=True)
    common.add_argument("--approval-required", action="store_true")
    common.add_argument("--authorized", action=argparse.BooleanOptionalAction, default=True)
    actions = parser.add_subparsers(dest="action", required=True)

    admit = actions.add_parser("admit", parents=[common])
    admit.add_argument("--counter-id", required=True)
    admit.add_argument("--amount", type=int, required=True)
    admit.add_argument("--idempotency-key", required=True)

    approve = actions.add_parser("approve", parents=[common])
    approve.add_argument("--operation-id", required=True)

    cancel = actions.add_parser("cancel", parents=[common])
    cancel.add_argument("--operation-id", required=True)

    claim = actions.add_parser("claim", parents=[common])
    claim.add_argument("--operation-id", required=True)
    claim.add_argument("--worker-id", required=True)
    claim.add_argument("--lease-seconds", type=float, default=1.0)
    claim.add_argument("--hold-seconds", type=float, default=0.0)

    execute = actions.add_parser("execute", parents=[common])
    execute.add_argument("--operation-id", required=True)
    execute.add_argument("--worker-id", required=True)
    execute.add_argument("--lease-seconds", type=float, default=1.0)
    execute.add_argument(
        "--pause-at",
        choices=(
            "before_lock",
            "after_lock",
            "before_mutation",
            "after_mutation",
            "after_attempt_success",
            "after_operation_success",
            "before_commit",
        ),
    )
    execute.add_argument("--lost-ack", action="store_true")

    stale = actions.add_parser("stale", parents=[common])
    stale.add_argument("--claim-json", required=True)
    stale.add_argument("--mode", choices=("heartbeat", "fail", "execute"), required=True)

    task = actions.add_parser("task", parents=[common])
    task.add_argument("--worker-id", required=True)
    task.add_argument("--stale-seconds", type=float, default=0.15)
    task.add_argument("--recover", action="store_true")
    task.add_argument(
        "--pause-at",
        choices=(
            "before_task_claim",
            "after_task_claim",
            "before_operation_claim",
            "after_operation_claim",
            "before_mutation",
            "after_mutation",
            "after_operation_commit",
            "before_task_projection",
        ),
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run(_parser().parse_args())))
