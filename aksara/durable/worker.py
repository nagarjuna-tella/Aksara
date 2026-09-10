"""Small PostgreSQL-first worker for durable operations."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from aksara.durable.execution import PostgresAtomicExecutor, ReadOnlyExecutor
from aksara.durable.external import ExternalOperationExecutor
from aksara.durable.service import DurableOperationService
from aksara.durable.types import EffectClass, OperationClaim, OperationRecord


class DurableOperationWorker:
    """Claim and execute durable work for one explicitly selected tenant."""

    def __init__(
        self,
        service: DurableOperationService,
        *,
        worker_id: str | None = None,
        lease_seconds: float | None = None,
        poll_interval: float = 1.0,
    ) -> None:
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        self.service = service
        self.worker_id = worker_id or f"operation-worker-{uuid4()}"
        self.lease_seconds = lease_seconds
        self.poll_interval = poll_interval
        self._stop = asyncio.Event()

    async def poll_once(
        self,
        *,
        tenant_id: str | None,
        operation_id: UUID | None = None,
    ) -> OperationRecord | None:
        claim = await self.service.claim(
            tenant_id=tenant_id,
            worker_id=self.worker_id,
            operation_id=operation_id,
            lease_seconds=self.lease_seconds,
        )
        if claim is None:
            return None
        return await self.execute_claim(claim)

    async def execute_claim(self, claim: OperationClaim) -> OperationRecord:
        if claim.effect_class is EffectClass.POSTGRES_ATOMIC:
            return await PostgresAtomicExecutor(self.service).execute(claim)
        if claim.effect_class is EffectClass.READ_ONLY:
            return await ReadOnlyExecutor(self.service).execute(claim)
        return await ExternalOperationExecutor(self.service).execute(claim)

    async def run(self, *, tenant_id: str | None) -> None:
        self._stop.clear()
        while not self._stop.is_set():
            operation = await self.poll_once(tenant_id=tenant_id)
            if operation is not None:
                continue
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.poll_interval)
            except TimeoutError:
                pass

    def stop(self) -> None:
        self._stop.set()


__all__ = ["DurableOperationWorker"]
