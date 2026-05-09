"""
Durable workflow state helpers.

Provides a small persistence primitive for long-running workflow steps that
should only execute once after succeeding.

Concurrency model
-----------------
DurableStep is designed for *sequential* orchestration: a single orchestrator
calls steps one after the other.  Concurrent execution of the same step is
detected and rejected via an atomic PostgreSQL INSERT … ON CONFLICT claim:

* Only one caller can transition a step into 'running' at a time.
* A second concurrent caller sees no RETURNING row and raises
  ConcurrentStepError rather than silently double-executing.
* If the concurrent holder completes before the loser re-reads, the loser
  transparently returns the cached result instead of raising.

Step re-entry rules (force=False, the default):
  - No row exists     → claim and execute
  - status='failed'   → re-claim and retry
  - status='running'  → raise ConcurrentStepError
  - status='completed'→ return cached result without any DB write

force=True bypasses all status checks and always re-executes.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from typing import Any, Callable, Optional
from uuid import UUID

from aksara.db import Database


DURABLE_STATE_TABLE = "aksara_durable_state"


class ConcurrentStepError(RuntimeError):
    """Raised when a workflow step is already being executed by another concurrent caller.

    DurableStep is designed for sequential orchestration. Calling the same step
    from multiple concurrent tasks is a usage error.
    """
_DURABLE_STATE_SCHEMA_SQL = f'''CREATE TABLE IF NOT EXISTS "{DURABLE_STATE_TABLE}" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    status VARCHAR(20) NOT NULL,
    result JSONB,
    error TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT uq_{DURABLE_STATE_TABLE} UNIQUE (workflow_id, step_name)
);'''


@dataclass
class DurableStepState:
    """Persisted state for a durable workflow step."""

    workflow_id: str
    step_name: str
    status: str
    result: Any = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


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
        "DurableStep results must be JSON-serializable or provide a custom serializer"
    )


class DurableStep:
    """Persist workflow step results so successful work is not repeated."""

    def __init__(
        self,
        workflow_id: str,
        *,
        db: Optional[Database] = None,
        serializer: Optional[Callable[[Any], Any]] = None,
        deserializer: Optional[Callable[[Any], Any]] = None,
    ):
        self.workflow_id = workflow_id
        self._db = db
        self._serializer = serializer or _default_serializer
        self._deserializer = deserializer or (lambda value: value)

    def _get_db(self) -> Database:
        if self._db is not None:
            return self._db
        return Database.get_instance()

    def _encode_result(self, value: Any) -> Any:
        return json.loads(json.dumps(value, default=self._serializer))

    def _decode_result(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                pass
        return self._deserializer(value)

    async def ensure_table(self) -> None:
        """Create the durable state table when needed."""
        await self._get_db().execute(_DURABLE_STATE_SCHEMA_SQL)

    async def get_state(self, step_name: str) -> Optional[DurableStepState]:
        """Load persisted state for a workflow step."""
        await self.ensure_table()
        record = await self._get_db().fetchrow(
            f'''
            SELECT workflow_id, step_name, status, result, error, created_at, updated_at, completed_at
            FROM "{DURABLE_STATE_TABLE}"
            WHERE workflow_id = $1 AND step_name = $2
            ''',
            self.workflow_id,
            step_name,
        )
        if record is None:
            return None

        return DurableStepState(
            workflow_id=record["workflow_id"],
            step_name=record["step_name"],
            status=record["status"],
            result=self._decode_result(record["result"]),
            error=record["error"],
            created_at=record["created_at"],
            updated_at=record["updated_at"],
            completed_at=record["completed_at"],
        )

    async def run(
        self,
        step_name: str,
        func: Callable[..., Any],
        *args: Any,
        force: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Run a step once and reuse its persisted result on later calls.

        The step claim is atomic: only one concurrent caller can own execution
        at a time. A second concurrent caller targeting the same running step
        raises ConcurrentStepError rather than double-executing.
        """
        await self.ensure_table()
        db = self._get_db()

        # Fast path: return cached result without acquiring any lock.
        if not force:
            state = await self.get_state(step_name)
            if state is not None and state.status == "completed":
                return state.result

        # Atomically claim the step for execution.
        # force=True  → always overwrite, even if already 'completed' or 'running'.
        # force=False → only claim when no row exists yet, or the previous run failed.
        #               A row in 'running' or 'completed' state blocks the claim.
        if force:
            claimed = await db.fetchrow(
                f'''
                INSERT INTO "{DURABLE_STATE_TABLE}" (workflow_id, step_name, status, error, completed_at)
                VALUES ($1, $2, 'running', NULL, NULL)
                ON CONFLICT (workflow_id, step_name) DO UPDATE
                  SET
                    status = 'running',
                    error = NULL,
                    completed_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING workflow_id
                ''',
                self.workflow_id,
                step_name,
            )
        else:
            claimed = await db.fetchrow(
                f'''
                INSERT INTO "{DURABLE_STATE_TABLE}" (workflow_id, step_name, status, error, completed_at)
                VALUES ($1, $2, 'running', NULL, NULL)
                ON CONFLICT (workflow_id, step_name) DO UPDATE
                  SET
                    status = 'running',
                    error = NULL,
                    completed_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                  WHERE "{DURABLE_STATE_TABLE}".status = 'failed'
                RETURNING workflow_id
                ''',
                self.workflow_id,
                step_name,
            )

        if not claimed:
            # Another concurrent caller holds this step. Re-read to find out why.
            state = await self.get_state(step_name)
            if state is not None and state.status == "completed":
                return state.result
            raise ConcurrentStepError(
                f"Step '{step_name}' of workflow '{self.workflow_id}' is already running "
                "concurrently. DurableStep is designed for sequential workflows — "
                "do not call the same step from multiple concurrent tasks."
            )

        try:
            result = func(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result

            encoded_result = self._encode_result(result)
            record = await db.fetchrow(
                f'''
                INSERT INTO "{DURABLE_STATE_TABLE}" (workflow_id, step_name, status, result, error, completed_at)
                VALUES ($1, $2, 'completed', $3, NULL, CURRENT_TIMESTAMP)
                ON CONFLICT (workflow_id, step_name) DO UPDATE
                  SET
                    status = EXCLUDED.status,
                    result = EXCLUDED.result,
                    error = NULL,
                    completed_at = EXCLUDED.completed_at,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING result
                ''',
                self.workflow_id,
                step_name,
                json.dumps(encoded_result),
            )
            return self._decode_result(record["result"] if record is not None else encoded_result)
        except Exception as exc:
            await db.fetchrow(
                f'''
                INSERT INTO "{DURABLE_STATE_TABLE}" (workflow_id, step_name, status, error, completed_at)
                VALUES ($1, $2, 'failed', $3, NULL)
                ON CONFLICT (workflow_id, step_name) DO UPDATE
                  SET
                    status = EXCLUDED.status,
                    error = EXCLUDED.error,
                    completed_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING workflow_id
                ''',
                self.workflow_id,
                step_name,
                str(exc),
            )
            raise

    async def clear(self, step_name: Optional[str] = None) -> None:
        """Delete persisted state for one step or the whole workflow."""
        await self.ensure_table()
        db = self._get_db()
        if step_name is None:
            await db.execute(
                f'DELETE FROM "{DURABLE_STATE_TABLE}" WHERE workflow_id = $1',
                self.workflow_id,
            )
            return

        await db.execute(
            f'DELETE FROM "{DURABLE_STATE_TABLE}" WHERE workflow_id = $1 AND step_name = $2',
            self.workflow_id,
            step_name,
        )


__all__ = [
    "DURABLE_STATE_TABLE",
    "ConcurrentStepError",
    "DurableStep",
    "DurableStepState",
]