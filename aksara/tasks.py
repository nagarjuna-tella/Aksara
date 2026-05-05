"""
Built-in background task queue.

Provides a lightweight database-backed task registry, enqueue helpers,
and an application-owned worker loop.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from functools import update_wrapper
from typing import Any, Callable, Literal, Optional
from uuid import UUID

from aksara.db import Database
from aksara.logging import logger


TaskStatus = Literal["pending", "running", "completed", "failed"]

TASKS_TABLE = "aksara_tasks"
TASKS_TABLE_SQL = f'''CREATE TABLE IF NOT EXISTS "{TASKS_TABLE}" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_name VARCHAR(255) NOT NULL,
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
    f'ON "{TASKS_TABLE}" (status, available_at, created_at)'
)

_TASK_REGISTRY: dict[str, "RegisteredTask"] = {}


@dataclass
class TaskRecord:
    """Persisted background task state."""

    id: UUID
    task_name: str
    payload: dict[str, Any]
    status: TaskStatus
    attempts: int
    max_attempts: int
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
        return asdict(value)
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
    ):
        update_wrapper(self, func)
        self.func = func
        self.name = name or f"{func.__module__}.{func.__qualname__}"
        self.max_attempts = max_attempts

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.func(*args, **kwargs)

    async def enqueue(
        self,
        *args: Any,
        db: Optional[Database] = None,
        delay_seconds: float = 0.0,
        max_attempts: Optional[int] = None,
        **kwargs: Any,
    ) -> TaskRecord:
        """Enqueue the task for background execution."""
        return await enqueue_task(
            self,
            *args,
            db=db,
            delay_seconds=delay_seconds,
            max_attempts=max_attempts,
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
) -> RegisteredTask | Callable[[Callable[..., Any]], RegisteredTask]:
    """Register a function as a durable background task."""

    def decorator(target: Callable[..., Any]) -> RegisteredTask:
        registered = RegisteredTask(target, name=name, max_attempts=max_attempts)
        _TASK_REGISTRY[registered.name] = registered
        return registered

    if func is None:
        return decorator
    return decorator(func)


async def ensure_tasks_table(db: Optional[Database] = None) -> None:
    """Create the internal task table when needed."""
    database = _get_db(db)
    await database.execute(TASKS_TABLE_SQL)
    await database.execute(TASKS_INDEX_SQL)


def _resolve_task_definition(task_ref: str | RegisteredTask) -> RegisteredTask:
    """Resolve a task name or wrapper into a registered task definition."""
    if isinstance(task_ref, RegisteredTask):
        return task_ref
    return get_registered_task(task_ref)


async def enqueue_task(
    task_ref: str | RegisteredTask,
    *args: Any,
    db: Optional[Database] = None,
    delay_seconds: float = 0.0,
    max_attempts: Optional[int] = None,
    **kwargs: Any,
) -> TaskRecord:
    """Persist a task invocation for background execution."""
    from aksara.conf import settings

    database = _get_db(db)
    await ensure_tasks_table(database)

    task_definition = _resolve_task_definition(task_ref)
    effective_max_attempts = max_attempts or task_definition.max_attempts or settings.task_max_attempts
    payload = _encode_json_value({"args": list(args), "kwargs": kwargs})

    record = await database.fetchrow(
        f'''
        INSERT INTO "{TASKS_TABLE}" (task_name, payload, max_attempts, available_at)
        VALUES (
            $1,
            $2,
            $3,
            CURRENT_TIMESTAMP + ($4::double precision * INTERVAL '1 second')
        )
        RETURNING *
        ''',
        task_definition.name,
        json.dumps(payload),
        effective_max_attempts,
        delay_seconds,
    )
    if record is None:
        raise RuntimeError(f"Failed to enqueue task '{task_definition.name}'")
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
    """Simple polling worker that executes tasks from the database queue."""

    def __init__(
        self,
        db: Optional[Database] = None,
        *,
        poll_interval: Optional[float] = None,
        retry_delay_seconds: Optional[float] = None,
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
        """Stop the background polling loop."""
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

        record = await database.fetchrow(
            f'''
            WITH next_task AS (
                SELECT id
                FROM "{TASKS_TABLE}"
                WHERE status = 'pending' AND available_at <= CURRENT_TIMESTAMP
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

        task_record = TaskRecord.from_record(record)
        await self._process_task(task_record)
        refreshed = await get_task_record(task_record.id, db=database)
        return refreshed or task_record

    async def _run_loop(self) -> None:
        """Continuously poll for work until asked to stop."""
        while not self._stop_event.is_set():
            try:
                processed = await self.poll_once()
            except Exception:
                logger.exception("Task worker poll failed")
                processed = None

            if processed is not None:
                continue

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval)
            except asyncio.TimeoutError:
                continue

    async def _process_task(self, task_record: TaskRecord) -> None:
        """Execute a claimed task and persist the outcome."""
        database = _get_db(self._db)

        try:
            task_definition = get_registered_task(task_record.task_name)
            result = await self._execute_callable(task_definition, task_record.payload)
        except Exception as exc:
            logger.exception("Task '%s' failed", task_record.task_name)
            await self._mark_failure(task_record, str(exc), db=database)
            return

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
        """Persist a failed attempt and optionally reschedule it."""
        database = _get_db(db)
        should_retry = task_record.attempts < task_record.max_attempts

        if should_retry:
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
                self.retry_delay_seconds,
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
    "TASKS_TABLE",
    "TaskRecord",
    "TaskWorker",
    "clear_task_registry",
    "enqueue_task",
    "ensure_tasks_table",
    "get_registered_task",
    "get_task_record",
    "task",
]