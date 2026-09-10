"""Executable, test-only specification for ADR 0001's two core invariants.

The disposable tables below intentionally are not Aksara's future durable
operation schema.  They exist only to prove transaction pinning, atomic
completion, database-time leasing, and fencing against a real PostgreSQL
server.  No symbol in this module is imported by the framework package.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import sys
import time
from collections.abc import AsyncIterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio

from aksara import TenantModel, fields
from aksara.context_state import tenant_id_var
from aksara.db import Database, atomic
from aksara.db.expressions import F
from aksara.db.session import get_session
from aksara.db.tenant_context import build_enable_rls_sql

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"), reason="DATABASE_URL is required"
)

OPERATIONS = "aksara_v070_proto_operations"
ATTEMPTS = "aksara_v070_proto_attempts"
COUNTERS = "aksara_v070_proto_counters"
TRIGGER_FUNCTION = "aksara_v070_record_backend_pid"
EVIDENCE_DIR_ENV = "AKSARA_V070_EVIDENCE_DIR"


class PrototypeCounter(TenantModel):
    """A tenant-scoped application row whose duplicate mutation is obvious."""

    mutation_counter = fields.Integer(default=0)
    label = fields.String(max_length=80, default="prototype")
    last_backend_pid = fields.Integer(nullable=True)

    class Meta:
        table_name = COUNTERS


@dataclass(frozen=True)
class Claim:
    operation_id: UUID
    attempt_id: UUID
    tenant_id: UUID
    worker_id: str
    fence: int
    lease_expires_at: datetime
    backend_pid: int


@dataclass
class Lab:
    admin_url: str
    role_dsn: str
    role: str
    db: Database
    admin: asyncpg.Connection


class InjectedFailure(RuntimeError):
    pass


class CommitAcknowledgementLost(ConnectionError):
    """Client-side simulation raised only after PostgreSQL has committed."""


def _role_dsn(database_url: str, role: str, password: str) -> str:
    parsed = urlsplit(database_url)
    host = parsed.hostname or "localhost"
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{quote(role)}:{quote(password)}@{host}{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


@contextmanager
def _tenant_scope(tenant_id: UUID | None):
    token = tenant_id_var.set(str(tenant_id) if tenant_id is not None else None)
    try:
        yield
    finally:
        tenant_id_var.reset(token)


def _jsonable(value: Any) -> Any:
    if isinstance(value, (UUID, datetime)):
        return str(value)
    if isinstance(value, asyncpg.Record):
        return {key: _jsonable(item) for key, item in dict(value).items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _record(filename: str, scenario: str, result: dict[str, Any]) -> None:
    """Write opt-in structured evidence without ever recording a DSN."""
    configured = os.getenv(EVIDENCE_DIR_ENV)
    if not configured:
        return
    directory = Path(configured)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    payload: dict[str, Any] = {"schema_version": 1, "scenarios": {}}
    if path.exists():
        payload = json.loads(path.read_text())
    payload["scenarios"][scenario] = _jsonable(result)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def _count(status: str) -> int:
    return int(status.rsplit(" ", 1)[-1])


async def _role_connection(lab: Lab, tenant_id: UUID) -> asyncpg.Connection:
    connection = await asyncpg.connect(lab.role_dsn)
    await connection.execute(
        "SELECT set_config('aksara.current_tenant_id', $1, false)", str(tenant_id)
    )
    return connection


@pytest_asyncio.fixture
async def lab() -> AsyncIterator[Lab]:
    admin_url = os.environ["DATABASE_URL"]
    suffix = uuid4().hex[:10]
    role = f"aksara_v070_{suffix}"
    password = secrets.token_urlsafe(24)
    role_url = _role_dsn(admin_url, role, password)
    admin = await asyncpg.connect(admin_url)
    previous_database = Database._instance
    application_db: Database | None = None
    previous_process_dsn = os.environ.get("AKSARA_V070_ROLE_DSN")
    try:
        escaped_password = password.replace("'", "''")
        await admin.execute(
            f'''CREATE ROLE "{role}" LOGIN PASSWORD '{escaped_password}' '''
            "NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION"
        )
        await admin.execute(
            f'''
            CREATE TABLE "{OPERATIONS}" (
                id UUID PRIMARY KEY,
                tenant_id UUID NOT NULL,
                state TEXT NOT NULL CHECK (state IN ('ready','running','succeeded','failed','cancelled')),
                current_attempt UUID,
                fence BIGINT NOT NULL DEFAULT 0,
                worker_id TEXT,
                lease_expires_at TIMESTAMPTZ,
                progress INTEGER NOT NULL DEFAULT 0,
                completion_backend_pid INTEGER,
                created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
            );
            CREATE TABLE "{ATTEMPTS}" (
                id UUID PRIMARY KEY,
                operation_id UUID NOT NULL REFERENCES "{OPERATIONS}"(id) ON DELETE CASCADE,
                tenant_id UUID NOT NULL,
                fence BIGINT NOT NULL,
                worker_id TEXT NOT NULL,
                state TEXT NOT NULL CHECK (state IN ('running','succeeded','failed','cancelled','abandoned')),
                lease_expires_at TIMESTAMPTZ NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                backend_pid INTEGER NOT NULL,
                completion_backend_pid INTEGER,
                started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
                completed_at TIMESTAMPTZ,
                UNIQUE (operation_id, fence)
            );
            CREATE TABLE "{COUNTERS}" (
                id UUID PRIMARY KEY,
                tenant_id UUID NOT NULL,
                mutation_counter INTEGER NOT NULL DEFAULT 0 CHECK (mutation_counter >= 0),
                label VARCHAR(80) NOT NULL DEFAULT 'prototype',
                last_backend_pid INTEGER,
                created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
            );
            CREATE FUNCTION "{TRIGGER_FUNCTION}"() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                NEW.last_backend_pid = pg_backend_pid();
                RETURN NEW;
            END
            $$;
            CREATE TRIGGER aksara_v070_counter_pid
            BEFORE INSERT OR UPDATE ON "{COUNTERS}"
            FOR EACH ROW EXECUTE FUNCTION "{TRIGGER_FUNCTION}"()
            '''
        )
        for table in (OPERATIONS, ATTEMPTS, COUNTERS):
            await admin.execute(build_enable_rls_sql(table))
            await admin.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
            await admin.execute(
                f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "{table}" TO "{role}"'
            )

        application_db = Database(role_url, min_size=1, max_size=4)
        await application_db.connect()
        os.environ["AKSARA_V070_ROLE_DSN"] = role_url
        yield Lab(admin_url, role_url, role, application_db, admin)
    finally:
        Database._instance = previous_database
        if application_db is not None:
            await application_db.disconnect()
        if previous_process_dsn is None:
            os.environ.pop("AKSARA_V070_ROLE_DSN", None)
        else:
            os.environ["AKSARA_V070_ROLE_DSN"] = previous_process_dsn
        for table in (ATTEMPTS, COUNTERS, OPERATIONS):
            await admin.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
        await admin.execute(f'DROP FUNCTION IF EXISTS "{TRIGGER_FUNCTION}"() CASCADE')
        await admin.execute(f'DROP ROLE IF EXISTS "{role}"')
        await admin.close()


async def _new_scenario(
    lab: Lab, *, tenant_id: UUID | None = None
) -> tuple[UUID, UUID, UUID]:
    tenant = tenant_id or uuid4()
    operation_id, counter_id = uuid4(), uuid4()
    with _tenant_scope(tenant):
        await lab.db.execute(
            f'''
            INSERT INTO "{OPERATIONS}" (id, tenant_id, state)
            VALUES ($1, $2, 'ready')
            ''',
            operation_id,
            tenant,
        )
        await lab.db.execute(
            f'''
            INSERT INTO "{COUNTERS}" (id, tenant_id, mutation_counter, label)
            VALUES ($1, $2, 0, 'prototype')
            ''',
            counter_id,
            tenant,
        )
    return tenant, operation_id, counter_id


async def _snapshot(
    lab: Lab, tenant_id: UUID, operation_id: UUID, counter_id: UUID
) -> dict[str, Any]:
    connection = await _role_connection(lab, tenant_id)
    try:
        operation = await connection.fetchrow(
            f'SELECT * FROM "{OPERATIONS}" WHERE id = $1', operation_id
        )
        attempts = await connection.fetch(
            f'SELECT * FROM "{ATTEMPTS}" WHERE operation_id = $1 ORDER BY fence',
            operation_id,
        )
        counter = await connection.fetchrow(
            f'SELECT * FROM "{COUNTERS}" WHERE id = $1', counter_id
        )
        return {
            "operation": dict(operation) if operation else None,
            "attempts": [dict(row) for row in attempts],
            "counter": dict(counter) if counter else None,
        }
    finally:
        await connection.close()


async def _claim_on_connection(
    connection: asyncpg.Connection,
    operation_id: UUID,
    tenant_id: UUID,
    worker_id: str,
    *,
    lease_seconds: float = 2.0,
    increment_fence: bool = True,
) -> Claim | None:
    async with connection.transaction():
        row = await connection.fetchrow(
            f'''
            SELECT *, lease_expires_at <= clock_timestamp() AS lease_expired
            FROM "{OPERATIONS}"
            WHERE id = $1 AND tenant_id = $2
            FOR UPDATE
            ''',
            operation_id,
            tenant_id,
        )
        if row is None or row["state"] == "succeeded":
            return None
        if row["state"] == "running" and not row["lease_expired"]:
            return None
        if row["state"] not in {"ready", "running"}:
            return None

        if row["state"] == "running" and row["current_attempt"]:
            await connection.execute(
                f'''
                UPDATE "{ATTEMPTS}"
                SET state = 'abandoned', completed_at = clock_timestamp()
                WHERE id = $1 AND operation_id = $2 AND fence = $3
                  AND state = 'running'
                ''',
                row["current_attempt"],
                operation_id,
                row["fence"],
            )

        fence = int(row["fence"]) + (1 if increment_fence else 0)
        attempt_id = uuid4()
        inserted = await connection.fetchrow(
            f'''
            INSERT INTO "{ATTEMPTS}" (
                id, operation_id, tenant_id, fence, worker_id, state,
                lease_expires_at, backend_pid
            ) VALUES (
                $1, $2, $3, $4, $5, 'running',
                clock_timestamp() + ($6::double precision * INTERVAL '1 second'),
                pg_backend_pid()
            ) RETURNING lease_expires_at, backend_pid
            ''',
            attempt_id,
            operation_id,
            tenant_id,
            fence,
            worker_id,
            lease_seconds,
        )
        await connection.execute(
            f'''
            UPDATE "{OPERATIONS}"
            SET state = 'running', current_attempt = $2, fence = $3,
                worker_id = $4, lease_expires_at = $5,
                updated_at = clock_timestamp()
            WHERE id = $1 AND tenant_id = $6
            ''',
            operation_id,
            attempt_id,
            fence,
            worker_id,
            inserted["lease_expires_at"],
            tenant_id,
        )
        return Claim(
            operation_id,
            attempt_id,
            tenant_id,
            worker_id,
            fence,
            inserted["lease_expires_at"],
            inserted["backend_pid"],
        )


async def _claim(
    lab: Lab,
    operation_id: UUID,
    tenant_id: UUID,
    worker_id: str,
    *,
    lease_seconds: float = 2.0,
    increment_fence: bool = True,
) -> Claim | None:
    connection = await _role_connection(lab, tenant_id)
    try:
        return await _claim_on_connection(
            connection,
            operation_id,
            tenant_id,
            worker_id,
            lease_seconds=lease_seconds,
            increment_fence=increment_fence,
        )
    finally:
        await connection.close()


async def _atomic_complete(
    lab: Lab,
    claim: Claim,
    counter_id: UUID,
    *,
    inject: str | None = None,
    cancellation: bool = False,
    locked: asyncio.Event | None = None,
    release: asyncio.Event | None = None,
) -> dict[str, int]:
    def fail(stage: str) -> None:
        if inject == stage:
            if cancellation:
                raise asyncio.CancelledError(stage)
            raise InjectedFailure(stage)

    fail("before_begin")
    pids: dict[str, int] = {}
    with _tenant_scope(claim.tenant_id):
        async with atomic(db=lab.db) as connection:
            pids["lock"] = await connection.fetchval("SELECT pg_backend_pid()")
            row = await connection.fetchrow(
                f'''
                SELECT state, current_attempt, fence, worker_id,
                       lease_expires_at > clock_timestamp() AS lease_valid
                FROM "{OPERATIONS}"
                WHERE id = $1 AND tenant_id = $2
                FOR UPDATE
                ''',
                claim.operation_id,
                claim.tenant_id,
            )
            owns = bool(
                row
                and row["state"] == "running"
                and row["current_attempt"] == claim.attempt_id
                and row["fence"] == claim.fence
                and row["worker_id"] == claim.worker_id
                and row["lease_valid"]
            )
            if not owns:
                raise PermissionError("operation ownership lost")
            if locked is not None:
                locked.set()
            if release is not None:
                await release.wait()
            fail("after_lock")

            if inject == "during_database_mutation":
                await lab.db.execute(
                    f'UPDATE "{COUNTERS}" SET mutation_counter = -1 WHERE id = $1',
                    counter_id,
                )
            counter = await PrototypeCounter.objects.get(id=counter_id)
            pids["orm_read"] = await lab.db.fetchval("SELECT pg_backend_pid()")
            counter.mutation_counter += 1
            await counter.save()
            pids["model_save"] = await lab.db.fetchval("SELECT pg_backend_pid()")
            fail("after_mutation")

            updated_attempt = _count(
                await lab.db.execute(
                    f'''
                    UPDATE "{ATTEMPTS}"
                    SET state = 'succeeded', completed_at = clock_timestamp(),
                        completion_backend_pid = pg_backend_pid()
                    WHERE id = $1 AND operation_id = $2 AND tenant_id = $3
                      AND fence = $4 AND worker_id = $5 AND state = 'running'
                    ''',
                    claim.attempt_id,
                    claim.operation_id,
                    claim.tenant_id,
                    claim.fence,
                    claim.worker_id,
                )
            )
            assert updated_attempt == 1
            pids["attempt_success"] = await lab.db.fetchval("SELECT pg_backend_pid()")
            fail("after_attempt")

            updated_operation = _count(
                await lab.db.execute(
                    f'''
                    UPDATE "{OPERATIONS}"
                    SET state = 'succeeded', completion_backend_pid = pg_backend_pid(),
                        lease_expires_at = NULL, updated_at = clock_timestamp()
                    WHERE id = $1 AND tenant_id = $2 AND state = 'running'
                      AND current_attempt = $3 AND fence = $4 AND worker_id = $5
                    ''',
                    claim.operation_id,
                    claim.tenant_id,
                    claim.attempt_id,
                    claim.fence,
                    claim.worker_id,
                )
            )
            assert updated_operation == 1
            pids["operation_success"] = await lab.db.fetchval("SELECT pg_backend_pid()")
            fail("after_operation")
    return pids


async def _heartbeat(lab: Lab, claim: Claim, lease_seconds: float = 2.0) -> int:
    connection = await _role_connection(lab, claim.tenant_id)
    try:
        async with connection.transaction():
            attempt_count = _count(
                await connection.execute(
                    f'''
                    UPDATE "{ATTEMPTS}" a
                    SET lease_expires_at = clock_timestamp()
                        + ($6::double precision * INTERVAL '1 second')
                    FROM "{OPERATIONS}" o
                    WHERE a.id = $1 AND a.operation_id = $2 AND a.tenant_id = $3
                      AND a.fence = $4 AND a.worker_id = $5 AND a.state = 'running'
                      AND o.id = a.operation_id AND o.current_attempt = a.id
                      AND o.fence = a.fence AND o.worker_id = a.worker_id
                      AND o.state = 'running'
                    ''',
                    claim.attempt_id,
                    claim.operation_id,
                    claim.tenant_id,
                    claim.fence,
                    claim.worker_id,
                    lease_seconds,
                )
            )
            if attempt_count != 1:
                return 0
            return _count(
                await connection.execute(
                    f'''
                    UPDATE "{OPERATIONS}"
                    SET lease_expires_at = clock_timestamp()
                        + ($6::double precision * INTERVAL '1 second'),
                        updated_at = clock_timestamp()
                    WHERE id = $1 AND tenant_id = $2 AND current_attempt = $3
                      AND fence = $4 AND worker_id = $5 AND state = 'running'
                    ''',
                    claim.operation_id,
                    claim.tenant_id,
                    claim.attempt_id,
                    claim.fence,
                    claim.worker_id,
                    lease_seconds,
                )
            )
    finally:
        await connection.close()


async def _progress(lab: Lab, claim: Claim, value: int) -> int:
    connection = await _role_connection(lab, claim.tenant_id)
    try:
        async with connection.transaction():
            attempt_count = _count(
                await connection.execute(
                    f'''
                    UPDATE "{ATTEMPTS}" a SET progress = $6
                    FROM "{OPERATIONS}" o
                    WHERE a.id = $1 AND a.operation_id = $2 AND a.tenant_id = $3
                      AND a.fence = $4 AND a.worker_id = $5 AND a.state = 'running'
                      AND o.id = a.operation_id AND o.current_attempt = a.id
                      AND o.fence = a.fence AND o.worker_id = a.worker_id
                      AND o.state = 'running'
                    ''',
                    claim.attempt_id,
                    claim.operation_id,
                    claim.tenant_id,
                    claim.fence,
                    claim.worker_id,
                    value,
                )
            )
            if attempt_count != 1:
                return 0
            return _count(
                await connection.execute(
                    f'''
                    UPDATE "{OPERATIONS}" SET progress = $6,
                        updated_at = clock_timestamp()
                    WHERE id = $1 AND tenant_id = $2 AND current_attempt = $3
                      AND fence = $4 AND worker_id = $5 AND state = 'running'
                    ''',
                    claim.operation_id,
                    claim.tenant_id,
                    claim.attempt_id,
                    claim.fence,
                    claim.worker_id,
                    value,
                )
            )
    finally:
        await connection.close()


async def _stale_authoritative_write(lab: Lab, claim: Claim, state: str) -> int:
    connection = await _role_connection(lab, claim.tenant_id)
    try:
        return _count(
            await connection.execute(
                f'''
                UPDATE "{OPERATIONS}" SET state = $6, updated_at = clock_timestamp()
                WHERE id = $1 AND tenant_id = $2 AND current_attempt = $3
                  AND fence = $4 AND worker_id = $5 AND state = 'running'
                ''',
                claim.operation_id,
                claim.tenant_id,
                claim.attempt_id,
                claim.fence,
                claim.worker_id,
                state,
            )
        )
    finally:
        await connection.close()


def _assert_rolled_back(snapshot: dict[str, Any]) -> None:
    assert snapshot["counter"]["mutation_counter"] == 0
    assert snapshot["operation"]["state"] == "running"
    assert snapshot["attempts"][-1]["state"] == "running"


async def test_real_connection_pinning_nested_savepoint_and_orm_paths(lab: Lab):
    tenant, operation_id, counter_id = await _new_scenario(lab)
    claim = await _claim(lab, operation_id, tenant, "worker-normal")
    assert claim is not None
    with _tenant_scope(tenant):
        async with atomic(db=lab.db) as outer:
            outer_pid = await outer.fetchval("SELECT pg_backend_pid()")
            assert get_session() is outer
            created_id = uuid4()
            created = await PrototypeCounter.objects.create(
                id=created_id, tenant_id=tenant, mutation_counter=0, label="manager-create"
            )
            assert created.id == created_id
            try:
                async with atomic(db=lab.db) as inner:
                    assert inner is outer
                    assert await inner.fetchval("SELECT pg_backend_pid()") == outer_pid
                    await PrototypeCounter.objects.filter(id=created_id).update(
                        mutation_counter=F("mutation_counter") + 10
                    )
                    raise InjectedFailure("inner savepoint")
            except InjectedFailure:
                pass
            assert (
                await PrototypeCounter.objects.get(id=created_id)
            ).mutation_counter == 0

    pids = await _atomic_complete(lab, claim, counter_id)
    snapshot = await _snapshot(lab, tenant, operation_id, counter_id)
    completion_pids = {
        snapshot["counter"]["last_backend_pid"],
        snapshot["operation"]["completion_backend_pid"],
        snapshot["attempts"][0]["completion_backend_pid"],
        *pids.values(),
    }
    assert len(completion_pids) == 1
    assert snapshot["counter"]["mutation_counter"] == 1
    assert snapshot["operation"]["state"] == "succeeded"
    assert snapshot["attempts"][0]["state"] == "succeeded"
    _record(
        "connection-pinning.json",
        "nested_savepoint_and_atomic_completion",
        {
            "outer_backend_pid": outer_pid,
            "completion_backend_pids": sorted(completion_pids),
            "nested_connection_identity": True,
            "inner_savepoint_rolled_back": True,
            "manager_create": True,
            "model_save": True,
            "queryset_update": True,
        },
    )


@pytest.mark.parametrize(
    "stage",
    [
        "before_begin",
        "after_lock",
        "during_database_mutation",
        "after_mutation",
        "after_attempt",
        "after_operation",
    ],
)
async def test_atomic_completion_rolls_back_every_precommit_failure(lab: Lab, stage: str):
    tenant, operation_id, counter_id = await _new_scenario(lab)
    claim = await _claim(lab, operation_id, tenant, f"worker-{stage}")
    assert claim is not None
    expected = Exception if stage == "during_database_mutation" else InjectedFailure
    with pytest.raises(expected):
        await _atomic_complete(lab, claim, counter_id, inject=stage)
    snapshot = await _snapshot(lab, tenant, operation_id, counter_id)
    _assert_rolled_back(snapshot)
    _record(
        "atomic-boundary-results.json",
        stage,
        {
            "application_mutation": 0,
            "operation_state": snapshot["operation"]["state"],
            "attempt_state": snapshot["attempts"][0]["state"],
            "fresh_connection_verified": True,
            "pass": True,
        },
    )


@pytest.mark.parametrize(
    "stage", ["after_lock", "after_mutation", "after_attempt", "after_operation"]
)
async def test_cancellation_rolls_back_at_async_boundaries(lab: Lab, stage: str):
    tenant, operation_id, counter_id = await _new_scenario(lab)
    claim = await _claim(lab, operation_id, tenant, f"cancel-{stage}")
    assert claim is not None
    with pytest.raises(asyncio.CancelledError):
        await _atomic_complete(
            lab, claim, counter_id, inject=stage, cancellation=True
        )
    snapshot = await _snapshot(lab, tenant, operation_id, counter_id)
    _assert_rolled_back(snapshot)
    assert get_session() is None
    _record(
        "failure-injection-results.json",
        f"cancellation_{stage}",
        {"rolled_back": True, "session_cleared": True, "pass": True},
    )


async def test_connection_termination_rolls_back_and_pool_recovers(lab: Lab):
    tenant, operation_id, counter_id = await _new_scenario(lab)
    claim = await _claim(lab, operation_id, tenant, "terminated-worker")
    assert claim is not None
    terminated_pid: int | None = None
    with _tenant_scope(tenant), pytest.raises(
        (asyncpg.ConnectionDoesNotExistError, asyncpg.InterfaceError)
    ):
        async with atomic(db=lab.db) as connection:
            terminated_pid = await connection.fetchval("SELECT pg_backend_pid()")
            row = await connection.fetchrow(
                f'SELECT * FROM "{OPERATIONS}" WHERE id=$1 FOR UPDATE', operation_id
            )
            assert row["fence"] == claim.fence
            await lab.db.execute(
                f'''
                    UPDATE "{COUNTERS}" SET mutation_counter=mutation_counter+1
                    WHERE id=$1
                    ''',
                counter_id,
            )
            assert await lab.admin.fetchval(
                "SELECT pg_terminate_backend($1)", terminated_pid
            )
            await connection.fetchval("SELECT 1")
    snapshot = await _snapshot(lab, tenant, operation_id, counter_id)
    _assert_rolled_back(snapshot)
    assert get_session() is None
    with _tenant_scope(tenant):
        replacement_pid = await lab.db.fetchval("SELECT pg_backend_pid()")
        assert await lab.db.fetchval("SELECT 1") == 1
    _record(
        "failure-injection-results.json",
        "connection_termination",
        {
            "terminated_backend_pid": terminated_pid,
            "replacement_backend_pid": replacement_pid,
            "rolled_back": True,
            "pool_recovered": True,
            "pass": True,
        },
    )


async def test_commit_acknowledgement_loss_requires_authoritative_reread(lab: Lab):
    tenant, operation_id, counter_id = await _new_scenario(lab)
    claim = await _claim(lab, operation_id, tenant, "ambiguous-worker")
    assert claim is not None
    with pytest.raises(CommitAcknowledgementLost):
        await _atomic_complete(lab, claim, counter_id)
        # Deterministic approximation: the exception is raised after the
        # transaction context has received a successful commit response.
        raise CommitAcknowledgementLost("response discarded after commit")
    snapshot = await _snapshot(lab, tenant, operation_id, counter_id)
    assert snapshot["counter"]["mutation_counter"] == 1
    assert snapshot["operation"]["state"] == "succeeded"
    assert snapshot["attempts"][0]["state"] == "succeeded"
    _record(
        "atomic-boundary-results.json",
        "commit_acknowledgement_lost",
        {
            "simulation": "client discards known successful commit response",
            "actual_network_ack_loss_injected": False,
            "application_mutation": 1,
            "operation_state": "succeeded",
            "attempt_state": "succeeded",
            "recovery_rule": "reconnect and read operation before retry",
            "pass": True,
        },
    )


async def test_atomicity_negative_controls_detect_split_and_escaped_commits(lab: Lab):
    results: dict[str, Any] = {}
    for scenario in ("split_commits", "different_connection"):
        tenant, operation_id, counter_id = await _new_scenario(lab)
        claim = await _claim(lab, operation_id, tenant, f"broken-{scenario}")
        assert claim is not None
        if scenario == "split_commits":
            with _tenant_scope(tenant):
                async with atomic(db=lab.db):
                    await PrototypeCounter.objects.filter(id=counter_id).update(
                        mutation_counter=F("mutation_counter") + 1
                    )
            # Crash/failure occurs before the separate completion transaction.
        else:
            with _tenant_scope(tenant), pytest.raises(InjectedFailure):
                async with atomic(db=lab.db):
                    escaped = await _role_connection(lab, tenant)
                    try:
                        await escaped.execute(
                            f'''
                                UPDATE "{COUNTERS}"
                                SET mutation_counter=mutation_counter+1
                                WHERE id=$1
                                ''',
                            counter_id,
                        )
                    finally:
                        await escaped.close()
                    raise InjectedFailure("outer transaction fails")
        snapshot = await _snapshot(lab, tenant, operation_id, counter_id)
        assert snapshot["counter"]["mutation_counter"] == 1
        assert snapshot["operation"]["state"] == "running"
        assert snapshot["attempts"][0]["state"] == "running"
        results[scenario] = {
            "defect_detected": True,
            "application_mutation": 1,
            "operation_state": "running",
            "attempt_state": "running",
        }

    # The reverse split is equally invalid: authoritative success cannot be
    # committed before an application mutation that later fails or never runs.
    tenant, operation_id, counter_id = await _new_scenario(lab)
    claim = await _claim(lab, operation_id, tenant, "broken-success-first")
    assert claim is not None
    connection = await _role_connection(lab, tenant)
    try:
        async with connection.transaction():
            assert _count(
                await connection.execute(
                    f'''
                    UPDATE "{ATTEMPTS}" SET state='succeeded',
                        completed_at=clock_timestamp()
                    WHERE id=$1 AND state='running'
                    ''',
                    claim.attempt_id,
                )
            ) == 1
            assert _count(
                await connection.execute(
                    f'''
                    UPDATE "{OPERATIONS}" SET state='succeeded'
                    WHERE id=$1 AND current_attempt=$2 AND fence=$3
                    ''',
                    operation_id,
                    claim.attempt_id,
                    claim.fence,
                )
            ) == 1
    finally:
        await connection.close()
    snapshot = await _snapshot(lab, tenant, operation_id, counter_id)
    assert snapshot["counter"]["mutation_counter"] == 0
    assert snapshot["operation"]["state"] == "succeeded"
    assert snapshot["attempts"][0]["state"] == "succeeded"
    results["success_without_mutation"] = {
        "defect_detected": True,
        "application_mutation": 0,
        "operation_state": "succeeded",
        "attempt_state": "succeeded",
    }
    _record("atomic-boundary-results.json", "negative_controls", results)


async def test_two_connection_claim_race_is_exclusive(lab: Lab):
    iterations = 15
    winners: list[str] = []
    for index in range(iterations):
        tenant, operation_id, _ = await _new_scenario(lab)
        connection_a = await _role_connection(lab, tenant)
        connection_b = await _role_connection(lab, tenant)
        try:
            start = asyncio.Event()

            async def contender(
                connection: asyncpg.Connection,
                worker: str,
                start_event: asyncio.Event = start,
                selected_operation: UUID = operation_id,
                selected_tenant: UUID = tenant,
            ):
                await start_event.wait()
                return await _claim_on_connection(
                    connection,
                    selected_operation,
                    selected_tenant,
                    worker,
                    lease_seconds=2,
                )

            task_a = asyncio.create_task(contender(connection_a, "worker-a"))
            task_b = asyncio.create_task(contender(connection_b, "worker-b"))
            start.set()
            claims = await asyncio.gather(task_a, task_b)
            non_null = [claim for claim in claims if claim is not None]
            assert len(non_null) == 1
            assert non_null[0].fence == 1
            winners.append(non_null[0].worker_id)
        finally:
            await connection_a.close()
            await connection_b.close()
    _record(
        "fencing-results.json",
        "two_connection_claim_race",
        {
            "iterations": iterations,
            "exclusive_winner_every_iteration": True,
            "worker_a_wins": winners.count("worker-a"),
            "worker_b_wins": winners.count("worker-b"),
            "pass": True,
        },
    )


async def test_n_to_n_plus_one_rejects_every_stale_write_and_b_completes(lab: Lab):
    tenant, operation_id, counter_id = await _new_scenario(lab)
    claim_a = await _claim(
        lab, operation_id, tenant, "worker-a", lease_seconds=0.12
    )
    assert claim_a is not None and claim_a.fence == 1
    await asyncio.sleep(0.16)
    claim_b = await _claim(lab, operation_id, tenant, "worker-b", lease_seconds=2)
    assert claim_b is not None and claim_b.fence == claim_a.fence + 1

    assert await _heartbeat(lab, claim_a) == 0
    assert await _progress(lab, claim_a, 90) == 0
    for state in ("succeeded", "failed", "cancelled"):
        assert await _stale_authoritative_write(lab, claim_a, state) == 0
    with pytest.raises(PermissionError, match="ownership lost"):
        await _atomic_complete(lab, claim_a, counter_id)
    attacked = await _snapshot(lab, tenant, operation_id, counter_id)
    assert attacked["counter"]["mutation_counter"] == 0
    assert attacked["operation"]["current_attempt"] == claim_b.attempt_id
    assert attacked["operation"]["fence"] == claim_b.fence
    assert attacked["operation"]["state"] == "running"
    assert attacked["attempts"][0]["state"] == "abandoned"
    assert attacked["attempts"][1]["state"] == "running"

    await _atomic_complete(lab, claim_b, counter_id)
    completed = await _snapshot(lab, tenant, operation_id, counter_id)
    assert completed["counter"]["mutation_counter"] == 1
    assert completed["operation"]["state"] == "succeeded"
    assert completed["attempts"][0]["state"] == "abandoned"
    assert completed["attempts"][1]["state"] == "succeeded"
    _record(
        "fencing-results.json",
        "n_to_n_plus_one",
        {
            "fence_n": claim_a.fence,
            "fence_n_plus_one": claim_b.fence,
            "attempt_a_state": "abandoned",
            "stale_heartbeat_rows": 0,
            "stale_progress_rows": 0,
            "stale_terminal_write_rows": 0,
            "stale_application_mutation": 0,
            "valid_b_application_mutation": 1,
            "operation_state": "succeeded",
            "attempt_b_state": "succeeded",
            "pass": True,
        },
    )


async def test_fencing_negative_controls_detect_broken_designs(lab: Lab):
    results: dict[str, Any] = {}

    # Finalization-only fence checking: a stale mutation commits before the
    # guarded finalization discovers ownership loss.
    tenant, operation_id, counter_id = await _new_scenario(lab)
    claim_a = await _claim(lab, operation_id, tenant, "a-finalize", lease_seconds=0.08)
    assert claim_a is not None
    await asyncio.sleep(0.11)
    claim_b = await _claim(lab, operation_id, tenant, "b-finalize")
    assert claim_b is not None
    connection = await _role_connection(lab, tenant)
    try:
        await connection.execute(
            f'UPDATE "{COUNTERS}" SET mutation_counter=mutation_counter+1 WHERE id=$1',
            counter_id,
        )
    finally:
        await connection.close()
    finalization_rows = await _stale_authoritative_write(lab, claim_a, "succeeded")
    snapshot = await _snapshot(lab, tenant, operation_id, counter_id)
    assert finalization_rows == 0 and snapshot["counter"]["mutation_counter"] == 1
    results["finalization_only"] = {
        "defect_detected": True,
        "stale_mutation_committed": 1,
        "finalization_rows": 0,
    }

    # Removed fence/attempt predicate: operation state alone cannot identify A.
    tenant, operation_id, counter_id = await _new_scenario(lab)
    claim_a = await _claim(lab, operation_id, tenant, "a-no-fence", lease_seconds=0.08)
    assert claim_a is not None
    await asyncio.sleep(0.11)
    claim_b = await _claim(lab, operation_id, tenant, "b-no-fence")
    assert claim_b is not None
    connection = await _role_connection(lab, tenant)
    try:
        async with connection.transaction():
            row = await connection.fetchrow(
                f'''
                SELECT state FROM "{OPERATIONS}"
                WHERE id=$1 AND tenant_id=$2 FOR UPDATE
                ''',
                operation_id,
                tenant,
            )
            assert row["state"] == "running"
            broken_rows = _count(
                await connection.execute(
                    f'''
                    UPDATE "{COUNTERS}" SET mutation_counter=mutation_counter+1
                    WHERE id=$1 AND tenant_id=$2
                    ''',
                    counter_id,
                    tenant,
                )
            )
    finally:
        await connection.close()
    snapshot = await _snapshot(lab, tenant, operation_id, counter_id)
    assert broken_rows == 1 and snapshot["counter"]["mutation_counter"] == 1
    results["removed_fence_condition"] = {
        "defect_detected": True,
        "stale_mutation_committed": 1,
        "current_fence": claim_b.fence,
        "stale_fence": claim_a.fence,
    }

    # Recovery without a fence increment violates monotonic takeover. Execute
    # that broken claim in a rollback-only admin transaction because the
    # prototype's uniqueness constraint correctly rejects duplicate fences.
    tenant, operation_id, _ = await _new_scenario(lab)
    claim_a = await _claim(lab, operation_id, tenant, "a-no-increment", lease_seconds=0.08)
    assert claim_a is not None
    await asyncio.sleep(0.11)
    broken_claim: Claim | None = None
    with pytest.raises(InjectedFailure, match="rollback broken recovery"):
        async with lab.admin.transaction():
            await lab.admin.execute(
                f'''
                ALTER TABLE "{ATTEMPTS}"
                DROP CONSTRAINT aksara_v070_proto_attempts_operation_id_fence_key
                '''
            )
            broken_claim = await _claim_on_connection(
                lab.admin,
                operation_id,
                tenant,
                "b-no-increment",
                lease_seconds=2,
                increment_fence=False,
            )
            assert broken_claim is not None
            assert broken_claim.fence == claim_a.fence
            raise InjectedFailure("rollback broken recovery")
    assert broken_claim is not None
    results["recovery_without_increment"] = {
        "defect_detected": True,
        "old_fence": claim_a.fence,
        "broken_candidate_fence": broken_claim.fence,
        "monotonicity_check": False,
    }

    # Heartbeat without attempt/fence identity lets A extend B's ownership.
    tenant, operation_id, _ = await _new_scenario(lab)
    claim_a = await _claim(lab, operation_id, tenant, "a-broken-heartbeat", lease_seconds=0.08)
    assert claim_a is not None
    await asyncio.sleep(0.11)
    claim_b = await _claim(lab, operation_id, tenant, "b-broken-heartbeat")
    assert claim_b is not None
    before = (await _snapshot(lab, tenant, operation_id, uuid4()))["operation"]["lease_expires_at"]
    connection = await _role_connection(lab, tenant)
    try:
        broken_heartbeat_rows = _count(
            await connection.execute(
                f'''
                UPDATE "{OPERATIONS}"
                SET lease_expires_at=clock_timestamp()+INTERVAL '10 seconds'
                WHERE id=$1 AND tenant_id=$2 AND state='running'
                ''',
                operation_id,
                tenant,
            )
        )
    finally:
        await connection.close()
    after = (await _snapshot(lab, tenant, operation_id, uuid4()))["operation"]["lease_expires_at"]
    assert broken_heartbeat_rows == 1 and after > before
    results["heartbeat_without_attempt_identity"] = {
        "defect_detected": True,
        "rows": broken_heartbeat_rows,
        "extended_current_owner_from_stale_request": True,
    }
    _record("fencing-results.json", "negative_controls", results)


async def test_lease_expiry_while_row_locked_serializes_takeover(lab: Lab):
    results: dict[str, Any] = {}
    for outcome in ("commit", "rollback"):
        tenant, operation_id, counter_id = await _new_scenario(lab)
        claim_a = await _claim(
            lab, operation_id, tenant, f"a-lock-{outcome}", lease_seconds=0.16
        )
        assert claim_a is not None
        locked, release = asyncio.Event(), asyncio.Event()

        async def a_transaction(
            selected_claim: Claim = claim_a,
            selected_counter: UUID = counter_id,
            selected_outcome: str = outcome,
            locked_event: asyncio.Event = locked,
            release_event: asyncio.Event = release,
        ):
            try:
                pids = await _atomic_complete(
                    lab,
                    selected_claim,
                    selected_counter,
                    inject="after_lock" if selected_outcome == "rollback" else None,
                    locked=locked_event,
                    release=release_event,
                )
                return pids
            except InjectedFailure:
                return None

        task_a = asyncio.create_task(a_transaction())
        await locked.wait()
        await asyncio.sleep(0.20)
        connection_b = await _role_connection(lab, tenant)
        task_b = asyncio.create_task(
            _claim_on_connection(
                connection_b, operation_id, tenant, f"b-lock-{outcome}", lease_seconds=2
            )
        )
        await asyncio.sleep(0.05)
        blocked_while_a_holds_lock = not task_b.done()
        assert blocked_while_a_holds_lock
        release.set()
        await task_a
        claim_b = await asyncio.wait_for(task_b, timeout=2)
        await connection_b.close()
        snapshot = await _snapshot(lab, tenant, operation_id, counter_id)
        if outcome == "commit":
            assert claim_b is None
            assert snapshot["counter"]["mutation_counter"] == 1
            assert snapshot["operation"]["state"] == "succeeded"
        else:
            assert claim_b is not None and claim_b.fence == claim_a.fence + 1
            assert snapshot["counter"]["mutation_counter"] == 0
            assert snapshot["operation"]["current_attempt"] == claim_b.attempt_id
        results[outcome] = {
            "b_blocked_while_a_held_row_lock": blocked_while_a_holds_lock,
            "b_reclaimed": claim_b is not None,
            "application_mutation": snapshot["counter"]["mutation_counter"],
            "operation_state": snapshot["operation"]["state"],
            "pass": True,
        }
    _record("fencing-results.json", "lease_expiry_while_locked", results)


async def _run_process(*arguments: str) -> tuple[int, str, str]:
    helper = Path(__file__).parent / "prototypes" / "v070_process_worker.py"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(helper),
        *arguments,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=os.environ.copy(),
    )
    stdout, stderr = await process.communicate()
    return process.returncode or 0, stdout.decode().strip(), stderr.decode().strip()


async def test_multiprocess_claim_death_reclaim_and_stale_attack(lab: Lab):
    tenant, operation_id, _ = await _new_scenario(lab)
    base = ("--operation-id", str(operation_id), "--tenant-id", str(tenant))
    result_a, result_b = await asyncio.gather(
        _run_process("claim", *base, "--worker-id", "process-a", "--lease-seconds", "2"),
        _run_process("claim", *base, "--worker-id", "process-b", "--lease-seconds", "2"),
    )
    assert result_a[0] == result_b[0] == 0
    claims = [json.loads(result_a[1]), json.loads(result_b[1])]
    assert len([claim for claim in claims if claim is not None]) == 1

    tenant, operation_id, counter_id = await _new_scenario(lab)
    helper = Path(__file__).parent / "prototypes" / "v070_process_worker.py"
    hold = await asyncio.create_subprocess_exec(
        sys.executable,
        str(helper),
        "claim-hold",
        "--operation-id",
        str(operation_id),
        "--tenant-id",
        str(tenant),
        "--worker-id",
        "process-dead-a",
        "--lease-seconds",
        "0.25",
        "--hold-seconds",
        "30",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=os.environ.copy(),
    )
    assert hold.stdout is not None
    claim_a = json.loads((await asyncio.wait_for(hold.stdout.readline(), timeout=5)).decode())
    hold.kill()
    await hold.wait()
    await asyncio.sleep(0.30)
    code, stdout, stderr = await _run_process(
        "claim",
        "--operation-id",
        str(operation_id),
        "--tenant-id",
        str(tenant),
        "--worker-id",
        "process-b",
        "--lease-seconds",
        "2",
    )
    assert code == 0, stderr
    claim_b = json.loads(stdout)
    assert claim_b["fence"] == claim_a["fence"] + 1

    code, stdout, stderr = await _run_process(
        "stale-complete",
        "--operation-id",
        str(operation_id),
        "--tenant-id",
        str(tenant),
        "--worker-id",
        "process-dead-a",
        "--attempt-id",
        claim_a["attempt_id"],
        "--counter-id",
        str(counter_id),
        "--fence",
        str(claim_a["fence"]),
    )
    assert code == 0, stderr
    stale = json.loads(stdout)
    assert stale == {"mutation_rows": 0, "ownership_valid": False}
    snapshot = await _snapshot(lab, tenant, operation_id, counter_id)
    assert snapshot["counter"]["mutation_counter"] == 0
    assert snapshot["operation"]["fence"] == claim_b["fence"]
    _record(
        "multiprocess-results.json",
        "claim_death_reclaim_stale_attack",
        {
            "independent_claim_processes": 2,
            "exclusive_claim": True,
            "worker_a_hard_killed": True,
            "reclaim_fence": claim_b["fence"],
            "stale_process_equivalent_rejected": True,
            "stale_application_mutation": 0,
            "pass": True,
        },
    )


async def test_transaction_escape_audit_identifies_prohibited_pool_acquire(lab: Lab):
    tenant, _, _ = await _new_scenario(lab)
    with _tenant_scope(tenant):
        async with atomic(db=lab.db) as pinned:
            pinned_pid = await pinned.fetchval("SELECT pg_backend_pid()")
            db_api_pid = await lab.db.fetchval("SELECT pg_backend_pid()")
            async with lab.db.acquire() as acquired:
                acquire_pid = await acquired.fetchval("SELECT pg_backend_pid()")
                assert acquired is pinned
            escaped = await lab.db.pool.acquire()
            try:
                escaped_pid = await escaped.fetchval("SELECT pg_backend_pid()")
            finally:
                await lab.db.pool.release(escaped)
    assert pinned_pid == db_api_pid == acquire_pid
    assert escaped_pid != pinned_pid
    _record(
        "connection-pinning.json",
        "escape_audit",
        {
            "database_methods_reused_pinned_connection": True,
            "database_acquire_reused_pinned_connection": True,
            "direct_pool_acquire_escaped": True,
            "pinned_backend_pid": pinned_pid,
            "escaped_backend_pid": escaped_pid,
            "future_executor_must_prohibit_direct_pool_acquire": True,
        },
    )


async def test_pool_session_and_tenant_context_recover_after_faults(lab: Lab):
    tenant_a, operation_id, counter_a = await _new_scenario(lab)
    tenant_b = uuid4()
    _, _, counter_b = await _new_scenario(lab, tenant_id=tenant_b)
    claim = await _claim(lab, operation_id, tenant_a, "cleanup-worker")
    assert claim is not None
    for stage in ("after_lock", "after_mutation", "after_attempt", "after_operation"):
        with pytest.raises(asyncio.CancelledError):
            await _atomic_complete(
                lab, claim, counter_a, inject=stage, cancellation=True
            )
        assert get_session() is None

    with _tenant_scope(tenant_a):
        assert await PrototypeCounter.objects.filter(id=counter_b).all() == []
        assert await PrototypeCounter.objects.filter(id=counter_a).count() == 1
    with _tenant_scope(tenant_b):
        assert await PrototypeCounter.objects.filter(id=counter_a).all() == []
        assert await PrototypeCounter.objects.filter(id=counter_b).count() == 1
    with _tenant_scope(None):
        assert await PrototypeCounter.objects.all() == []
        setting = await lab.db.fetchval(
            "SELECT current_setting('aksara.current_tenant_id', true)"
        )
        assert setting in (None, "")
    assert get_session() is None
    assert lab.db.pool.get_idle_size() == lab.db.pool.get_size()
    with _tenant_scope(tenant_a):
        assert await lab.db.fetchval("SELECT 1") == 1
    _record(
        "pool-cleanup-results.json",
        "fault_campaign_and_tenant_reuse",
        {
            "cancelled_transactions": 4,
            "session_context_cleared": True,
            "pool_size": lab.db.pool.get_size(),
            "pool_idle": lab.db.pool.get_idle_size(),
            "subsequent_query_succeeded": True,
            "tenant_a_cannot_read_b": True,
            "tenant_b_cannot_read_a": True,
            "no_tenant_reads_no_rows": True,
            "tenant_guc_cleared": True,
            "pass": True,
        },
    )


async def test_performance_sanity_uses_short_transactions(lab: Lab):
    timings: dict[str, list[float]] = {
        "claim_ms": [],
        "heartbeat_ms": [],
        "fence_validation_and_completion_ms": [],
        "reclaim_ms": [],
    }
    for index in range(8):
        tenant, operation_id, counter_id = await _new_scenario(lab)
        start = time.perf_counter()
        claim = await _claim(lab, operation_id, tenant, f"perf-{index}", lease_seconds=2)
        timings["claim_ms"].append((time.perf_counter() - start) * 1000)
        assert claim is not None
        start = time.perf_counter()
        assert await _heartbeat(lab, claim) == 1
        timings["heartbeat_ms"].append((time.perf_counter() - start) * 1000)
        start = time.perf_counter()
        await _atomic_complete(lab, claim, counter_id)
        timings["fence_validation_and_completion_ms"].append(
            (time.perf_counter() - start) * 1000
        )
    tenant, operation_id, _ = await _new_scenario(lab)
    claim = await _claim(lab, operation_id, tenant, "perf-expire", lease_seconds=0.05)
    assert claim is not None
    await asyncio.sleep(0.07)
    start = time.perf_counter()
    reclaimed = await _claim(lab, operation_id, tenant, "perf-reclaim", lease_seconds=2)
    timings["reclaim_ms"].append((time.perf_counter() - start) * 1000)
    assert reclaimed is not None
    summary = {
        name: {
            "samples": len(values),
            "min_ms": round(min(values), 3),
            "median_ms": round(sorted(values)[len(values) // 2], 3),
            "max_ms": round(max(values), 3),
        }
        for name, values in timings.items()
    }
    assert all(item["max_ms"] < 2000 for item in summary.values())
    _record(
        "performance-sanity.json",
        "local_integration_sample",
        {
            "purpose": "pathology detection only; not a benchmark claim",
            "transactions_hold_no application work across claims": True,
            "results": summary,
            "pass": True,
        },
    )
