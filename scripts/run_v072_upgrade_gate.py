"""Exercise a public v0.7.1 application schema through a v0.7.2rc1 upgrade."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import asyncpg

ROOT = Path(__file__).resolve().parents[1]

V071_PHASE = r'''
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID, uuid4

import aksara
import asyncpg
from aksara.migrations.executor import apply_migrations
import aksara._examples.support_desk as support_desk


async def main():
    dsn, tenant_id = sys.argv[1:3]
    assert aksara.__version__ == "0.7.1"
    assert "site-packages" in str(Path(aksara.__file__).resolve())
    conn = await asyncpg.connect(dsn)
    try:
        migrations = Path(support_desk.__file__).resolve().parent / "migrations"
        result = await apply_migrations(conn, migrations, include_internal=True, verbose=False)
        assert result["errors"] == [], result
        pre_columns = {
            row["column_name"]
            for row in await conn.fetch(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = 'aksara_tasks'"
            )
        }
        assert "claim_token" not in pre_columns

        organization_id, agent_id, ticket_id, task_id, operation_id = [uuid4() for _ in range(5)]
        await conn.execute(
            "INSERT INTO support_organizations "
            "(id, name, slug, created_at, updated_at) "
            "VALUES ($1, 'Upgrade Org', 'upgrade-org', clock_timestamp(), clock_timestamp())",
            organization_id,
        )
        await conn.execute(
            "INSERT INTO support_agents "
            "(id, tenant_id, name, email, role, is_active, created_at, updated_at) "
            "VALUES ($1, $2, 'Upgrade Agent', 'upgrade@example.invalid', 'admin', true, "
            "clock_timestamp(), clock_timestamp())",
            agent_id,
            UUID(tenant_id),
        )
        await conn.execute(
            "INSERT INTO support_tickets "
            "(id, tenant_id, subject, description, status, priority, assigned_to_id, "
            "created_at, updated_at) VALUES ($1, $2, 'Persisted upgrade ticket', "
            "'Created with public v0.7.1', 'open', 'normal', $3, "
            "clock_timestamp(), clock_timestamp())",
            ticket_id,
            UUID(tenant_id),
            agent_id,
        )
        await conn.execute(
            "INSERT INTO aksara_tasks "
            "(id, task_name, queue, tenant_id, payload, status, attempts, max_attempts, "
            "available_at, created_at, updated_at) VALUES "
            "($1, 'support_desk.upgrade_probe', 'default', $2, $3::jsonb, 'pending', "
            "0, 3, clock_timestamp(), clock_timestamp(), clock_timestamp())",
            task_id,
            tenant_id,
            json.dumps({"ticket_id": str(ticket_id)}),
        )
        await conn.execute(
            "INSERT INTO aksara_operations "
            "(id, application_namespace, tenant_id, tenant_scope, action_name, action_version, "
            "executor_type, effect_class, command_id, resolver_key, resolver_version, "
            "principal_reference, principal_reference_hash, canonical_input_hash, state, "
            "result, retain_until) VALUES "
            "($1, 'support-desk-upgrade', $2, $2, 'upgrade.probe', '1', 'inline', "
            "'read_only', $3, 'upgrade-probe', '1', '{}'::jsonb, $4, $5, 'succeeded', "
            "'{\"preserved\": true}'::jsonb, clock_timestamp() + interval '1 day')",
            operation_id,
            tenant_id,
            uuid4(),
            "0" * 64,
            "1" * 64,
        )
        print(json.dumps({
            "version": aksara.__version__,
            "origin": str(Path(aksara.__file__).resolve()),
            "migrations": result["applied"],
            "ids": {"organization": str(organization_id), "agent": str(agent_id),
                    "ticket": str(ticket_id), "task": str(task_id),
                    "operation": str(operation_id)},
            "task_columns_before": sorted(pre_columns),
        }, sort_keys=True))
    finally:
        await conn.close()


asyncio.run(main())
'''

CANDIDATE_PHASE = r'''
import asyncio
import json
import os
import sys
from pathlib import Path

import aksara
import asyncpg
from aksara.db import Database
from aksara.migrations.executor import apply_migrations
from aksara.tasks import TaskWorker
import aksara._examples.support_desk as support_desk


async def main():
    dsn, tenant_id, ids_json = sys.argv[1:4]
    ids = json.loads(ids_json)
    assert aksara.__version__ == "0.7.2rc1"
    assert "site-packages" in str(Path(aksara.__file__).resolve())
    conn = await asyncpg.connect(dsn)
    database = None
    try:
        migrations = Path(support_desk.__file__).resolve().parent / "migrations"
        result = await apply_migrations(conn, migrations, include_internal=True, verbose=False)
        assert result["errors"] == [], result
        assert "aksara_core_migrations_0003_task_claim_ownership" in result["applied"], result
        columns = {
            row["column_name"]
            for row in await conn.fetch(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = 'aksara_tasks'"
            )
        }
        assert {"locked_by", "claim_token", "lock_expires_at"} <= columns
        ticket = await conn.fetchrow(
            "SELECT subject, description, assigned_to_id, tenant_id FROM support_tickets WHERE id = $1",
            ids["ticket"],
        )
        assert ticket and ticket["subject"] == "Persisted upgrade ticket"
        assert str(ticket["assigned_to_id"]) == ids["agent"]
        assert str(ticket["tenant_id"]) == tenant_id
        operation = await conn.fetchrow(
            "SELECT state, result FROM aksara_operations WHERE id = $1", ids["operation"]
        )
        operation_result = json.loads(operation["result"]) if operation else {}
        assert operation and operation["state"] == "succeeded" and operation_result["preserved"]
        task = await conn.fetchrow(
            "SELECT status, locked_by, claim_token, lock_expires_at FROM aksara_tasks WHERE id = $1",
            ids["task"],
        )
        assert task and task["status"] == "pending"
        assert task["locked_by"] is None and task["claim_token"] is None

        database = Database(dsn, min_size=1, max_size=2)
        await database.connect()
        worker = TaskWorker(database, worker_id="v072-upgrade-worker")
        claim = await worker._claim_task()
        assert claim is not None and str(claim.id) == ids["task"]
        assert claim.locked_by == "v072-upgrade-worker" and claim.claim_token is not None
        replay = await apply_migrations(conn, migrations, include_internal=True, verbose=False)
        assert replay["errors"] == [] and replay["applied"] == [], replay
        print(json.dumps({
            "version": aksara.__version__,
            "origin": str(Path(aksara.__file__).resolve()),
            "migrations_applied": result["applied"],
            "migrations_idempotent": True,
            "data_preserved": True,
            "relation_preserved": True,
            "durable_operation_preserved": True,
            "queued_task_upgraded": True,
            "task_claimed_with_owner_token": True,
            "task_columns_after": sorted(columns),
        }, sort_keys=True))
    finally:
        if database is not None:
            await database.disconnect()
        await conn.close()


asyncio.run(main())
'''

HTTP_PHASE = r'''
import json
from fastapi.testclient import TestClient
from aksara._examples.support_desk.main import app

with TestClient(app) as client:
    anonymous = client.get("/api/tickets/")
    authorized = client.get(
        "/api/tickets/",
        headers={"Authorization": "Bearer development-tenant-a-token"},
    )
    admin = client.get("/admin/login/")
    catalog = client.get(
        "/ai/tools/mcp",
        headers={"Authorization": "Bearer development-mcp-agent-token"},
    )
    payload = authorized.json()
    subjects = [row["subject"] for row in payload["results"]]
    assert anonymous.status_code == 403
    assert authorized.status_code == 200 and "Persisted upgrade ticket" in subjects
    assert admin.status_code == 200
    assert catalog.status_code == 200 and any(
        tool["name"] == "ticket_list" for tool in catalog.json()["tools"]
    )
    print(json.dumps({
        "anonymous_status": anonymous.status_code,
        "authorized_status": authorized.status_code,
        "preserved_ticket_visible": True,
        "admin_status": admin.status_code,
        "mcp_catalog_status": catalog.status_code,
        "mcp_ticket_tool": True,
    }, sort_keys=True))
'''


def scoped_dsn(base: str, schema: str) -> str:
    parsed = urlsplit(base)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["options"] = f"-csearch_path={schema}"
    return urlunsplit(parsed._replace(query=urlencode(query)))


def run_phase(python: Path, script: Path, args: list[str], env: dict[str, str]) -> dict:
    run = subprocess.run(
        [str(python), "-I", str(script), *args],
        cwd=script.parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr or run.stdout
    for line in reversed(run.stdout.splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise AssertionError(f"phase emitted no JSON object: {run.stdout}")


async def run(args: argparse.Namespace) -> dict:
    schema = f"aksara_v072_upgrade_{uuid4().hex[:12]}"
    tenant_id = "00000000-0000-0000-0000-000000000001"
    admin = await asyncpg.connect(args.database_url)
    try:
        await admin.execute(f'CREATE SCHEMA "{schema}"')
        dsn = scoped_dsn(args.database_url, schema)
        env = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}}
        env.update({
            "DATABASE_URL": dsn,
            "AKSARA_DATABASE_URL": dsn,
            "AKSARA_SUPPRESS_BRAND": "1",
            "AKSARA_TASK_POLL_INTERVAL": "10",
            "SUPPORT_DESK_MCP_TOKEN_EXPIRES_AT": "4102444800",
        })
        with tempfile.TemporaryDirectory(prefix="aksara-v072-upgrade-") as raw:
            root = Path(raw)
            old_script = root / "public_v071.py"
            candidate_script = root / "candidate.py"
            http_script = root / "http.py"
            old_script.write_text(V071_PHASE)
            candidate_script.write_text(CANDIDATE_PHASE)
            http_script.write_text(HTTP_PHASE)
            old = await asyncio.to_thread(
                run_phase, args.public_python, old_script, [dsn, tenant_id], env
            )
            candidate = await asyncio.to_thread(
                run_phase,
                args.candidate_python,
                candidate_script,
                [dsn, tenant_id, json.dumps(old["ids"])],
                env,
            )
            http = await asyncio.to_thread(
                run_phase, args.candidate_python, http_script, [], env
            )
        return {
            "schema_version": 1,
            "pass": True,
            "public_v071": old,
            "candidate": candidate,
            "application_surfaces": http,
            "doctor": "covered by the candidate packaged Support Desk gate on the same wheel",
            "durable_runtime": "preserved row here; execution/revocation/retry covered by the candidate packaged Support Desk gate",
            "database": urlsplit(args.database_url).path.lstrip("/"),
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "scope": "Public PyPI v0.7.1 installed package creates and seeds a Support Desk schema; the installed v0.7.2rc1 wheel upgrades it and verifies persisted data, relations, queued-task ownership migration, Durable Operation state, REST authorization, Admin, and MCP discovery.",
        }
    finally:
        await admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await admin.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-python", required=True, type=Path)
    parser.add_argument("--candidate-python", required=True, type=Path)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    result = asyncio.run(run(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("PASS: public v0.7.1 Support Desk data and runtime state survive candidate upgrade")


if __name__ == "__main__":
    main()
