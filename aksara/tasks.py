"""
Built-in background task queue.

Provides a lightweight database-backed task registry, enqueue helpers,
and an application-owned worker loop.

Reliability features
--------------------
* FOR UPDATE SKIP LOCKED — prevents double-processing when multiple app
  instances share the same database.
* Stale lock recovery — the worker periodically resets tasks whose
  locked_at timestamp is older than task_stale_lock_timeout_seconds
  (default 300 s / 5 min), rescuing work that was claimed by a worker
  that crashed before it could finish.  The check runs every
  task_lock_recovery_interval_seconds (default 60 s).
* Exponential backoff — retry delays grow as
  retry_delay_seconds * retry_backoff_base^(attempt-1), capped at
  retry_max_delay_seconds.  Set retry_backoff_base=1.0 for flat delays.
* Configurable concurrency — each TaskWorker can process up to
  task_concurrency tasks simultaneously (default 1).
* Completed-task TTL — old records are purged automatically when
  task_result_ttl_seconds is set; cleaned up every
  task_cleanup_interval_seconds.
* Recurring tasks — register with every=timedelta(minutes=5) and the
  worker schedules them automatically via an atomic cron-state table.
* Named queues — tasks are tagged with a queue name; workers bind to one
  or more queues, isolating workloads across instances.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timedelta
from functools import update_wrapper
from typing import TYPE_CHECKING, Any, Literal, Optional, cast
from uuid import UUID, uuid4
from weakref import WeakSet

from aksara.db import Database, atomic
from aksara.logging import logger

if TYPE_CHECKING:
    from aksara.durable.service import DurableOperationService

TaskStatus = Literal["pending", "running", "completed", "failed"]

TASKS_TABLE = "aksara_tasks"
DURABLE_OPERATION_TASK_NAME = "aksara.durable.execute"
_STALE_OPERATION_RECOVERY_BATCH_SIZE = 100
TASKS_TABLE_SQL = f'''CREATE TABLE IF NOT EXISTS "{TASKS_TABLE}" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_name VARCHAR(255) NOT NULL,
    queue VARCHAR(100) NOT NULL DEFAULT 'default',
    tenant_id VARCHAR(255),
    payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    available_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    locked_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    last_error TEXT,
    result JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);'''
TASKS_INDEX_SQL = (
    f'CREATE INDEX IF NOT EXISTS "idx_{TASKS_TABLE}_pending" '
    f'ON "{TASKS_TABLE}" (queue, status, available_at, created_at)'
)
# Idempotent migration: adds queue column to tables created before this feature.
_TASKS_MIGRATE_QUEUE_SQL = (
    f'ALTER TABLE "{TASKS_TABLE}" ADD COLUMN IF NOT EXISTS '
    f"queue VARCHAR(100) NOT NULL DEFAULT 'default'"
)
# Idempotent migration: adds tenant_id so the durable task subsystem
# can persist tenant provenance for tasks enqueued under a tenant
# context. Nullable because tasks enqueued outside any tenant scope
# (e.g. internal jobs) are legitimate.
_TASKS_MIGRATE_TENANT_ID_SQL = (
    f'ALTER TABLE "{TASKS_TABLE}" ADD COLUMN IF NOT EXISTS '
    f'tenant_id VARCHAR(255)'
)

CRON_STATE_TABLE = "aksara_cron_state"
CRON_STATE_TABLE_SQL = f'''CREATE TABLE IF NOT EXISTS "{CRON_STATE_TABLE}" (
    task_name VARCHAR(255) PRIMARY KEY,
    last_enqueued_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);'''

_TASK_REGISTRY: dict[str, "RegisteredTask"] = {}
_TASKS_SCHEMA_READY_FOR: WeakSet[Database] = WeakSet()
_CRON_SCHEMA_READY_FOR: WeakSet[Database] = WeakSet()


@dataclass
class TaskRecord:
    """Persisted background task state."""

    id: UUID
    task_name: str
    payload: dict[str, Any]
    status: TaskStatus
    attempts: int
    max_attempts: int
    queue: str = "default"
    # tenant_id is captured at enqueue time from tenant_id_var so the
    # worker can restore the same tenant context before executing the
    # callable. Nullable because tasks may be enqueued outside any
    # tenant scope (e.g. internal jobs).
    tenant_id: Optional[str] = None
    operation_id: UUID | None = None
    operation_application_namespace: str | None = None
    available_at: Optional[datetime] = None
    locked_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_error: Optional[str] = None
    result: Any = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_record(cls, record: Any) -> "TaskRecord":
        """Convert a database record into a TaskRecord."""
        return cls(
            id=record["id"],
            task_name=record["task_name"],
            queue=record.get("queue", "default") or "default",
            tenant_id=record.get("tenant_id"),
            operation_id=record.get("operation_id"),
            operation_application_namespace=record.get(
                "operation_application_namespace"
            ),
            payload=_decode_json_value(record["payload"]) or {},
            status=record["status"],
            attempts=record["attempts"],
            max_attempts=record["max_attempts"],
            available_at=record.get("available_at"),
            locked_at=record.get("locked_at"),
            completed_at=record.get("completed_at"),
            last_error=record.get("last_error"),
            result=_decode_json_value(record.get("result")),
            created_at=record.get("created_at"),
            updated_at=record.get("updated_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the task record into a dictionary."""
        return asdict(self)


def _get_db(db: Optional[Database] = None) -> Database:
    """Return the active database instance."""
    if db is not None:
        return db
    return Database.get_instance()


def _default_serializer(value: Any) -> Any:
    """Convert common Python values into JSON-safe payloads."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return asdict(cast(Any, value))
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(
        "Task payloads and results must be JSON-serializable or provide a serializable representation"
    )


def _encode_json_value(value: Any) -> Any:
    """Normalize a value into JSON-safe primitives."""
    return json.loads(json.dumps(value, default=_default_serializer))


def _decode_json_value(value: Any) -> Any:
    """Decode JSON payloads returned by the database."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


class RegisteredTask:
    """Callable task wrapper that keeps queue metadata and enqueue helpers."""

    def __init__(
        self,
        func: Callable[..., Any],
        *,
        name: Optional[str] = None,
        max_attempts: Optional[int] = None,
        queue: str = "default",
        every: Optional[timedelta] = None,
    ):
        update_wrapper(self, func)
        self.func = func
        self.name = name or f"{func.__module__}.{func.__qualname__}"
        self.max_attempts = max_attempts
        self.queue = queue
        self.every = every

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.func(*args, **kwargs)

    async def enqueue(
        self,
        *args: Any,
        db: Optional[Database] = None,
        delay_seconds: float = 0.0,
        max_attempts: Optional[int] = None,
        queue: Optional[str] = None,
        **kwargs: Any,
    ) -> TaskRecord:
        """Enqueue the task for background execution."""
        return await enqueue_task(
            self,
            *args,
            db=db,
            delay_seconds=delay_seconds,
            max_attempts=max_attempts,
            queue=queue,
            **kwargs,
        )

    delay = enqueue


def clear_task_registry() -> None:
    """Clear registered tasks. Primarily useful in tests."""
    _TASK_REGISTRY.clear()


def get_registered_task(name: str) -> "RegisteredTask":
    """Return a registered task by name."""
    task_definition = _TASK_REGISTRY.get(name)
    if task_definition is None:
        raise KeyError(f"Task '{name}' is not registered")
    return task_definition


def task(
    func: Optional[Callable[..., Any]] = None,
    *,
    name: Optional[str] = None,
    max_attempts: Optional[int] = None,
    queue: str = "default",
    every: Optional[timedelta | int | float] = None,
) -> "RegisteredTask | Callable[[Callable[..., Any]], RegisteredTask]":
    """Register a function as a durable background task.

    Args:
        name: Override the auto-derived task name (module.qualname).
        max_attempts: Max retry attempts (overrides global setting).
        queue: Named queue this task belongs to (default: "default").
        every: Recurring schedule — a timedelta or seconds as int/float.
               When set, the worker automatically enqueues the task each
               time the interval elapses.
    """

    def decorator(target: Callable[..., Any]) -> RegisteredTask:
        every_td: Optional[timedelta] = None
        if every is not None:
            every_td = every if isinstance(every, timedelta) else timedelta(seconds=float(every))
        registered = RegisteredTask(
            target,
            name=name,
            max_attempts=max_attempts,
            queue=queue,
            every=every_td,
        )
        _TASK_REGISTRY[registered.name] = registered
        return registered

    if func is None:
        return decorator
    return decorator(func)


async def ensure_tasks_table(db: Optional[Database] = None) -> None:
    """Create (or migrate) the internal task table."""
    database = _get_db(db)
    if database in _TASKS_SCHEMA_READY_FOR:
        return
    ready = await database.fetchval(
        f"""
        SELECT
            (
                SELECT COUNT(*) = 15
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = '{TASKS_TABLE}'
                  AND column_name IN (
                      'id', 'task_name', 'queue', 'tenant_id', 'payload', 'status',
                      'attempts', 'max_attempts', 'available_at', 'locked_at',
                      'completed_at', 'last_error', 'result', 'created_at', 'updated_at'
                  )
            )
            AND EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = current_schema()
                  AND tablename = '{TASKS_TABLE}'
                  AND indexname = 'idx_{TASKS_TABLE}_pending'
            )
        """
    )
    if ready:
        _TASKS_SCHEMA_READY_FOR.add(database)
        return

    await database.execute(TASKS_TABLE_SQL)
    await database.execute(_TASKS_MIGRATE_QUEUE_SQL)
    await database.execute(_TASKS_MIGRATE_TENANT_ID_SQL)
    await database.execute(TASKS_INDEX_SQL)
    _TASKS_SCHEMA_READY_FOR.add(database)


async def ensure_cron_state_table(db: Optional[Database] = None) -> None:
    """Create the recurring-task cron-state table when needed."""
    database = _get_db(db)
    if database in _CRON_SCHEMA_READY_FOR:
        return
    ready = await database.fetchval(
        f"""
        SELECT COUNT(*) = 2
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = '{CRON_STATE_TABLE}'
          AND column_name IN ('task_name', 'last_enqueued_at')
        """
    )
    if ready:
        _CRON_SCHEMA_READY_FOR.add(database)
        return
    await database.execute(CRON_STATE_TABLE_SQL)
    _CRON_SCHEMA_READY_FOR.add(database)


def _resolve_task_definition(task_ref: "str | RegisteredTask") -> RegisteredTask:
    """Resolve a task name or wrapper into a registered task definition."""
    if isinstance(task_ref, RegisteredTask):
        return task_ref
    return get_registered_task(task_ref)


async def enqueue_task(
    task_ref: "str | RegisteredTask",
    *args: Any,
    db: Optional[Database] = None,
    delay_seconds: float = 0.0,
    max_attempts: Optional[int] = None,
    queue: Optional[str] = None,
    **kwargs: Any,
) -> TaskRecord:
    """Persist a task invocation for background execution."""
    from aksara.conf import settings

    # Capture the enqueuing tenant context so the worker can restore the
    # same tenant scope at execution time. Without this the durable
    # payload drops all tenant provenance and tenant-aware ORM operations
    # inside the task would run with tenant_id_var=None.
    from aksara.context_state import tenant_id_var

    database = _get_db(db)
    await ensure_tasks_table(database)

    task_definition = _resolve_task_definition(task_ref)
    effective_max_attempts = max_attempts or task_definition.max_attempts or settings.task_max_attempts
    effective_queue = queue if queue is not None else task_definition.queue
    current_tenant = tenant_id_var.get()
    tenant_value: Optional[str] = (
        str(current_tenant) if current_tenant is not None else None
    )
    payload = _encode_json_value({"args": list(args), "kwargs": kwargs})

    record = await database.fetchrow(
        f'''
        INSERT INTO "{TASKS_TABLE}" (task_name, queue, tenant_id, payload, max_attempts, available_at)
        VALUES (
            $1, $2, $3, $4, $5,
            CURRENT_TIMESTAMP + ($6::double precision * INTERVAL '1 second')
        )
        RETURNING *
        ''',
        task_definition.name,
        effective_queue,
        tenant_value,
        json.dumps(payload),
        effective_max_attempts,
        delay_seconds,
    )
    if record is None:
        raise RuntimeError(f"Failed to enqueue task '{task_definition.name}'")
    return TaskRecord.from_record(record)


async def enqueue_operation_task(
    operation_id: UUID,
    *,
    service: DurableOperationService,
    tenant_id: str | None,
    queue: str = "default",
    delay_seconds: float = 0.0,
) -> TaskRecord:
    """Create the optional task projection for a task-backed Operation.

    The Operation remains authoritative. Repeated calls return the one task
    already linked to the logical operation.
    """

    from aksara.durable.errors import OperationNotFound
    from aksara.durable.service import _tenant_context
    from aksara.durable.types import tenant_scope

    database = service.db
    scope = tenant_scope(tenant_id)
    with _tenant_context(scope):
        async with database.acquire() as connection:
            operation = await service.repository.get_operation(
                connection, operation_id, scope, service.application_namespace
            )
            if operation is None:
                raise OperationNotFound("operation was not found in the active tenant")
            if operation["executor_type"] != "task":
                raise ValueError("only actions registered with executor_type='task' may be linked")
            record = await connection.fetchrow(
                f'''
                INSERT INTO "{TASKS_TABLE}" (
                    task_name, queue, tenant_id, payload, max_attempts,
                    available_at, operation_id, operation_application_namespace
                ) VALUES (
                    $1, $2, $3, '{{}}'::jsonb, $4,
                    CURRENT_TIMESTAMP + ($5::double precision * INTERVAL '1 second'),
                    $6, $7
                )
                ON CONFLICT (operation_id) WHERE operation_id IS NOT NULL
                DO UPDATE SET
                    operation_id = EXCLUDED.operation_id,
                    operation_application_namespace = EXCLUDED.operation_application_namespace
                RETURNING *
                ''',
                DURABLE_OPERATION_TASK_NAME,
                queue,
                operation["tenant_id"],
                operation["max_attempts"],
                delay_seconds,
                operation_id,
                service.application_namespace,
            )
    if record is None:
        raise RuntimeError("failed to enqueue operation-backed task")
    return TaskRecord.from_record(record)


async def get_task_record(
    task_id: UUID,
    db: Optional[Database] = None,
) -> Optional[TaskRecord]:
    """Load a task record by id."""
    database = _get_db(db)
    await ensure_tasks_table(database)
    record = await database.fetchrow(
        f'SELECT * FROM "{TASKS_TABLE}" WHERE id = $1',
        task_id,
    )
    if record is None:
        return None
    return TaskRecord.from_record(record)


class TaskWorker:
    """Polling worker that executes tasks from the database queue.

    One instance is created per Aksara app and runs its own asyncio loop.
    Multiple app instances can share the same queue safely — PostgreSQL row
    locks (FOR UPDATE SKIP LOCKED) prevent double-processing.

    The worker also runs periodic stale lock recovery: tasks whose locked_at
    is older than stale_lock_timeout_seconds are reset to 'pending' so they
    can be re-claimed by a healthy worker.

    Set concurrency > 1 to process multiple tasks simultaneously within a
    single worker instance.
    """

    def __init__(
        self,
        db: Optional[Database] = None,
        *,
        poll_interval: Optional[float] = None,
        retry_delay_seconds: Optional[float] = None,
        stale_lock_timeout_seconds: Optional[float] = None,
        lock_recovery_interval_seconds: Optional[float] = None,
        concurrency: Optional[int] = None,
        retry_backoff_base: Optional[float] = None,
        retry_max_delay_seconds: Optional[float] = None,
        result_ttl_seconds: Optional[float] = None,
        cleanup_interval_seconds: Optional[float] = None,
        cron_check_interval_seconds: Optional[float] = None,
        queues: Optional[list[str]] = None,
        durable_service: DurableOperationService | None = None,
        worker_id: str | None = None,
        _boundary_hook: Callable[[str], None | Awaitable[None]] | None = None,
    ):
        from aksara.conf import settings

        self._db = db
        self.poll_interval = (
            poll_interval if poll_interval is not None else settings.task_poll_interval_seconds
        )
        self.retry_delay_seconds = (
            retry_delay_seconds
            if retry_delay_seconds is not None
            else settings.task_retry_delay_seconds
        )
        self.stale_lock_timeout_seconds = (
            stale_lock_timeout_seconds
            if stale_lock_timeout_seconds is not None
            else settings.task_stale_lock_timeout_seconds
        )
        self.lock_recovery_interval_seconds = (
            lock_recovery_interval_seconds
            if lock_recovery_interval_seconds is not None
            else settings.task_lock_recovery_interval_seconds
        )
        self.concurrency = (
            concurrency if concurrency is not None else settings.task_concurrency
        )
        self.retry_backoff_base = (
            retry_backoff_base
            if retry_backoff_base is not None
            else settings.task_retry_backoff_base
        )
        self.retry_max_delay_seconds = (
            retry_max_delay_seconds
            if retry_max_delay_seconds is not None
            else settings.task_retry_max_delay_seconds
        )
        self.result_ttl_seconds = (
            result_ttl_seconds
            if result_ttl_seconds is not None
            else settings.task_result_ttl_seconds
        )
        self.cleanup_interval_seconds = (
            cleanup_interval_seconds
            if cleanup_interval_seconds is not None
            else settings.task_cleanup_interval_seconds
        )
        self.cron_check_interval_seconds = (
            cron_check_interval_seconds
            if cron_check_interval_seconds is not None
            else settings.task_cron_check_interval_seconds
        )
        # None → all queues; list → only those queues
        self.queues: Optional[list[str]] = queues
        self.durable_service = durable_service
        self.worker_id = worker_id or f"task-worker-{uuid4()}"
        self._boundary_hook = _boundary_hook

        self._last_recovery: float = 0.0
        self._last_cleanup: float = 0.0
        self._last_cron_check: float = 0.0
        self._runner_task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()

    @property
    def running(self) -> bool:
        """Return True when the background loop is active."""
        return self._runner_task is not None and not self._runner_task.done()

    async def start(self) -> None:
        """Start the background polling loop."""
        if self.running:
            return

        await ensure_tasks_table(self._db)
        self._stop_event = asyncio.Event()
        self._runner_task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Stop the background polling loop and drain in-flight tasks."""
        if self._runner_task is None:
            return

        self._stop_event.set()
        runner = self._runner_task
        self._runner_task = None
        await runner

    async def poll_once(self) -> Optional[TaskRecord]:
        """Claim and process a single pending task if one is available."""
        database = _get_db(self._db)
        await ensure_tasks_table(database)

        await self._at_boundary("before_task_claim")
        task_record = await self._claim_task()
        if task_record is None:
            return None
        await self._at_boundary("after_task_claim")

        await self._process_task(task_record)
        refreshed = await get_task_record(task_record.id, db=database)
        return refreshed or task_record

    async def _at_boundary(self, name: str) -> None:
        """Invoke the private process-failure campaign seam, when configured."""

        if self._boundary_hook is None:
            return
        result = self._boundary_hook(name)
        if inspect.isawaitable(result):
            await result

    async def recover_stale_locks(self) -> int:
        """Reset tasks stuck in 'running' state back to 'pending'.

        A task is considered stale when its locked_at timestamp is older than
        stale_lock_timeout_seconds, which typically means the worker that claimed
        it crashed before completing execution.

        Returns the number of tasks recovered.
        """
        database = _get_db(self._db)
        await ensure_tasks_table(database)
        result = await database.fetchrow(
            f'''
            WITH recovered AS (
                UPDATE "{TASKS_TABLE}" AS task
                SET
                    status = 'pending',
                    locked_at = NULL,
                    available_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE
                    status = 'running'
                    AND (to_jsonb(task) ->> 'operation_id') IS NULL
                    AND locked_at < CURRENT_TIMESTAMP - ($1::double precision * INTERVAL '1 second')
                RETURNING id
            )
            SELECT COUNT(*) AS count FROM recovered
            ''',
            self.stale_lock_timeout_seconds,
        )
        count = int(result["count"]) if result else 0
        if self.durable_service is not None:
            count += await self._recover_stale_operation_tasks(database)
        if count > 0:
            logger.warning("Recovered %d stale task(s) stuck in 'running' state", count)
        return count

    async def _recover_stale_operation_tasks(self, database: Database) -> int:
        """Project stale linked tasks under each Operation's tenant scope."""

        from aksara.durable.service import _tenant_context
        from aksara.durable.types import tenant_scope

        recovered = 0
        assert self.durable_service is not None
        cursor_locked_at = None
        cursor_id = None
        while True:
            stale_tasks = await database.fetch(
                f'''
                SELECT * FROM "{TASKS_TABLE}"
                WHERE status = 'running' AND operation_id IS NOT NULL
                  AND operation_application_namespace = $5
                  AND locked_at < CURRENT_TIMESTAMP
                      - ($1::double precision * INTERVAL '1 second')
                  AND (
                      $2::timestamptz IS NULL
                      OR locked_at > $2
                      OR (locked_at = $2 AND id > $3)
                  )
                ORDER BY locked_at, id
                LIMIT $4
                ''',
                self.stale_lock_timeout_seconds,
                cursor_locked_at,
                cursor_id,
                _STALE_OPERATION_RECOVERY_BATCH_SIZE,
                self.durable_service.application_namespace,
            )
            if not stale_tasks:
                break
            cursor_locked_at = stale_tasks[-1]["locked_at"]
            cursor_id = stale_tasks[-1]["id"]
            for task_row in stale_tasks:
                task_record = TaskRecord.from_record(task_row)
                if task_record.operation_id is None:
                    continue
                scope = tenant_scope(task_record.tenant_id)
                with _tenant_context(scope):
                    async with atomic(db=database) as connection:
                        operation = await self.durable_service.repository.get_operation(
                            connection,
                            task_record.operation_id,
                            scope,
                            self.durable_service.application_namespace,
                            for_update=True,
                        )
                        if operation is None:
                            continue
                        state = operation["state"]
                        terminal = state in {
                            "succeeded",
                            "failed",
                            "cancelled",
                            "expired",
                        }
                        reclaimable = state in {"waiting_for_approval", "ready"} or (
                            state == "running"
                            and operation["lease_expires_at"]
                            <= await connection.fetchval("SELECT clock_timestamp()")
                        )
                        if not terminal and not reclaimable:
                            continue
                        status = (
                            "completed" if state == "succeeded" else "failed"
                            if terminal
                            else "pending"
                        )
                        result = operation["result"] if state == "succeeded" else None
                        error = (
                            None
                            if state == "succeeded" or not terminal
                            else (_decode_json_value(operation["error"]) or {}).get(
                                "message", state
                            )
                        )
                        update_status = await connection.execute(
                            f'''
                            UPDATE "{TASKS_TABLE}"
                            SET status = $2::varchar, result = $3::jsonb,
                                last_error = $4, locked_at = NULL,
                                completed_at = CASE WHEN $2::varchar = 'completed'
                                    THEN COALESCE($5, CURRENT_TIMESTAMP) ELSE completed_at END,
                                available_at = CASE WHEN $2::varchar = 'pending'
                                    THEN CURRENT_TIMESTAMP ELSE available_at END,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = $1 AND status = 'running'
                              AND operation_application_namespace = $7
                              AND locked_at < CURRENT_TIMESTAMP
                                  - ($6::double precision * INTERVAL '1 second')
                            ''',
                            task_record.id,
                            status,
                            json.dumps(_encode_json_value(result))
                            if result is not None
                            else None,
                            error,
                            operation["completed_at"],
                            self.stale_lock_timeout_seconds,
                            self.durable_service.application_namespace,
                        )
                        recovered += update_status == "UPDATE 1"
        return recovered

    async def purge_old_tasks(
        self,
        *,
        statuses: tuple[str, ...] = ("completed",),
        older_than_seconds: Optional[float] = None,
    ) -> int:
        """Delete task records older than a TTL threshold.

        Args:
            statuses: Which status values to purge (default: completed only).
            older_than_seconds: Age threshold in seconds; falls back to
                result_ttl_seconds if not given.  Returns 0 if both are None.

        Returns the number of rows deleted.
        """
        timeout = older_than_seconds if older_than_seconds is not None else self.result_ttl_seconds
        if timeout is None:
            return 0

        database = _get_db(self._db)
        await ensure_tasks_table(database)
        application_namespace = (
            self.durable_service.application_namespace
            if self.durable_service is not None
            else None
        )
        result = await database.fetchrow(
            f'''
            WITH deleted AS (
                DELETE FROM "{TASKS_TABLE}" AS task
                WHERE status = ANY($1::text[])
                  AND updated_at < CURRENT_TIMESTAMP - ($2::double precision * INTERVAL '1 second')
                  AND (
                      (to_jsonb(task) ->> 'operation_id') IS NULL
                      OR (to_jsonb(task) ->> 'operation_application_namespace') = $3
                  )
                RETURNING id
            )
            SELECT COUNT(*) AS count FROM deleted
            ''',
            list(statuses),
            timeout,
            application_namespace,
        )
        count = int(result["count"]) if result else 0
        if count > 0:
            logger.info("Purged %d old task record(s) (TTL %.0fs)", count, timeout)
        return count

    async def _claim_task(self) -> Optional[TaskRecord]:
        """Atomically claim the next available task. Returns None if queue is empty."""
        database = _get_db(self._db)
        await ensure_tasks_table(database)

        if self.queues is not None and self.durable_service is not None:
            record = await database.fetchrow(
                f'''
                WITH next_task AS (
                    SELECT id
                    FROM "{TASKS_TABLE}"
                    WHERE status = 'pending'
                      AND available_at <= CURRENT_TIMESTAMP
                      AND (
                          operation_id IS NULL
                          OR operation_application_namespace = $2
                      )
                      AND queue = ANY($1::text[])
                    ORDER BY available_at ASC, created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE "{TASKS_TABLE}"
                SET
                    status = 'running',
                    attempts = attempts + 1,
                    locked_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id IN (SELECT id FROM next_task)
                RETURNING *
                ''',
                self.queues,
                self.durable_service.application_namespace,
            )
        elif self.queues is not None:
            record = await database.fetchrow(
                f'''
                WITH next_task AS (
                    SELECT id
                    FROM "{TASKS_TABLE}" AS task
                    WHERE status = 'pending'
                      AND available_at <= CURRENT_TIMESTAMP
                      AND (to_jsonb(task) ->> 'operation_id') IS NULL
                      AND queue = ANY($1::text[])
                    ORDER BY available_at ASC, created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE "{TASKS_TABLE}"
                SET
                    status = 'running',
                    attempts = attempts + 1,
                    locked_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id IN (SELECT id FROM next_task)
                RETURNING *
                ''',
                self.queues,
            )
        elif self.durable_service is not None:
            record = await database.fetchrow(
                f'''
                WITH next_task AS (
                    SELECT id
                    FROM "{TASKS_TABLE}"
                    WHERE status = 'pending' AND available_at <= CURRENT_TIMESTAMP
                      AND (
                          operation_id IS NULL
                          OR operation_application_namespace = $1
                      )
                    ORDER BY available_at ASC, created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE "{TASKS_TABLE}"
                SET
                    status = 'running',
                    attempts = attempts + 1,
                    locked_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id IN (SELECT id FROM next_task)
                RETURNING *
                ''',
                self.durable_service.application_namespace,
            )
        else:
            record = await database.fetchrow(
                f'''
                WITH next_task AS (
                    SELECT id
                    FROM "{TASKS_TABLE}" AS task
                    WHERE status = 'pending' AND available_at <= CURRENT_TIMESTAMP
                      AND (to_jsonb(task) ->> 'operation_id') IS NULL
                    ORDER BY available_at ASC, created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE "{TASKS_TABLE}"
                SET
                    status = 'running',
                    attempts = attempts + 1,
                    locked_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id IN (SELECT id FROM next_task)
                RETURNING *
                '''
            )

        if record is None:
            return None
        return TaskRecord.from_record(record)

    async def _schedule_recurring_tasks(self) -> int:
        """Enqueue any recurring tasks whose interval has elapsed.

        Uses an atomic INSERT … ON CONFLICT DO UPDATE … WHERE so that only
        one worker across all instances enqueues each due task.

        Returns the count of tasks enqueued this cycle.
        """
        database = _get_db(self._db)
        await ensure_cron_state_table(database)
        await ensure_tasks_table(database)

        count = 0
        for name, task_def in list(_TASK_REGISTRY.items()):
            if task_def.every is None:
                continue
            if self.queues is not None and task_def.queue not in self.queues:
                continue

            interval_seconds = task_def.every.total_seconds()

            # Claim the scheduling slot atomically.
            # INSERT path: first-ever registration — run immediately, record now.
            # ON CONFLICT path: re-run only when the interval has elapsed since
            #   last_enqueued_at; update the timestamp to prevent double-firing.
            record = await database.fetchrow(
                f'''
                INSERT INTO "{CRON_STATE_TABLE}" (task_name, last_enqueued_at)
                VALUES ($1, CURRENT_TIMESTAMP)
                ON CONFLICT (task_name) DO UPDATE
                  SET last_enqueued_at = CURRENT_TIMESTAMP
                  WHERE "{CRON_STATE_TABLE}".last_enqueued_at
                        < CURRENT_TIMESTAMP - ($2::double precision * INTERVAL '1 second')
                RETURNING task_name
                ''',
                name,
                interval_seconds,
            )

            if record is not None:
                try:
                    await enqueue_task(task_def, db=database)
                    count += 1
                    logger.debug("Scheduled recurring task '%s'", name)
                except Exception:
                    logger.exception("Failed to enqueue recurring task '%s'", name)

        return count

    async def _run_loop(self) -> None:
        """Continuously poll for work until asked to stop."""
        active_tasks: set[asyncio.Task[Any]] = set()

        while not self._stop_event.is_set():
            now = time.monotonic()

            # Stale lock recovery
            if now - self._last_recovery >= self.lock_recovery_interval_seconds:
                try:
                    await self.recover_stale_locks()
                except Exception:
                    logger.exception("Stale lock recovery failed")
                self._last_recovery = now

            # Completed task cleanup
            if (
                self.result_ttl_seconds is not None
                and now - self._last_cleanup >= self.cleanup_interval_seconds
            ):
                try:
                    await self.purge_old_tasks()
                except Exception:
                    logger.exception("Task cleanup failed")
                self._last_cleanup = now

            # Recurring task scheduling
            if now - self._last_cron_check >= self.cron_check_interval_seconds:
                try:
                    await self._schedule_recurring_tasks()
                except Exception:
                    logger.exception("Recurring task scheduling failed")
                self._last_cron_check = now

            # Fill up to concurrency limit
            while len(active_tasks) < self.concurrency:
                try:
                    record = await self._claim_task()
                except Exception:
                    logger.exception("Task worker poll failed")
                    break
                if record is None:
                    break
                t = asyncio.create_task(self._process_task(record))
                active_tasks.add(t)
                t.add_done_callback(
                    lambda completed: self._consume_active_task(
                        active_tasks, completed
                    )
                )

            if not active_tasks:
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval)
                except asyncio.TimeoutError:
                    pass
            else:
                _, _ = await asyncio.wait(
                    active_tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=self.poll_interval,
                )

        # Drain in-flight tasks gracefully before shutdown
        if active_tasks:
            await asyncio.gather(*active_tasks, return_exceptions=True)

    @staticmethod
    def _consume_active_task(
        active_tasks: set[asyncio.Task[Any]],
        completed: asyncio.Task[Any],
    ) -> None:
        """Remove a child task and retrieve failures reported by asyncio."""

        active_tasks.discard(completed)
        if completed.cancelled():
            return
        try:
            completed.result()
        except Exception:  # noqa: BLE001 - callback must retrieve every child failure
            logger.exception("Task worker child failed")

    async def _process_task(self, task_record: TaskRecord) -> None:
        """Execute a claimed task and persist the outcome."""
        from aksara.context_state import tenant_id_var

        database = _get_db(self._db)

        if task_record.operation_id is not None:
            try:
                await self._process_operation_task(task_record)
            except Exception:  # noqa: BLE001 - durable state is authoritative
                logger.exception(
                    "Linked operation task '%s' failed; projecting durable state",
                    task_record.id,
                )
                await self._project_current_operation_task(task_record)
            return

        # Restore the tenant context captured at enqueue time so the
        # callable observes the same tenant scope it was scheduled
        # under. Without this, tenant-aware ORM operations inside the
        # task run with tenant_id_var=None and escape tenant isolation.
        tenant_token = tenant_id_var.set(task_record.tenant_id)
        try:
            try:
                task_definition = get_registered_task(task_record.task_name)
                result = await self._execute_callable(task_definition, task_record.payload)
            except Exception as exc:
                logger.exception("Task '%s' failed", task_record.task_name)
                await self._mark_failure(task_record, str(exc), db=database)
                return
        finally:
            tenant_id_var.reset(tenant_token)

        encoded_result = _encode_json_value(result)
        await database.execute(
            f'''
            UPDATE "{TASKS_TABLE}"
            SET
                status = 'completed',
                result = $1,
                last_error = NULL,
                locked_at = NULL,
                completed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $2
            ''',
            json.dumps(encoded_result),
            task_record.id,
        )

    async def _process_operation_task(self, task_record: TaskRecord) -> None:
        """Delegate a linked task to Operation claim/fence authority."""

        service = self.durable_service
        if service is None or task_record.operation_id is None:
            return
        if task_record.operation_application_namespace != service.application_namespace:
            return
        from aksara.durable.execution import PostgresAtomicExecutor, ReadOnlyExecutor
        from aksara.durable.service import _tenant_context
        from aksara.durable.types import EffectClass, tenant_scope

        scope = tenant_scope(task_record.tenant_id)
        await self._at_boundary("before_operation_claim")
        claim = await service.claim(
            tenant_id=task_record.tenant_id,
            worker_id=f"{self.worker_id}:{task_record.id}",
            operation_id=task_record.operation_id,
            lease_seconds=self.stale_lock_timeout_seconds,
        )
        if claim is None:
            with _tenant_context(scope):
                async with service.db.acquire() as connection:
                    operation = await service.repository.get_public_operation(
                        connection,
                        task_record.operation_id,
                        scope,
                        service.application_namespace,
                    )
            if operation is None or operation.state.value != "running":
                await self._project_operation_task(task_record, operation)
            return
        await self._at_boundary("after_operation_claim")

        if claim.effect_class is EffectClass.POSTGRES_ATOMIC:
            operation = await PostgresAtomicExecutor(
                service,
                _boundary_hook=self._at_boundary,
            ).execute(claim)
        elif claim.effect_class is EffectClass.READ_ONLY:
            operation = await ReadOnlyExecutor(
                service,
                lease_seconds=self.stale_lock_timeout_seconds,
            ).execute(claim)
        elif claim.effect_class in {
            EffectClass.EXTERNAL_IDEMPOTENT,
            EffectClass.EXTERNAL_AT_LEAST_ONCE,
            EffectClass.EXTERNAL_NONRETRYABLE,
        }:
            from aksara.durable.worker import DurableOperationWorker

            operation = await DurableOperationWorker(
                service,
                worker_id=claim.worker_id,
                lease_seconds=self.stale_lock_timeout_seconds,
            ).execute_claim(claim)
        else:
            operation = await service.fail_attempt(
                claim,
                code="unsupported_task_effect_class",
                message="task adapter does not execute this effect class",
                retryable=False,
            )
        await self._at_boundary("after_operation_commit")
        await self._at_boundary("before_task_projection")
        await self._project_operation_task(task_record, operation)

    async def _project_current_operation_task(
        self,
        task_record: TaskRecord,
    ) -> None:
        """Recover a linked task from its authoritative Operation state."""

        service = self.durable_service
        if service is None or task_record.operation_id is None:
            return
        from aksara.durable.service import _tenant_context
        from aksara.durable.types import tenant_scope

        scope = tenant_scope(task_record.tenant_id)
        with _tenant_context(scope):
            async with service.db.acquire() as connection:
                operation = await service.repository.get_public_operation(
                    connection,
                    task_record.operation_id,
                    scope,
                    service.application_namespace,
                )
        await self._project_operation_task(task_record, operation)

    async def _project_operation_task(self, task_record: TaskRecord, operation: Any) -> None:
        """Update the compatibility task row from authoritative Operation state."""

        database = _get_db(self._db)
        if operation is None:
            status, result, error, delay = "failed", None, "operation missing", 0.0
        elif operation.state.value == "succeeded":
            status, result, error, delay = "completed", operation.result, None, 0.0
        elif operation.state.value in {"failed", "cancelled", "expired"}:
            message = (
                operation.error.get("message", operation.state.value)
                if isinstance(operation.error, dict)
                else operation.state.value
            )
            status, result, error, delay = "failed", None, message, 0.0
        else:
            status, result, error, delay = "pending", None, None, self.poll_interval
        await database.execute(
            f'''
            UPDATE "{TASKS_TABLE}"
            SET status = $2::varchar, result = $3::jsonb, last_error = $4,
                locked_at = NULL,
                completed_at = CASE WHEN $2::varchar = 'completed'
                    THEN CURRENT_TIMESTAMP ELSE NULL END,
                available_at = CASE WHEN $2::varchar = 'pending'
                    THEN CURRENT_TIMESTAMP + ($5::double precision * INTERVAL '1 second')
                    ELSE available_at END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1 AND operation_id = $6 AND status = 'running'
              AND operation_application_namespace = $9
              AND attempts = $7 AND locked_at = $8
            ''',
            task_record.id,
            status,
            json.dumps(_encode_json_value(result)) if result is not None else None,
            error,
            delay,
            task_record.operation_id,
            task_record.attempts,
            task_record.locked_at,
            task_record.operation_application_namespace,
        )

    async def _execute_callable(
        self,
        task_definition: RegisteredTask,
        payload: dict[str, Any],
    ) -> Any:
        """Execute a registered task from its serialized payload."""
        args = list(payload.get("args", []))
        kwargs = dict(payload.get("kwargs", {}))
        func = task_definition.func

        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)

        result = await asyncio.to_thread(func, *args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    async def _mark_failure(
        self,
        task_record: TaskRecord,
        error: str,
        *,
        db: Optional[Database] = None,
    ) -> None:
        """Persist a failed attempt and optionally reschedule it with backoff."""
        database = _get_db(db)
        should_retry = task_record.attempts < task_record.max_attempts

        if should_retry:
            # Exponential backoff: base_delay * backoff_base^(attempt-1), capped.
            delay = min(
                self.retry_delay_seconds * (self.retry_backoff_base ** (task_record.attempts - 1)),
                self.retry_max_delay_seconds,
            )
            await database.execute(
                f'''
                UPDATE "{TASKS_TABLE}"
                SET
                    status = 'pending',
                    last_error = $1,
                    locked_at = NULL,
                    available_at = CURRENT_TIMESTAMP + ($2::double precision * INTERVAL '1 second'),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $3
                ''',
                error,
                delay,
                task_record.id,
            )
            return

        await database.execute(
            f'''
            UPDATE "{TASKS_TABLE}"
            SET
                status = 'failed',
                last_error = $1,
                locked_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $2
            ''',
            error,
            task_record.id,
        )


__all__ = [
    "CRON_STATE_TABLE",
    "DURABLE_OPERATION_TASK_NAME",
    "TASKS_TABLE",
    "TaskRecord",
    "TaskWorker",
    "clear_task_registry",
    "enqueue_operation_task",
    "enqueue_task",
    "ensure_cron_state_table",
    "ensure_tasks_table",
    "get_registered_task",
    "get_task_record",
    "task",
]
