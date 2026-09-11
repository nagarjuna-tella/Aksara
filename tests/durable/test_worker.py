"""Durable worker orchestration and lease maintenance."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from aksara.durable.errors import OwnershipLost
from aksara.durable.external import ExternalOperationExecutor
from aksara.durable.types import EffectClass, OperationClaim, PrincipalReference
from aksara.durable.worker import DurableOperationWorker


def _claim() -> OperationClaim:
    return OperationClaim(
        operation_id=uuid4(),
        attempt_id=uuid4(),
        tenant_id="tenant-1",
        tenant_scope="tenant-1",
        action_name="external.call",
        action_version="1",
        effect_class=EffectClass.EXTERNAL_IDEMPOTENT,
        worker_id="worker-1",
        fence=1,
        ordinal=1,
        lease_expires_at=datetime.now(UTC) + timedelta(seconds=1),
        command={},
        principal_reference=PrincipalReference(
            resolver_key="test",
            resolver_version="1",
            identity_namespace="tests",
            principal_kind="user",
            subject_id="user-1",
            tenant_id="tenant-1",
        ),
    )


@pytest.mark.asyncio
async def test_external_execution_renews_lease_until_completion(monkeypatch):
    heartbeats = 0

    async def heartbeat(_claim, *, lease_seconds):
        nonlocal heartbeats
        assert lease_seconds == 0.015
        heartbeats += 1

    async def execute(_executor, _claim):
        await asyncio.sleep(0.04)
        return "completed"

    service = SimpleNamespace(default_lease_seconds=0.015, heartbeat=heartbeat)
    worker = DurableOperationWorker(service, lease_seconds=0.015)
    monkeypatch.setattr(ExternalOperationExecutor, "execute", execute)

    assert await worker.execute_claim(_claim()) == "completed"
    assert heartbeats >= 2


@pytest.mark.asyncio
async def test_worker_repolls_after_normal_ownership_loss(monkeypatch):
    calls = 0
    service = SimpleNamespace(default_lease_seconds=1.0)
    worker = DurableOperationWorker(service, poll_interval=0.001)

    async def poll_once(*, tenant_id, operation_id=None):
        nonlocal calls
        assert tenant_id == "tenant-1"
        assert operation_id is None
        calls += 1
        if calls == 1:
            raise OwnershipLost("reclaimed")
        worker.stop()

    monkeypatch.setattr(worker, "poll_once", poll_once)

    await worker.run(tenant_id="tenant-1")
    assert calls == 2
