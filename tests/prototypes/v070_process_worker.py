"""Independent-process worker for the v0.7 operation invariant prototype.

This module is test-only.  It deliberately uses the disposable prototype
tables created by ``test_v070_operation_invariants.py`` and is never imported
by the Aksara package.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any
from uuid import UUID, uuid4

import asyncpg

OPERATIONS = "aksara_v070_proto_operations"
ATTEMPTS = "aksara_v070_proto_attempts"
COUNTERS = "aksara_v070_proto_counters"
TENANT_SETTING = "aksara.current_tenant_id"


def _json_value(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


async def _claim(
    connection: asyncpg.Connection,
    operation_id: UUID,
    tenant_id: UUID,
    worker_id: str,
    lease_seconds: float,
) -> dict[str, Any] | None:
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

        if row["state"] == "running" and row["current_attempt"] is not None:
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

        attempt_id = uuid4()
        fence = int(row["fence"]) + 1
        attempt = await connection.fetchrow(
            f'''
            INSERT INTO "{ATTEMPTS}" (
                id, operation_id, tenant_id, fence, worker_id, state,
                lease_expires_at, backend_pid
            )
            VALUES (
                $1, $2, $3, $4, $5, 'running',
                clock_timestamp() + ($6::double precision * INTERVAL '1 second'),
                pg_backend_pid()
            )
            RETURNING lease_expires_at, backend_pid
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
            attempt["lease_expires_at"],
            tenant_id,
        )
        return {
            "operation_id": operation_id,
            "attempt_id": attempt_id,
            "tenant_id": tenant_id,
            "worker_id": worker_id,
            "fence": fence,
            "lease_expires_at": attempt["lease_expires_at"],
            "backend_pid": attempt["backend_pid"],
        }


async def _stale_complete(
    connection: asyncpg.Connection,
    *,
    operation_id: UUID,
    attempt_id: UUID,
    counter_id: UUID,
    tenant_id: UUID,
    worker_id: str,
    fence: int,
) -> dict[str, Any]:
    async with connection.transaction():
        row = await connection.fetchrow(
            f'''
            SELECT state, current_attempt, fence, worker_id
            FROM "{OPERATIONS}"
            WHERE id = $1 AND tenant_id = $2
            FOR UPDATE
            ''',
            operation_id,
            tenant_id,
        )
        owns = bool(
            row
            and row["state"] == "running"
            and row["current_attempt"] == attempt_id
            and row["fence"] == fence
            and row["worker_id"] == worker_id
        )
        if not owns:
            return {"ownership_valid": False, "mutation_rows": 0}
        status = await connection.execute(
            f'''
            UPDATE "{COUNTERS}"
            SET mutation_counter = mutation_counter + 1,
                updated_at = clock_timestamp()
            WHERE id = $1 AND tenant_id = $2
            ''',
            counter_id,
            tenant_id,
        )
        return {
            "ownership_valid": True,
            "mutation_rows": int(status.rsplit(" ", 1)[-1]),
        }


async def _run(args: argparse.Namespace) -> int:
    dsn = os.environ["AKSARA_V070_ROLE_DSN"]
    connection = await asyncpg.connect(dsn)
    try:
        tenant_id = UUID(args.tenant_id)
        await connection.execute(
            f"SELECT set_config('{TENANT_SETTING}', $1, false)",
            str(tenant_id),
        )
        if args.action in {"claim", "claim-hold"}:
            result = await _claim(
                connection,
                UUID(args.operation_id),
                tenant_id,
                args.worker_id,
                args.lease_seconds,
            )
            print(
                json.dumps(result, default=_json_value, sort_keys=True),
                flush=True,
            )
            if args.action == "claim-hold" and result is not None:
                await asyncio.sleep(args.hold_seconds)
            return 0

        result = await _stale_complete(
            connection,
            operation_id=UUID(args.operation_id),
            attempt_id=UUID(args.attempt_id),
            counter_id=UUID(args.counter_id),
            tenant_id=tenant_id,
            worker_id=args.worker_id,
            fence=args.fence,
        )
        print(json.dumps(result, sort_keys=True), flush=True)
        return 0
    finally:
        await connection.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--operation-id", required=True)
    common.add_argument("--tenant-id", required=True)
    common.add_argument("--worker-id", required=True)

    actions = parser.add_subparsers(dest="action", required=True)
    claim = actions.add_parser("claim", parents=[common])
    claim.add_argument("--lease-seconds", type=float, default=1.0)

    claim_hold = actions.add_parser("claim-hold", parents=[common])
    claim_hold.add_argument("--lease-seconds", type=float, default=1.0)
    claim_hold.add_argument("--hold-seconds", type=float, default=30.0)

    stale_complete = actions.add_parser("stale-complete", parents=[common])
    stale_complete.add_argument("--attempt-id", required=True)
    stale_complete.add_argument("--counter-id", required=True)
    stale_complete.add_argument("--fence", type=int, default=0)
    return parser


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run(_parser().parse_args())))
