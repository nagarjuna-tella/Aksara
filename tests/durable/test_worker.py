"""Durable worker orchestration and lease maintenance."""

from __future__ import annotations

import asyncio
import logging
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
async def test_success_wins_when_renewal_finishes_at_the_same_time(monkeypatch):
    async def execute(_executor, _claim):
        return "completed"

    async def renewal(_claim, _execution):
        raise OwnershipLost("late renewal")

    async def wait_for_both(tasks, *, return_when):
        assert return_when is asyncio.FIRST_COMPLETED
        await asyncio.gather(*tasks, return_exceptions=True)
        return set(tasks), set()

    service = SimpleNamespace(default_lease_seconds=1.0)
    worker = DurableOperationWorker(service)
    monkeypatch.setattr(ExternalOperationExecutor, "execute", execute)
    monkeypatch.setattr(worker, "_renew_external_claim", renewal)
    monkeypatch.setattr(asyncio, "wait", wait_for_both)

    assert await worker.execute_claim(_claim()) == "completed"


@pytest.mark.asyncio
async def test_cancelling_execute_claim_cancels_external_child(monkeypatch):
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def execute(_executor, _claim):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    async def heartbeat(_claim, *, lease_seconds):
        del lease_seconds

    service = SimpleNamespace(default_lease_seconds=0.03, heartbeat=heartbeat)
    worker = DurableOperationWorker(service, lease_seconds=0.03)
    monkeypatch.setattr(ExternalOperationExecutor, "execute", execute)
    running = asyncio.create_task(worker.execute_claim(_claim()))
    await started.wait()

    running.cancel()
    with pytest.raises(asyncio.CancelledError):
        await running

    assert cancelled.is_set()


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


@pytest.mark.asyncio
async def test_worker_logs_and_retries_after_poll_failure(monkeypatch, caplog):
    calls = 0
    service = SimpleNamespace(default_lease_seconds=1.0)
    worker = DurableOperationWorker(service, poll_interval=0.001)

    async def poll_once(*, tenant_id, operation_id=None):
        nonlocal calls
        assert tenant_id == "tenant-1"
        assert operation_id is None
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary database failure")
        worker.stop()

    monkeypatch.setattr(worker, "poll_once", poll_once)

    with caplog.at_level(logging.ERROR, logger="aksara.durable.worker"):
        await worker.run(tenant_id="tenant-1")

    assert calls == 2
    assert "Durable operation worker poll failed; retrying" in caplog.text
