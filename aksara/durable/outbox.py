"""At-least-once export for durable transition outbox records."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping
from typing import Any
from uuid import uuid4

from aksara.db import atomic
from aksara.durable.service import DurableOperationService, _tenant_context
from aksara.durable.types import tenant_scope

TransitionSink = Callable[[Mapping[str, Any]], None | Awaitable[None]]


class DurableOutboxExporter:
    """Claim and export transition records without making the sink authoritative."""

    def __init__(
        self,
        service: DurableOperationService,
        sink: TransitionSink,
        *,
        worker_id: str | None = None,
        claim_seconds: float = 30.0,
        retry_seconds: float = 5.0,
    ) -> None:
        if claim_seconds <= 0 or retry_seconds < 0:
            raise ValueError("outbox claim must be positive and retry cannot be negative")
        self.service = service
        self.sink = sink
        self.worker_id = worker_id or f"outbox-{uuid4()}"
        self.claim_seconds = claim_seconds
        self.retry_seconds = retry_seconds

    async def export_once(self, *, tenant_id: str | None) -> bool:
        scope = tenant_scope(tenant_id)
        with _tenant_context(scope):
            async with atomic(db=self.service.db) as connection:
                record = await connection.fetchrow(
                    """
                    WITH candidate AS (
                        SELECT o.id FROM aksara_operation_outbox o
                        JOIN aksara_operations p ON p.id = o.operation_id
                        WHERE o.tenant_scope = $1
                          AND p.application_namespace = $2
                          AND o.exported_at IS NULL
                          AND o.next_attempt_at <= clock_timestamp()
                          AND (o.claim_expires_at IS NULL
                               OR o.claim_expires_at <= clock_timestamp())
                        ORDER BY o.id
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    UPDATE aksara_operation_outbox o
                    SET claimed_by = $3,
                        claim_expires_at = clock_timestamp()
                            + ($4::double precision * INTERVAL '1 second'),
                        export_attempts = export_attempts + 1
                    FROM candidate
                    WHERE o.id = candidate.id
                    RETURNING o.*
                    """,
                    scope,
                    self.service.application_namespace,
                    self.worker_id,
                    self.claim_seconds,
                )
        if record is None:
            return False

        payload = record["payload"]
        if isinstance(payload, str):
            import json

            payload = json.loads(payload)
        try:
            result = self.sink(dict(payload))
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            with _tenant_context(scope):
                async with atomic(db=self.service.db) as connection:
                    await connection.execute(
                        """
                        UPDATE aksara_operation_outbox
                        SET claimed_by = NULL, claim_expires_at = NULL,
                            last_error = $4,
                            next_attempt_at = clock_timestamp()
                                + ($5::double precision * INTERVAL '1 second')
                        WHERE id = $1 AND tenant_scope = $2 AND claimed_by = $3
                          AND exported_at IS NULL
                        """,
                        record["id"],
                        scope,
                        self.worker_id,
                        (str(exc) or type(exc).__name__)[:2000],
                        self.retry_seconds,
                    )
            return False

        with _tenant_context(scope):
            async with atomic(db=self.service.db) as connection:
                status = await connection.execute(
                    """
                    UPDATE aksara_operation_outbox
                    SET exported_at = clock_timestamp(), claimed_by = NULL,
                        claim_expires_at = NULL, last_error = NULL
                    WHERE id = $1 AND tenant_scope = $2 AND claimed_by = $3
                      AND exported_at IS NULL
                    """,
                    record["id"],
                    scope,
                    self.worker_id,
                )
        return status == "UPDATE 1"


__all__ = ["DurableOutboxExporter", "TransitionSink"]
