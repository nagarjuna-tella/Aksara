"""Narrow SQL repository for durable operation state-machine events."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

import asyncpg

from aksara.durable.states import AttemptState, OperationState
from aksara.durable.types import (
    AttemptRecord,
    EffectClass,
    OperationClaim,
    OperationRecord,
    OutboxRecord,
    PrincipalReference,
    TransitionRecord,
)


def _json(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _operation(record: Mapping[str, Any]) -> OperationRecord:
    return OperationRecord(
        id=record["id"],
        application_namespace=record["application_namespace"],
        tenant_id=record["tenant_id"],
        action_name=record["action_name"],
        action_version=record["action_version"],
        effect_class=EffectClass(record["effect_class"]),
        state=OperationState(record["state"]),
        state_version=int(record["state_version"]),
        attempt_count=int(record["attempt_count"]),
        max_attempts=int(record["max_attempts"]),
        available_at=record["available_at"],
        deadline_at=record["deadline_at"],
        cancellation_requested_at=record["cancellation_requested_at"],
        result=_json(record["result"]),
        error=_json(record["error"]),
        created_at=record["created_at"],
        updated_at=record["updated_at"],
        completed_at=record["completed_at"],
    )


class DurableOperationRepository:
    """Internal repository whose methods represent durable state events."""

    async def get_operation(
        self,
        connection: asyncpg.Connection,
        operation_id: UUID,
        tenant_scope: str,
        application_namespace: str,
        *,
        for_update: bool = False,
    ) -> asyncpg.Record | None:
        lock = " FOR UPDATE" if for_update else ""
        return await connection.fetchrow(
            f"""SELECT * FROM aksara_operations
            WHERE id = $1 AND tenant_scope = $2 AND application_namespace = $3{lock}""",
            operation_id,
            tenant_scope,
            application_namespace,
        )

    async def get_public_operation(
        self,
        connection: asyncpg.Connection,
        operation_id: UUID,
        tenant_scope: str,
        application_namespace: str,
    ) -> OperationRecord | None:
        row = await self.get_operation(
            connection, operation_id, tenant_scope, application_namespace
        )
        return _operation(row) if row is not None else None

    async def get_command(
        self,
        connection: asyncpg.Connection,
        operation_id: UUID,
        tenant_scope: str,
    ) -> dict[str, Any] | None:
        value = await connection.fetchval(
            """
            SELECT payload FROM aksara_operation_commands
            WHERE operation_id = $1 AND tenant_scope = $2
            """,
            operation_id,
            tenant_scope,
        )
        if value is None:
            return None
        payload = _json(value)
        return dict(payload)

    async def get_command_record(
        self,
        connection: asyncpg.Connection,
        operation_id: UUID,
        tenant_scope: str,
    ) -> asyncpg.Record | None:
        return await connection.fetchrow(
            """
            SELECT * FROM aksara_operation_commands
            WHERE operation_id = $1 AND tenant_scope = $2
            """,
            operation_id,
            tenant_scope,
        )

    async def insert_transition(
        self,
        connection: asyncpg.Connection,
        *,
        operation_id: UUID,
        tenant_scope: str,
        state_version: int,
        from_state: str | None,
        event: str,
        to_state: str,
        reason_code: str | None = None,
        actor_reference_hash: str | None = None,
        attempt_id: UUID | None = None,
        correlation: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> int:
        transition_id = await connection.fetchval(
            """
            INSERT INTO aksara_operation_transitions (
                operation_id, tenant_scope, state_version, from_state, event, to_state,
                reason_code, actor_reference_hash, attempt_id, correlation, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11::jsonb)
            RETURNING id
            """,
            operation_id,
            tenant_scope,
            state_version,
            from_state,
            event,
            to_state,
            reason_code,
            actor_reference_hash,
            attempt_id,
            json.dumps(dict(correlation or {})),
            json.dumps(dict(metadata or {})),
        )
        payload = {
            "operation_id": str(operation_id),
            "state_version": state_version,
            "from_state": from_state,
            "event": event,
            "to_state": to_state,
            "reason_code": reason_code,
            "attempt_id": str(attempt_id) if attempt_id else None,
        }
        await connection.execute(
            """
            INSERT INTO aksara_operation_outbox (
                operation_id, tenant_scope, transition_id, payload
            ) VALUES ($1, $2, $3, $4::jsonb)
            """,
            operation_id,
            tenant_scope,
            transition_id,
            json.dumps(payload),
        )
        return int(transition_id)

    async def history(
        self,
        connection: asyncpg.Connection,
        operation_id: UUID,
        tenant_scope: str,
        *,
        limit: int,
    ) -> list[TransitionRecord]:
        rows = await connection.fetch(
            """
            SELECT * FROM aksara_operation_transitions
            WHERE operation_id = $1 AND tenant_scope = $2
            ORDER BY id DESC LIMIT $3
            """,
            operation_id,
            tenant_scope,
            limit,
        )
        return [
            TransitionRecord(
                id=int(row["id"]),
                operation_id=row["operation_id"],
                state_version=int(row["state_version"]),
                from_state=(OperationState(row["from_state"]) if row["from_state"] else None),
                event=row["event"],
                to_state=OperationState(row["to_state"]),
                reason_code=row["reason_code"],
                attempt_id=row["attempt_id"],
                created_at=row["created_at"],
                metadata=dict(_json(row["metadata"])),
            )
            for row in rows
        ]

    async def attempts(
        self,
        connection: asyncpg.Connection,
        operation_id: UUID,
        tenant_scope: str,
    ) -> list[AttemptRecord]:
        rows = await connection.fetch(
            """
            SELECT * FROM aksara_operation_attempts
            WHERE operation_id = $1 AND tenant_scope = $2
            ORDER BY ordinal
            """,
            operation_id,
            tenant_scope,
        )
        return [
            AttemptRecord(
                id=row["id"],
                operation_id=row["operation_id"],
                ordinal=int(row["ordinal"]),
                fence=int(row["fence"]),
                worker_id=row["worker_id"],
                state=AttemptState(row["state"]),
                lease_expires_at=row["lease_expires_at"],
                started_at=row["started_at"],
                completed_at=row["completed_at"],
                retryable=row["retryable"],
                error_code=row["error_code"],
                error=_json(row["error"]),
                usage_summary=dict(_json(row["usage_summary"])),
            )
            for row in rows
        ]

    async def pending_outbox(
        self,
        connection: asyncpg.Connection,
        tenant_scope: str,
        application_namespace: str,
        *,
        limit: int,
    ) -> list[OutboxRecord]:
        rows = await connection.fetch(
            """
            SELECT o.* FROM aksara_operation_outbox o
            JOIN aksara_operations p ON p.id = o.operation_id
            WHERE o.tenant_scope = $1 AND p.application_namespace = $2
              AND o.exported_at IS NULL AND o.next_attempt_at <= clock_timestamp()
            ORDER BY o.id LIMIT $3
            """,
            tenant_scope,
            application_namespace,
            limit,
        )
        return [
            OutboxRecord(
                id=int(row["id"]),
                operation_id=row["operation_id"],
                transition_id=int(row["transition_id"]),
                topic=row["topic"],
                payload=dict(_json(row["payload"])),
                export_attempts=int(row["export_attempts"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def claim_row(
        self,
        connection: asyncpg.Connection,
        tenant_scope: str,
        application_namespace: str,
        *,
        operation_id: UUID | None = None,
    ) -> asyncpg.Record | None:
        return await connection.fetchrow(
            """
            SELECT * FROM aksara_operations
            WHERE tenant_scope = $1 AND application_namespace = $2
              AND ($3::uuid IS NULL OR id = $3)
              AND (
                  (state = 'ready' AND available_at <= clock_timestamp())
                  OR
                  (state = 'running' AND lease_expires_at <= clock_timestamp())
              )
            ORDER BY available_at, created_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """,
            tenant_scope,
            application_namespace,
            operation_id,
        )

    async def nonterminal_action_versions(
        self,
        connection: asyncpg.Connection,
        application_namespace: str,
    ) -> set[tuple[str, str]]:
        rows: Sequence[asyncpg.Record] = await connection.fetch(
            """
            SELECT DISTINCT action_name, action_version
            FROM aksara_operations
            WHERE application_namespace = $1
              AND state IN ('waiting_for_approval', 'ready', 'running')
            """,
            application_namespace,
        )
        return {(row["action_name"], row["action_version"]) for row in rows}

    @staticmethod
    def public_operation(record: Mapping[str, Any]) -> OperationRecord:
        return _operation(record)

    @staticmethod
    def claim(
        record: Mapping[str, Any],
        attempt: Mapping[str, Any],
        command: Mapping[str, Any],
    ) -> OperationClaim:
        reference = PrincipalReference(**dict(_json(record["principal_reference"])))
        return OperationClaim(
            operation_id=record["id"],
            attempt_id=attempt["id"],
            tenant_id=record["tenant_id"],
            tenant_scope=record["tenant_scope"],
            action_name=record["action_name"],
            action_version=record["action_version"],
            effect_class=EffectClass(record["effect_class"]),
            worker_id=attempt["worker_id"],
            fence=int(attempt["fence"]),
            ordinal=int(attempt["ordinal"]),
            lease_expires_at=attempt["lease_expires_at"],
            command=dict(command),
            principal_reference=reference,
        )


__all__ = ["DurableOperationRepository"]
