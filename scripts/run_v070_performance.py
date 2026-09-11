"""Run the v0.7 durable-operation PostgreSQL pathology and contention gate."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import secrets
import statistics
import sys
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import asyncpg

import aksara
from aksara.context_state import tenant_id_var
from aksara.db import Database
from aksara.durable import (
    DurableAction,
    DurableActionRegistry,
    DurableOperationService,
    DurableOutboxExporter,
    EffectClass,
    PostgresAtomicExecutor,
    PrincipalReference,
    PrincipalResolution,
    PrincipalResolverRegistry,
)
from aksara.migrations.executor import (
    discover_internal_migrations,
    load_migration_module,
)
from aksara.security.principal import Principal
from aksara.tasks import TaskWorker, enqueue_operation_task


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "audit-evidence" / "v070" / "performance-sanity.json",
    )
    parser.add_argument("--operations", type=int, default=256)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--noise-rows", type=int, default=3000)
    return parser


def _role_dsn(database_url: str, role: str, password: str) -> str:
    parsed = urlsplit(database_url)
    host = parsed.hostname or "localhost"
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parsed.port}" if parsed.port else ""
    return urlunsplit(
        (
            parsed.scheme,
            f"{quote(role)}:{quote(password)}@{host}{port}",
            parsed.path,
            parsed.query,
            parsed.fragment,
        )
    )


@contextmanager
def _tenant(tenant_id: str):
    token = tenant_id_var.set(tenant_id)
    try:
        yield
    finally:
        tenant_id_var.reset(token)


def _reference(tenant_id: str) -> PrincipalReference:
    return PrincipalReference(
        resolver_key="v070-performance",
        resolver_version="1",
        identity_namespace="v070-performance",
        principal_kind="service",
        subject_id="performance-worker",
        tenant_id=tenant_id,
    )


def _summary(samples: list[float]) -> dict[str, float | int]:
    ordered = sorted(samples)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    return {
        "samples": len(samples),
        "min_ms": round(ordered[0], 3),
        "median_ms": round(statistics.median(ordered), 3),
        "p95_ms": round(p95, 3),
        "max_ms": round(ordered[-1], 3),
    }


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000


async def _apply_internal_migrations(connection: asyncpg.Connection) -> None:
    for _, path in discover_internal_migrations():
        migration = load_migration_module(Path(path))()
        for operation in migration.operations:
            await operation.apply(connection)


async def _run(args: argparse.Namespace) -> dict[str, object]:
    if not args.database_url:
        raise ValueError("--database-url or DATABASE_URL is required")
    if args.operations < 32 or args.concurrency < 2 or args.noise_rows < 1000:
        raise ValueError("use at least 32 operations, 2 workers, and 1000 noise rows")

    suffix = uuid4().hex[:10]
    schema = f"aksara_v070_perf_{suffix}"
    role = f"aksara_v070_perf_role_{suffix}"
    password = secrets.token_urlsafe(24)
    tenant = str(uuid4())
    namespace = f"v070-performance-{suffix}"
    admin = await asyncpg.connect(args.database_url)
    database: Database | None = None
    prior_database = Database._instance
    started_at = datetime.now(UTC)
    try:
        escaped_password = password.replace("'", "''")
        await admin.execute(f'CREATE SCHEMA "{schema}"')
        await admin.execute(
            f'''CREATE ROLE "{role}" LOGIN PASSWORD '{escaped_password}' '''
            "NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION"
        )
        await admin.execute(f'ALTER ROLE "{role}" SET search_path TO "{schema}", public')
        await admin.execute(f'SET search_path TO "{schema}", public')
        await _apply_internal_migrations(admin)
        await admin.execute(
            """
            CREATE TABLE v070_performance_counters (
                id UUID PRIMARY KEY,
                tenant_scope TEXT NOT NULL,
                mutation_counter INTEGER NOT NULL DEFAULT 0
            );
            ALTER TABLE v070_performance_counters ENABLE ROW LEVEL SECURITY;
            ALTER TABLE v070_performance_counters FORCE ROW LEVEL SECURITY;
            CREATE POLICY v070_performance_counters_tenant
            ON v070_performance_counters
            USING (tenant_scope = current_setting('aksara.current_tenant_id', true))
            WITH CHECK (tenant_scope = current_setting('aksara.current_tenant_id', true));
            """
        )
        await admin.execute(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"')
        await admin.execute(
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"'
        )
        await admin.execute(
            f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA "{schema}" TO "{role}"'
        )

        database = Database(
            _role_dsn(args.database_url, role, password),
            min_size=1,
            max_size=max(args.concurrency + 2, 4),
        )
        await database.connect()

        async def increment(context, command):
            await context.database.execute(
                """
                UPDATE v070_performance_counters
                SET mutation_counter = mutation_counter + 1
                WHERE id = $1
                """,
                UUID(command["counter_id"]),
            )
            return {"counter_id": command["counter_id"], "value": 1}

        actions = DurableActionRegistry()
        actions.register(
            DurableAction(
                name="performance.increment",
                version="1",
                handler=increment,
                effect_class=EffectClass.POSTGRES_ATOMIC,
                required_scopes=("counter:write",),
            )
        )
        actions.register(
            DurableAction(
                name="performance.task_increment",
                version="1",
                handler=increment,
                effect_class=EffectClass.POSTGRES_ATOMIC,
                required_scopes=("counter:write",),
                executor_type="task",
            )
        )
        resolvers = PrincipalResolverRegistry()
        resolvers.register(
            "v070-performance",
            "1",
            lambda _reference: PrincipalResolution.resolved(
                Principal.for_user(
                    "performance-worker",
                    tenant_id=tenant,
                    scopes=("counter:write",),
                )
            ),
        )
        service = DurableOperationService(
            database,
            application_namespace=namespace,
            actions=actions,
            resolvers=resolvers,
            retention_seconds=300,
            idempotency_seconds=300,
        )
        reference = _reference(tenant)
        principal = Principal.for_user(
            "performance-worker",
            tenant_id=tenant,
            scopes=("counter:write",),
        )

        with _tenant(tenant):
            await database.execute(
                """
                INSERT INTO aksara_operations (
                    id, application_namespace, tenant_id, tenant_scope,
                    action_name, action_version, executor_type, effect_class,
                    command_id, resolver_key, resolver_version, principal_reference,
                    principal_reference_hash, canonical_input_hash, state,
                    completed_at, retain_until
                )
                SELECT gen_random_uuid(), $1, $2, $2,
                       'performance.noise', '1', 'inline', 'read_only',
                       gen_random_uuid(), 'v070-performance', '1',
                       '{"version": 1}'::jsonb, repeat('a', 64), repeat('b', 64),
                       'succeeded', clock_timestamp(), clock_timestamp() + INTERVAL '1 hour'
                FROM generate_series(1, $3::integer)
                """,
                namespace,
                tenant,
                args.noise_rows,
            )

        counter_ids = [uuid4() for _ in range(args.operations)]
        with _tenant(tenant):
            async with database.acquire() as connection:
                await connection.executemany(
                    """
                    INSERT INTO v070_performance_counters (id, tenant_scope)
                    VALUES ($1, $2)
                    """,
                    [(counter_id, tenant) for counter_id in counter_ids],
                )

        admission_samples: list[float] = []

        async def admit_one(index: int):
            started = time.perf_counter()
            result = await service.admit(
                "performance.increment",
                "1",
                {"counter_id": str(counter_ids[index])},
                reference,
                idempotency_key=f"admission-{index}",
            )
            admission_samples.append(_elapsed_ms(started))
            return result

        admission_started = time.perf_counter()
        admissions = await asyncio.gather(*(admit_one(i) for i in range(args.operations)))
        admission_total_ms = _elapsed_ms(admission_started)

        with _tenant(tenant):
            await database.execute("ANALYZE aksara_operations")
            async with database.acquire() as connection:
                plan = await connection.fetchval(
                    """
                    EXPLAIN (FORMAT JSON)
                    SELECT * FROM aksara_operations
                    WHERE tenant_scope = $1 AND application_namespace = $2
                      AND (
                          (state = 'ready' AND available_at <= clock_timestamp())
                          OR (state = 'running' AND lease_expires_at <= clock_timestamp())
                      )
                    ORDER BY available_at, created_at
                    FOR UPDATE SKIP LOCKED LIMIT 1
                    """,
                    tenant,
                    namespace,
                )
        if isinstance(plan, str):
            plan = json.loads(plan)
        plan_text = json.dumps(plan)

        same_key_started = time.perf_counter()
        duplicate_results = await asyncio.gather(
            *(
                service.admit(
                    "performance.increment",
                    "1",
                    {"counter_id": str(counter_ids[0])},
                    reference,
                    idempotency_key="admission-0",
                )
                for _ in range(args.concurrency * 2)
            )
        )
        same_key_ms = _elapsed_ms(same_key_started)

        claim_samples: list[float] = []
        heartbeat_samples: list[float] = []
        completion_samples: list[float] = []
        processed: list[UUID] = []
        executor = PostgresAtomicExecutor(service)

        async def operation_worker(worker_index: int) -> None:
            while True:
                started = time.perf_counter()
                claim = await service.claim(
                    tenant_id=tenant,
                    worker_id=f"performance-worker-{worker_index}",
                )
                claim_samples.append(_elapsed_ms(started))
                if claim is None:
                    return
                started = time.perf_counter()
                await service.heartbeat(claim, lease_seconds=30)
                heartbeat_samples.append(_elapsed_ms(started))
                started = time.perf_counter()
                await executor.execute(claim)
                completion_samples.append(_elapsed_ms(started))
                processed.append(claim.operation_id)

        execution_started = time.perf_counter()
        await asyncio.gather(*(operation_worker(i) for i in range(args.concurrency)))
        execution_total_ms = _elapsed_ms(execution_started)
        claim_samples = claim_samples[: len(processed)]

        status_samples: list[float] = []
        for admission in admissions[: min(64, len(admissions))]:
            started = time.perf_counter()
            await service.get(
                admission.operation.id,
                tenant_id=tenant,
                principal=principal,
            )
            status_samples.append(_elapsed_ms(started))

        cancel_count = max(16, args.concurrency * 2)
        cancelled_admissions = await asyncio.gather(
            *(
                service.admit(
                    "performance.increment",
                    "1",
                    {"counter_id": str(uuid4())},
                    reference,
                )
                for _ in range(cancel_count)
            )
        )
        cancellation_samples: list[float] = []

        async def cancel_one(operation_id: UUID) -> None:
            started = time.perf_counter()
            await service.request_cancellation(
                operation_id,
                tenant_id=tenant,
                principal=principal,
                requester_reference=reference,
            )
            cancellation_samples.append(_elapsed_ms(started))

        await asyncio.gather(
            *(cancel_one(item.operation.id) for item in cancelled_admissions)
        )

        reclaim_ids = [uuid4() for _ in range(args.concurrency)]
        with _tenant(tenant):
            async with database.acquire() as connection:
                await connection.executemany(
                    "INSERT INTO v070_performance_counters (id, tenant_scope) VALUES ($1, $2)",
                    [(counter_id, tenant) for counter_id in reclaim_ids],
                )
        reclaim_admissions = await asyncio.gather(
            *(
                service.admit(
                    "performance.increment",
                    "1",
                    {"counter_id": str(counter_id)},
                    reference,
                )
                for counter_id in reclaim_ids
            )
        )
        stale_claims = await asyncio.gather(
            *(
                service.claim(
                    tenant_id=tenant,
                    worker_id=f"stale-{index}",
                    operation_id=item.operation.id,
                    lease_seconds=0.03,
                )
                for index, item in enumerate(reclaim_admissions)
            )
        )
        await asyncio.sleep(0.05)
        reclaim_samples: list[float] = []

        async def reclaim_one(index: int, operation_id: UUID):
            started = time.perf_counter()
            claim = await service.claim(
                tenant_id=tenant,
                worker_id=f"replacement-{index}",
                operation_id=operation_id,
            )
            reclaim_samples.append(_elapsed_ms(started))
            assert claim is not None
            await executor.execute(claim)
            return claim

        replacement_claims = await asyncio.gather(
            *(
                reclaim_one(index, item.operation.id)
                for index, item in enumerate(reclaim_admissions)
            )
        )

        task_count = max(8, args.concurrency)
        task_counter_ids = [uuid4() for _ in range(task_count)]
        with _tenant(tenant):
            async with database.acquire() as connection:
                await connection.executemany(
                    "INSERT INTO v070_performance_counters (id, tenant_scope) VALUES ($1, $2)",
                    [(counter_id, tenant) for counter_id in task_counter_ids],
                )
        task_admissions = await asyncio.gather(
            *(
                service.admit(
                    "performance.task_increment",
                    "1",
                    {"counter_id": str(counter_id)},
                    reference,
                )
                for counter_id in task_counter_ids
            )
        )
        await asyncio.gather(
            *(
                enqueue_operation_task(
                    item.operation.id,
                    service=service,
                    tenant_id=tenant,
                    queue="v070-performance",
                )
                for item in task_admissions
            )
        )
        task_worker = TaskWorker(
            database,
            durable_service=service,
            worker_id="v070-performance-task-worker",
            queues=["v070-performance"],
            poll_interval=0,
        )
        task_started = time.perf_counter()
        for _ in range(task_count):
            completed = await task_worker.poll_once()
            assert completed is not None and completed.status == "completed"
        task_total_ms = _elapsed_ms(task_started)

        prune_namespace = f"{namespace}-prune"
        prune_service = DurableOperationService(
            database,
            application_namespace=prune_namespace,
            actions=actions,
            resolvers=resolvers,
            retention_seconds=0.03,
            idempotency_seconds=0.04,
            result_retention_seconds=0.02,
            error_retention_seconds=0.02,
        )
        prune_count = 32
        prune_admissions = await asyncio.gather(
            *(
                prune_service.admit(
                    "performance.increment",
                    "1",
                    {"counter_id": str(uuid4())},
                    reference,
                    idempotency_key=f"prune-{index}",
                )
                for index in range(prune_count)
            )
        )
        await asyncio.gather(
            *(
                prune_service.request_cancellation(
                    item.operation.id,
                    tenant_id=tenant,
                    principal=principal,
                    requester_reference=reference,
                )
                for item in prune_admissions
            )
        )
        exporter = DurableOutboxExporter(prune_service, lambda _event: None, retry_seconds=0)
        while await exporter.export_once(tenant_id=tenant):
            pass
        await asyncio.sleep(0.06)
        prune_started = time.perf_counter()
        prune_result = await prune_service.prune(
            tenant_id=tenant,
            batch_size=prune_count * 4,
        )
        prune_ms = _elapsed_ms(prune_started)

        with _tenant(tenant):
            row_counts = {
                name: int(await database.fetchval(f"SELECT COUNT(*) FROM {name}"))
                for name in (
                    "aksara_operations",
                    "aksara_operation_attempts",
                    "aksara_operation_transitions",
                    "aksara_operation_outbox",
                )
            }
            relation_sizes = {
                name: int(
                    await database.fetchval(
                        "SELECT pg_total_relation_size($1::regclass)", name
                    )
                )
                for name in row_counts
            }
            mutated = int(
                await database.fetchval(
                    "SELECT COUNT(*) FROM v070_performance_counters WHERE mutation_counter = 1"
                )
            )

        pool_size = database.pool.get_size()
        pool_idle = database.pool.get_idle_size()
        metrics = {
            "admission": _summary(admission_samples),
            "claim": _summary(claim_samples),
            "heartbeat": _summary(heartbeat_samples),
            "atomic_completion": _summary(completion_samples),
            "status_read": _summary(status_samples),
            "cancellation": _summary(cancellation_samples),
            "reclaim": _summary(reclaim_samples),
        }
        max_p95 = max(float(value["p95_ms"]) for value in metrics.values())
        passed = bool(
            len({item.operation.id for item in duplicate_results}) == 1
            and all(not item.created for item in duplicate_results)
            and len(processed) == args.operations
            and len(replacement_claims) == len(stale_claims) == args.concurrency
            and all(
                replacement is not None
                and stale is not None
                and replacement.fence == stale.fence + 1
                for replacement, stale in zip(replacement_claims, stale_claims, strict=True)
            )
            and mutated == args.operations + args.concurrency + task_count
            and prune_result["operations"] == prune_count
            and prune_result["idempotency"] == prune_count
            and "idx_aksara_operations_claim" in plan_text
            and max_p95 < 5000
            and pool_idle == pool_size
        )
        return {
            "schema_version": 1,
            "gate": "v070-durable-performance-pathology",
            "status": "pass" if passed else "fail",
            "purpose": "pathology and contention detection; not a throughput claim",
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
            "environment": {
                "aksara": aksara.__version__,
                "python": platform.python_version(),
                "platform": platform.platform(),
                "postgresql": await admin.fetchval("SHOW server_version"),
                "database": urlsplit(args.database_url).path.lstrip("/"),
                "application_role": {"superuser": False, "bypass_rls": False},
            },
            "workload": {
                "operations": args.operations,
                "concurrent_workers": args.concurrency,
                "terminal_noise_rows": args.noise_rows,
                "task_linked_operations": task_count,
                "pruned_operations": prune_count,
            },
            "metrics": metrics,
            "aggregate": {
                "admission_total_ms": round(admission_total_ms, 3),
                "admission_per_second": round(args.operations / (admission_total_ms / 1000), 2),
                "execution_total_ms": round(execution_total_ms, 3),
                "execution_per_second": round(args.operations / (execution_total_ms / 1000), 2),
                "concurrent_same_key_total_ms": round(same_key_ms, 3),
                "task_linked_total_ms": round(task_total_ms, 3),
                "prune_total_ms": round(prune_ms, 3),
            },
            "invariants": {
                "one_operation_for_concurrent_same_key": len(
                    {item.operation.id for item in duplicate_results}
                )
                == 1,
                "all_claimed_operations_completed": len(processed) == args.operations,
                "reclaim_advanced_every_fence": all(
                    replacement is not None
                    and stale is not None
                    and replacement.fence == stale.fence + 1
                    for replacement, stale in zip(
                        replacement_claims, stale_claims, strict=True
                    )
                ),
                "claim_plan_uses_partial_index": "idx_aksara_operations_claim" in plan_text,
                "mutations_match_successful_operations": mutated
                == args.operations + args.concurrency + task_count,
                "pruning_is_bounded_and_complete": prune_result["operations"]
                == prune_count
                and prune_result["idempotency"] == prune_count,
                "pool_fully_idle": pool_idle == pool_size,
            },
            "query_plan": plan,
            "row_counts": row_counts,
            "relation_sizes_bytes": relation_sizes,
            "prune_result": prune_result,
            "limitations": [
                "Local single-host PostgreSQL sanity run; hosted PostgreSQL 16 is validated by CI.",
                "Numbers detect obvious regressions and do not define a capacity or latency SLO.",
            ],
        }
    finally:
        Database._instance = prior_database
        if database is not None:
            await database.disconnect()
        await admin.execute("SET search_path TO public")
        await admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = $1",
            role,
        )
        await admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await admin.execute(f'DROP ROLE IF EXISTS "{role}"')
        await admin.close()


async def _main() -> int:
    args = _parser().parse_args()
    try:
        evidence = await _run(args)
    except Exception as exc:  # noqa: BLE001 - CLI reports any campaign failure
        print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"{evidence['status'].upper()}: {args.output}")
    return 0 if evidence["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
