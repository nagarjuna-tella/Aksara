"""Run the packaged support desk reference app against real PostgreSQL."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from importlib.metadata import version as distribution_version
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import asyncpg
import httpx

ROOT = Path(__file__).resolve().parent.parent
MIGRATION_HELPER = r'''
import asyncio
import json
import shutil
import sys
import tempfile
from pathlib import Path

import asyncpg

from aksara.migrations.executor import apply_migrations
import aksara._examples.support_desk as support_desk


async def main():
    dsn, stage = sys.argv[1:3]
    source = Path(support_desk.__file__).resolve().parent / "migrations"
    with tempfile.TemporaryDirectory(prefix="aksara-support-migrations-") as raw:
        path = source
        if stage == "first":
            path = Path(raw)
            shutil.copy(source / "support_desk_0001_initial.py", path)
        conn = await asyncpg.connect(dsn)
        try:
            result = await apply_migrations(
                conn,
                path,
                include_internal=True,
                verbose=False,
            )
            result["errors"] = [[name, str(error)] for name, error in result["errors"]]
            print(json.dumps(result, sort_keys=True))
        finally:
            await conn.close()


asyncio.run(main())
'''

RUNTIME_HELPER = r'''
import asyncio
import json
import sys
from uuid import uuid4

from aksara.context_state import tenant_id_var
from aksara.db import Database, transaction


async def main():
    dsn, tenant_a, tenant_b = sys.argv[1:4]
    db = Database(dsn, min_size=1, max_size=2)
    await db.connect()
    pids = []
    contexts = []
    try:
        for tenant in (tenant_a, tenant_b, tenant_a, None, tenant_b, None):
            token = tenant_id_var.set(tenant)
            try:
                pids.append(await db.fetchval("SELECT pg_backend_pid()"))
                contexts.append(
                    await db.fetchval(
                        "SELECT NULLIF(current_setting('aksara.current_tenant_id', true), '')"
                    )
                )
            finally:
                tenant_id_var.reset(token)

        slug = "rollback-" + uuid4().hex
        try:
            async with transaction.atomic(db=db):
                await db.execute(
                    """INSERT INTO support_organizations
                    (name, slug, created_at, updated_at)
                    VALUES ($1, $2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                    "Must roll back",
                    slug,
                )
                raise RuntimeError("intentional transaction failure")
        except RuntimeError:
            pass
        persisted = await db.fetchval(
            "SELECT COUNT(*) FROM support_organizations WHERE slug = $1",
            slug,
        )
        print(json.dumps({
            "backend_pids": pids,
            "contexts": contexts,
            "rollback_rows": persisted,
        }, sort_keys=True))
    finally:
        await db.disconnect()


asyncio.run(main())
'''


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True, help="Built Aksara wheel")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="Administrative PostgreSQL URL (or set DATABASE_URL)",
    )
    parser.add_argument(
        "--evidence-output",
        type=Path,
        default=ROOT / "audit-evidence" / "v070" / "support-desk-gate.json",
    )
    return parser


def _dsn_for_identity(base: str, user: str, password: str, schema: str, app_name: str) -> str:
    parsed = urlsplit(base)
    host = parsed.hostname or "localhost"
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parsed.port}" if parsed.port else ""
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update(
        {
            "application_name": app_name,
            "options": f"-csearch_path={schema}",
        }
    )
    return urlunsplit(
        (
            parsed.scheme,
            f"{quote(user)}:{quote(password)}@{host}{port}",
            parsed.path,
            urlencode(query),
            parsed.fragment,
        )
    )


def _dsn_for_schema(base: str, schema: str, app_name: str) -> str:
    parsed = urlsplit(base)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update(
        {
            "application_name": app_name,
            "options": f"-csearch_path={schema}",
        }
    )
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )


def _unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Gate:
    def __init__(self, *, wheel: Path, database_url: str, evidence_output: Path):
        self.wheel = wheel.resolve()
        self.database_url = database_url
        self.evidence_output = evidence_output.resolve()
        self.started_at = datetime.now(UTC)
        self.checks: list[dict[str, Any]] = []
        self._sensitive: list[str] = []

    def check(self, name: str, condition: bool, **details: Any) -> None:
        self.checks.append(
            {
                "name": name,
                "status": "pass" if condition else "fail",
                "details": details,
            }
        )
        if not condition:
            raise AssertionError(f"support desk gate failed: {name}")

    def redact(self, value: str) -> str:
        redacted = value
        for secret in self._sensitive:
            if secret:
                redacted = redacted.replace(secret, "[REDACTED]")
        return redacted

    def write_evidence(self, *, status: str, error: str | None = None) -> None:
        payload = {
            "schema_version": 1,
            "gate": "support-desk-v070-production-reference",
            "status": status,
            "started_at": self.started_at.isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
            "wheel": self.wheel.name,
            "wheel_sha256": _sha256(self.wheel) if self.wheel.exists() else None,
            "database": urlsplit(self.database_url).path.lstrip("/"),
            "checks": self.checks,
            "error": self.redact(error) if error else None,
        }
        self.evidence_output.parent.mkdir(parents=True, exist_ok=True)
        self.evidence_output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    async def run(self) -> None:
        if not self.wheel.is_file():
            raise FileNotFoundError(self.wheel)
        if not self.database_url:
            raise RuntimeError("--database-url or DATABASE_URL is required")

        suffix = uuid4().hex[:10]
        schema = f"aksara_support_{suffix}"
        role = f"aksara_support_{suffix}"
        role_password = secrets.token_urlsafe(30)
        secret_key = secrets.token_urlsafe(48)
        app_name = f"aksara-support-gate-{suffix}"
        tenant_a = str(uuid4())
        tenant_b = str(uuid4())
        tokens = [secrets.token_urlsafe(32) for _ in range(6)]
        self._sensitive.extend([role_password, secret_key, *tokens, self.database_url])

        admin = await asyncpg.connect(self.database_url)
        temp_root = Path(tempfile.mkdtemp(prefix="aksara-support-gate-"))
        python = temp_root / "venv" / "bin" / "python"
        migration_helper = temp_root / "migration_helper.py"
        runtime_helper = temp_root / "runtime_helper.py"
        migration_helper.write_text(MIGRATION_HELPER, encoding="utf-8")
        runtime_helper.write_text(RUNTIME_HELPER, encoding="utf-8")
        security_matrix = temp_root / "security_matrix.yml"
        shutil.copy(ROOT / "security" / "security_matrix.release.yml", security_matrix)
        servers: list[asyncio.subprocess.Process] = []

        app_dsn = _dsn_for_identity(
            self.database_url,
            role,
            role_password,
            schema,
            app_name,
        )
        admin_schema_dsn = _dsn_for_schema(self.database_url, schema, f"{app_name}-migrate")
        self._sensitive.extend([app_dsn, admin_schema_dsn])
        app_env = self._app_environment(
            app_dsn=app_dsn,
            tenant_a=tenant_a,
            tenant_b=tenant_b,
            tokens=tokens,
            secret_key=secret_key,
            security_matrix=security_matrix,
        )

        try:
            await self._install_wheel(python, temp_root)
            await self._configuration_checks(python, temp_root, app_env)

            escaped_password = role_password.replace("'", "''")
            await admin.execute(
                f'''CREATE ROLE "{role}" LOGIN PASSWORD '{escaped_password}'
                NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION'''
            )
            await admin.execute(f'CREATE SCHEMA "{schema}" AUTHORIZATION CURRENT_USER')
            attrs = await admin.fetchrow(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = $1",
                role,
            )
            self.check(
                "restricted application role",
                attrs is not None and not attrs["rolsuper"] and not attrs["rolbypassrls"],
                superuser=bool(attrs["rolsuper"]),
                bypass_rls=bool(attrs["rolbypassrls"]),
            )

            first = await self._migration_run(
                python,
                migration_helper,
                admin_schema_dsn,
                "first",
                temp_root,
            )
            self.check(
                "fresh schema migration",
                first["errors"] == []
                and "support_desk_0001_initial" in first["applied"]
                and "aksara_core_migrations_0001_runtime_tables" in first["applied"],
                applied=first["applied"],
            )
            await admin.execute(
                f'''INSERT INTO "{schema}".support_tickets
                (tenant_id, subject, description, status, created_at, updated_at)
                VALUES (
                    $1, 'Pre-upgrade ticket', 'Existing row', 'open',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )''',
                tenant_a,
            )
            await self._grant_application_access(admin, schema, role)

            failed_start_log = temp_root / "unapplied.log"
            failed_process = await self._start_server(
                python,
                temp_root,
                app_env,
                _unused_port(),
                failed_start_log,
            )
            servers.append(failed_process)
            failed_code = await asyncio.wait_for(failed_process.wait(), timeout=15)
            servers.remove(failed_process)
            failed_text = failed_start_log.read_text(encoding="utf-8", errors="replace")
            self.check(
                "unapplied migration fails startup",
                failed_code != 0 and "Unapplied support desk migrations" in failed_text,
                exit_code=failed_code,
            )
            self.check(
                "failed startup releases connections",
                await self._connection_count(admin, role) == 0,
                active_connections=await self._connection_count(admin, role),
            )

            upgrade = await self._migration_run(
                python,
                migration_helper,
                admin_schema_dsn,
                "all",
                temp_root,
            )
            self.check(
                "existing schema upgrade",
                upgrade["errors"] == []
                and upgrade["applied"] == ["support_desk_0002_ticket_priority"],
                applied=upgrade["applied"],
            )
            priority = await admin.fetchval(
                f'''SELECT priority FROM "{schema}".support_tickets
                WHERE subject = 'Pre-upgrade ticket' AND tenant_id = $1''',
                tenant_a,
            )
            self.check("upgrade preserves existing rows", priority == "normal", priority=priority)

            existing = await self._migration_run(
                python,
                migration_helper,
                admin_schema_dsn,
                "all",
                temp_root,
            )
            self.check(
                "existing schema migration is idempotent",
                existing["errors"] == [] and existing["applied"] == [],
                skipped=len(existing["skipped"]),
            )
            await self._grant_application_access(admin, schema, role)
            await self._doctor_checks(python, temp_root, app_env)
            rls_rows = await admin.fetch(
                """
                SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = $1
                  AND c.relname IN (
                      'support_agents', 'support_tickets', 'support_delivery_attempts'
                  )
                ORDER BY c.relname
                """,
                schema,
            )
            self.check(
                "tenant tables force PostgreSQL RLS",
                len(rls_rows) == 3
                and all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in rls_rows),
                tables=[row["relname"] for row in rls_rows],
            )

            runtime = await self._runtime_probe(
                python,
                runtime_helper,
                app_dsn,
                tenant_a,
                tenant_b,
                temp_root,
            )
            expected_contexts = [tenant_a, tenant_b, tenant_a, None, tenant_b, None]
            self.check(
                "pool reuse resets tenant context",
                runtime["contexts"] == expected_contexts
                and len(set(runtime["backend_pids"])) <= 2,
                backend_count=len(set(runtime["backend_pids"])),
                switches=len(runtime["contexts"]),
            )
            self.check(
                "transaction failure rolls back",
                runtime["rollback_rows"] == 0,
                persisted_rows=runtime["rollback_rows"],
            )

            durable = await self._durable_probe(
                python,
                app_dsn,
                tenant_a,
                tenant_b,
                temp_root,
                app_env,
            )
            for name, passed in durable["checks"].items():
                self.check(
                    f"v0.7 durable {name.replace('_', ' ')}",
                    passed,
                )

            port = _unused_port()
            first_log = temp_root / "server-first.log"
            server = await self._start_server(python, temp_root, app_env, port, first_log)
            servers.append(server)
            await self._wait_ready(port)
            ids = await self._exercise_http(port, tokens, tenant_a, tenant_b)

            pending = await self._wait_task_state(
                port,
                tokens[0],
                ids["task_id"],
                lambda record: record["status"] == "pending" and record["attempts"] == 1,
                timeout=8,
            )
            self.check(
                "durable task records failed attempt",
                pending["attempts"] == 1 and pending["last_error"],
                status=pending["status"],
                attempts=pending["attempts"],
            )
            await self._crash_server(server)
            servers.remove(server)

            restart_log = temp_root / "server-restart.log"
            server = await self._start_server(python, temp_root, app_env, port, restart_log)
            servers.append(server)
            await self._wait_ready(port)
            completed = await self._wait_task_state(
                port,
                tokens[0],
                ids["task_id"],
                lambda record: record["status"] == "completed",
                timeout=10,
            )
            delivery = await admin.fetchrow(
                f'''SELECT attempts, delivered, tenant_id
                FROM "{schema}".support_delivery_attempts
                WHERE ticket_id = $1''',
                ids["ticket_a"],
            )
            self.check(
                "task retry survives worker and app restart",
                completed["attempts"] == 2
                and delivery is not None
                and delivery["attempts"] == 2
                and delivery["delivered"]
                and str(delivery["tenant_id"]) == tenant_a,
                task_attempts=completed["attempts"],
                delivered=bool(delivery["delivered"]),
            )
            await self._exercise_mcp(
                python,
                port,
                tokens,
                ids,
                tenant_a,
                tenant_b,
                secret_key,
                Path(app_env["SUPPORT_DESK_MCP_AUDIT_PATH"]),
                Path(app_env["SUPPORT_DESK_MCP_REVOCATION_FILE"]),
            )

            terminated = await admin.fetchval(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE usename = $1 AND pid <> pg_backend_pid()
                ) terminated
                """,
                role,
            )
            await self._wait_ready(port, timeout=12)
            self.check(
                "database connection recovers after backend termination",
                int(terminated or 0) >= 1,
                terminated_connections=int(terminated or 0),
            )

            second_port = _unused_port()
            second_log = temp_root / "server-second.log"
            second = await self._start_server(
                python,
                temp_root,
                app_env,
                second_port,
                second_log,
            )
            servers.append(second)
            await self._wait_ready(second_port)
            await self._concurrent_requests(port, second_port, tokens)

            await self._stop_server(second)
            servers.remove(second)
            await self._graceful_inflight_shutdown(
                admin,
                schema,
                server,
                port,
                tokens[2],
            )
            servers.remove(server)
            self.check(
                "shutdown releases application connections",
                await self._connection_count(admin, role) == 0,
                active_connections=await self._connection_count(admin, role),
            )
        finally:
            for process in servers:
                if process.returncode is None:
                    process.kill()
                    await process.wait()
            await admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = $1",
                role,
            )
            await admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await admin.execute(f'DROP ROLE IF EXISTS "{role}"')
            await admin.close()
            shutil.rmtree(temp_root, ignore_errors=True)

    def _app_environment(
        self,
        *,
        app_dsn: str,
        tenant_a: str,
        tenant_b: str,
        tokens: list[str],
        secret_key: str,
        security_matrix: Path,
    ) -> dict[str, str]:
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in {"PYTHONPATH", "PYTHONHOME"}
        }
        env.update(
            {
                "AKSARA_ENV": "production",
                "AKSARA_DEBUG": "false",
                "AKSARA_SECRET_KEY": secret_key,
                "AKSARA_SUPPRESS_BRAND": "1",
                "AKSARA_MCP_ENABLED": "true",
                "AKSARA_AI_AGENT_TOKEN": tokens[2],
                "AKSARA_MCP_REQUIRE_AUTH": "true",
                "AKSARA_MCP_REQUIRE_SCOPED_TOKENS": "true",
                "AKSARA_MCP_TOKEN_TTL_SECONDS": "900",
                "AKSARA_MCP_REQUIRE_AUDIENCE": "true",
                "AKSARA_MCP_TOKEN_AUDIENCE": "support-desk",
                "AKSARA_MCP_REQUIRE_TENANT_BOUND_TOKENS": "true",
                "AKSARA_MULTI_TENANT": "true",
                "AKSARA_RLS_ENABLED": "true",
                "AKSARA_AI_WRITABLE_FIELDS_REVIEWED": "true",
                "AKSARA_AI_CONSOLE_ENABLED": "false",
                "AKSARA_STUDIO_EXPOSE_IN_PRODUCTION": "false",
                "AKSARA_STUDIO_REQUIRE_AUTH": "true",
                "AKSARA_COOKIE_SECURE": "true",
                "AKSARA_ADMIN_RATE_LIMIT_ENABLED": "true",
                "AKSARA_SECURITY_MATRIX_PATH": str(security_matrix),
                "CORS_ALLOW_ALL_ORIGINS": "false",
                "CORS_ALLOW_CREDENTIALS": "false",
                "AKSARA_TASK_POLL_INTERVAL": "0.05",
                "AKSARA_TASK_RETRY_DELAY": "2.0",
                "DATABASE_URL": app_dsn,
                "SUPPORT_DESK_TENANT_A_ID": tenant_a,
                "SUPPORT_DESK_TENANT_B_ID": tenant_b,
                "SUPPORT_DESK_TENANT_A_TOKEN": tokens[0],
                "SUPPORT_DESK_TENANT_B_TOKEN": tokens[1],
                "SUPPORT_DESK_MCP_TOKEN": tokens[2],
                "SUPPORT_DESK_MCP_TENANT_B_TOKEN": tokens[3],
                "SUPPORT_DESK_MCP_WRONG_AUDIENCE_TOKEN": tokens[4],
                "SUPPORT_DESK_MCP_EXPIRED_TOKEN": tokens[5],
                "SUPPORT_DESK_MCP_TOKEN_EXPIRES_AT": str(
                    int(datetime.now(UTC).timestamp()) + 900
                ),
                "SUPPORT_DESK_MCP_AUDIENCE": "support-desk",
                "SUPPORT_DESK_MCP_APPROVAL_SECRET": secret_key,
                "SUPPORT_DESK_MCP_AUDIT_PATH": str(security_matrix.parent / "mcp-audit.jsonl"),
                "SUPPORT_DESK_MCP_REVOCATION_FILE": str(security_matrix.parent / "mcp-revoked.txt"),
                "SUPPORT_DESK_ENABLE_FAILURE_PROBES": "true",
            }
        )
        return env

    async def _install_wheel(self, python: Path, temp_root: Path) -> None:
        await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-m", "venv", str(python.parent.parent)],
            check=True,
            cwd=temp_root,
            capture_output=True,
            text=True,
        )
        await asyncio.to_thread(
            subprocess.run,
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--quiet",
                "--force-reinstall",
                str(self.wheel),
            ],
            check=True,
            cwd=temp_root,
            capture_output=True,
            text=True,
        )
        result = await asyncio.to_thread(
            subprocess.run,
            [
                str(python),
                "-I",
                "-c",
                "import json, pathlib, aksara; print(json.dumps({'path': str(pathlib.Path(aksara.__file__).resolve()), 'version': aksara.__version__}))",
            ],
            check=True,
            cwd=temp_root,
            capture_output=True,
            text=True,
        )
        installed = json.loads(result.stdout)
        self.check(
            "wheel installed in isolated environment",
            str(temp_root / "venv") in installed["path"],
            version=installed["version"],
            import_location="isolated-venv",
        )

    async def _doctor_checks(
        self,
        python: Path,
        temp_root: Path,
        app_env: dict[str, str],
    ) -> None:
        command = python.parent / "aksara"
        production = await asyncio.to_thread(
            subprocess.run,
            [str(command), "doctor", "production-check", "--release", "--format", "json"],
            cwd=temp_root,
            env=app_env,
            capture_output=True,
            text=True,
        )
        if production.returncode != 0:
            raise RuntimeError(self.redact(production.stderr or production.stdout))
        report = json.loads(production.stdout)
        self.check(
            "Doctor release policy accepts production configuration",
            report["status"] == "pass"
            and report["release_ready"] is True
            and all(item["status"] == "pass" for item in report["results"]),
            policy=report["policy"],
            checks=len(report["results"]),
        )

        launch = await asyncio.to_thread(
            subprocess.run,
            [
                str(python),
                "-I",
                "-c",
                (
                    "import aksara._examples.support_desk as e; "
                    "from pathlib import Path; "
                    "from aksara.launch_check import run_launch_check; "
                    "print(run_launch_check(Path(e.__file__).resolve().parent).to_json())"
                ),
            ],
            cwd=temp_root,
            env=app_env,
            capture_output=True,
            text=True,
        )
        if launch.returncode != 0:
            raise RuntimeError(self.redact(launch.stderr or launch.stdout))
        launch_report = json.loads(launch.stdout)
        checks = {item["name"]: item for item in launch_report["checks"]}
        self.check(
            "Doctor launch inspection sees packaged app and current schema",
            not any(item["status"] == "error" for item in launch_report["checks"])
            and checks["project_detected"]["status"] == "ok"
            and checks["connection"]["status"] == "ok"
            and checks["migrations"]["status"] == "ok"
            and checks["mcp_catalog"]["status"] == "ok",
            readiness=launch_report["status"],
        )

    async def _configuration_checks(
        self,
        python: Path,
        temp_root: Path,
        app_env: dict[str, str],
    ) -> None:
        invalid_env = dict(app_env)
        invalid_env.pop("SUPPORT_DESK_MCP_TOKEN")
        invalid = await asyncio.create_subprocess_exec(
            str(python),
            "-I",
            "-c",
            "import aksara._examples.support_desk.main",
            cwd=temp_root,
            env=invalid_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await invalid.communicate()
        self.check(
            "invalid production configuration fails fast",
            invalid.returncode != 0
            and b"Support desk production configuration is incomplete" in stderr,
            exit_code=invalid.returncode,
        )

        unavailable_env = dict(app_env)
        unavailable_env["DATABASE_URL"] = "postgresql://unavailable:unavailable@127.0.0.1:1/unavailable"
        unavailable_log = temp_root / "database-unavailable.log"
        process = await self._start_server(
            python,
            temp_root,
            unavailable_env,
            _unused_port(),
            unavailable_log,
        )
        code = await asyncio.wait_for(process.wait(), timeout=15)
        self.check("database-unavailable startup fails", code != 0, exit_code=code)

    async def _migration_run(
        self,
        python: Path,
        helper: Path,
        dsn: str,
        stage: str,
        cwd: Path,
    ) -> dict[str, Any]:
        process = await asyncio.create_subprocess_exec(
            str(python),
            "-I",
            str(helper),
            dsn,
            stage,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(self.redact(stderr.decode(errors="replace")))
        return json.loads(stdout)

    async def _runtime_probe(
        self,
        python: Path,
        helper: Path,
        dsn: str,
        tenant_a: str,
        tenant_b: str,
        cwd: Path,
    ) -> dict[str, Any]:
        process = await asyncio.create_subprocess_exec(
            str(python),
            "-I",
            str(helper),
            dsn,
            tenant_a,
            tenant_b,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(self.redact(stderr.decode(errors="replace")))
        return json.loads(stdout)

    async def _durable_probe(
        self,
        python: Path,
        dsn: str,
        tenant_a: str,
        tenant_b: str,
        cwd: Path,
        env: dict[str, str],
    ) -> dict[str, Any]:
        process = await asyncio.create_subprocess_exec(
            str(python),
            "-I",
            str(ROOT / "scripts" / "v070_support_desk_probe.py"),
            dsn,
            tenant_a,
            tenant_b,
            cwd=cwd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(self.redact(stderr.decode(errors="replace")))
        result = json.loads(stdout)
        if not result["passed"]:
            failed = [name for name, passed in result["checks"].items() if not passed]
            raise AssertionError(f"v0.7 installed-wheel durable probe failed: {failed}")
        return result

    async def _grant_application_access(self, admin: asyncpg.Connection, schema: str, role: str) -> None:
        await admin.execute(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"')
        await admin.execute(
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"'
        )
        await admin.execute(
            f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA "{schema}" TO "{role}"'
        )

    async def _start_server(
        self,
        python: Path,
        cwd: Path,
        env: dict[str, str],
        port: int,
        log_path: Path,
    ) -> asyncio.subprocess.Process:
        log = log_path.open("wb")
        process = await asyncio.create_subprocess_exec(
            str(python),
            "-I",
            "-m",
            "uvicorn",
            "aksara._examples.support_desk.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--timeout-graceful-shutdown",
            "10",
            cwd=cwd,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        return process

    async def _wait_ready(self, port: int, *, timeout: float = 10) -> None:
        deadline = asyncio.get_running_loop().time() + timeout
        async with httpx.AsyncClient(timeout=1) as client:
            while asyncio.get_running_loop().time() < deadline:
                try:
                    response = await client.get(f"http://127.0.0.1:{port}/health/ready")
                    if response.status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.05)
        raise TimeoutError(f"support desk server on port {port} did not become ready")

    async def _stop_server(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        process.send_signal(signal.SIGINT)
        try:
            await asyncio.wait_for(process.wait(), timeout=15)
        except TimeoutError:
            process.kill()
            await process.wait()
            raise
        self.check("graceful process shutdown", process.returncode == 0, exit_code=process.returncode)

    async def _crash_server(self, process: asyncio.subprocess.Process) -> None:
        """Stop without lifespan cleanup to simulate a worker/process crash."""
        if process.returncode is None:
            process.kill()
            await process.wait()
        self.check(
            "worker process crash simulated",
            process.returncode is not None and process.returncode < 0,
            exit_code=process.returncode,
        )

    async def _exercise_http(
        self,
        port: int,
        tokens: list[str],
        tenant_a: str,
        tenant_b: str,
    ) -> dict[str, str]:
        base = f"http://127.0.0.1:{port}"
        headers_a = {"Authorization": f"Bearer {tokens[0]}"}
        headers_b = {"Authorization": f"Bearer {tokens[1]}"}
        headers_mcp = {"Authorization": f"Bearer {tokens[2]}"}
        async with httpx.AsyncClient(base_url=base, timeout=5, follow_redirects=False) as client:
            live, ready, admin, studio = await asyncio.gather(
                client.get("/health/live"),
                client.get("/health/ready"),
                client.get("/admin/login/"),
                client.get("/studio/ui"),
            )
            self.check(
                "normal startup health and production surfaces",
                (live.status_code, ready.status_code, admin.status_code, studio.status_code)
                == (200, 200, 200, 404),
                liveness=live.status_code,
                readiness=ready.status_code,
                admin=admin.status_code,
                studio=studio.status_code,
            )
            anonymous = await client.get("/api/tickets/")
            self.check("generated API rejects anonymous caller", anonymous.status_code == 403)

            agent = await client.post(
                "/api/agents/",
                headers=headers_a,
                json={"name": "Ada Agent", "email": "ada@example.invalid"},
            )
            self.check("generated related-model API", agent.status_code == 201, status=agent.status_code)
            agent_id = agent.json()["id"]
            created_a = await client.post(
                "/api/tickets/",
                headers=headers_a,
                json={
                    "subject": "Tenant A printer",
                    "description": "Printer is offline",
                    "assigned_to_id": agent_id,
                },
            )
            created_b = await client.post(
                "/api/tickets/",
                headers=headers_b,
                json={"subject": "Tenant B network", "description": "Network is slow"},
            )
            self.check(
                "generated CRUD injects authenticated tenants",
                created_a.status_code == 201
                and created_b.status_code == 201
                and created_a.json()["tenant_id"] == tenant_a
                and created_b.json()["tenant_id"] == tenant_b,
                tenant_a_status=created_a.status_code,
                tenant_b_status=created_b.status_code,
            )
            ticket_a = created_a.json()["id"]
            ticket_b = created_b.json()["id"]
            forged = await client.post(
                "/api/tickets/",
                headers=headers_a,
                json={
                    "subject": "Forged tenant",
                    "description": "Must fail",
                    "tenant_id": tenant_b,
                },
            )
            cross = await client.get(f"/api/tickets/{ticket_b}", headers=headers_a)
            list_a, list_b = await asyncio.gather(
                client.get("/api/tickets/", headers=headers_a),
                client.get("/api/tickets/", headers=headers_b),
            )
            subjects_a = {item["subject"] for item in list_a.json()["results"]}
            subjects_b = {item["subject"] for item in list_b.json()["results"]}
            self.check(
                "tenant switching and cross-tenant abuse are isolated",
                forged.status_code in {403, 422}
                and cross.status_code == 404
                and "Tenant B network" not in subjects_a
                and "Tenant A printer" not in subjects_b,
                forged_status=forged.status_code,
                cross_tenant_status=cross.status_code,
            )

            catalog = await client.get("/ai/tools/mcp", headers=headers_mcp)
            self.check("MCP tool catalog is available", catalog.status_code == 200)
            update_tool = next(
                tool for tool in catalog.json()["tools"] if tool["name"] == "ticket_update"
            )
            update_path = update_tool["metadata"]["path"].replace("{pk}", ticket_a)
            mcp_write = await client.patch(
                update_path,
                headers=headers_mcp,
                json={"status": "pending"},
            )
            mcp_cross = await client.patch(
                update_tool["metadata"]["path"].replace("{pk}", ticket_b),
                headers=headers_mcp,
                json={"status": "resolved"},
            )
            self.check(
                "MCP-scoped mutation obeys tenant RLS",
                mcp_write.status_code == 200 and mcp_cross.status_code == 404,
                own_tenant_status=mcp_write.status_code,
                cross_tenant_status=mcp_cross.status_code,
                transport="catalog-described REST operation",
            )

            queued = await client.post(
                f"/api/tickets/{ticket_a}/deliver",
                params={"fail_until_attempt": 1},
                headers=headers_a,
            )
            self.check("tenant-aware task enqueue", queued.status_code == 200, status=queued.status_code)
            task_id = queued.json()["task_id"]
            hidden_task = await client.get(f"/api/tasks/{task_id}", headers=headers_b)
            self.check("task status is tenant-scoped", hidden_task.status_code == 404)
            return {"ticket_a": ticket_a, "ticket_b": ticket_b, "task_id": task_id}

    async def _wait_task_state(
        self,
        port: int,
        token: str,
        task_id: str,
        predicate,
        *,
        timeout: float,
    ) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=2) as client:
            while asyncio.get_running_loop().time() < deadline:
                response = await client.get(
                    f"http://127.0.0.1:{port}/api/tasks/{task_id}",
                    headers=headers,
                )
                if response.status_code == 200 and predicate(response.json()):
                    return response.json()
                await asyncio.sleep(0.03)
        raise TimeoutError(f"task {task_id} did not reach expected state")

    async def _exercise_mcp(
        self,
        python: Path,
        port: int,
        tokens: list[str],
        ids: dict[str, str],
        tenant_a: str,
        tenant_b: str,
        approval_secret: str,
        audit_path: Path,
        revocation_path: Path,
    ) -> None:
        """Use the official MCP client against the wheel-installed running app."""
        import httpx2
        from mcp import Client
        from mcp.client.streamable_http import streamable_http_client

        url = f"http://127.0.0.1:{port}/mcp/"
        token = tokens[2]
        http_client = httpx2.AsyncClient(
            headers={"Authorization": f"Bearer {token}"},
        )
        forbidden_subject = "MCP forged tenant must not persist"
        created_subject = f"MCP persisted {uuid4().hex}"
        async with http_client, Client(
            streamable_http_client(url, http_client=http_client),
            read_timeout_seconds=10,
        ) as client:
                self.check(
                    "official MCP client negotiates protocol",
                    bool(client.protocol_version),
                    protocol_version=client.protocol_version,
                    sdk=f"mcp=={distribution_version('mcp')}",
                    transport="streamable-http",
                )
                listed = await client.list_tools()
                tools = {tool.name: tool for tool in listed.tools}
                expected = {
                    "ticket_list", "ticket_retrieve", "ticket_create",
                    "ticket_update", "ticket_delete",
                }
                self.check(
                    "MCP discovery exposes generated ticket CRUD",
                    expected.issubset(tools) and not any(name.startswith("supportagent_") for name in tools),
                    tools=sorted(tools),
                )
                create_schema = tools["ticket_create"].input_schema
                self.check(
                    "MCP generated schema preserves write contract",
                    set(create_schema.get("required", ())) == {"subject", "description"}
                    and "tenant_id" not in create_schema.get("properties", {})
                    and "created_at" not in create_schema.get("properties", {})
                    and create_schema.get("additionalProperties") is False,
                    required=create_schema.get("required", []),
                    fields=sorted(create_schema.get("properties", {})),
                )

                listed_rows = await client.call_tool("ticket_list", {"limit": 100})
                self.check(
                    "MCP authorized read returns tenant rows",
                    not listed_rows.is_error
                    and all(
                        row["tenant_id"] != "" for row in listed_rows.structured_content["results"]
                    )
                    and not any(
                        row["id"] == ids["ticket_b"]
                        for row in listed_rows.structured_content["results"]
                    ),
                    rows=len(listed_rows.structured_content.get("results", [])),
                )
                created = await client.call_tool(
                    "ticket_create",
                    {
                        "subject": created_subject,
                        "description": "Created through protocol MCP",
                        "priority": "high",
                    },
                    meta={"aksara.run_id": "packaged-reference", "aksara.tool_call_id": "create-one"},
                )
                self.check(
                    "MCP authorized write persists through generated API",
                    not created.is_error and created.structured_content["subject"] == created_subject,
                    error=created.structured_content if created.is_error else None,
                )

                equivalent_subject = f"REST equivalent {uuid4().hex}"
                equivalent_arguments = {
                    "subject": equivalent_subject,
                    "description": "Same generated contract",
                    "priority": "high",
                }
                async with httpx.AsyncClient(timeout=5) as api_client:
                    api_created = await api_client.post(
                        f"http://127.0.0.1:{port}/api/tickets/",
                        headers={"Authorization": f"Bearer {token}"},
                        json=equivalent_arguments,
                    )
                    api_invalid = await api_client.post(
                        f"http://127.0.0.1:{port}/api/tickets/",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"subject": "invalid-without-description"},
                    )
                mcp_equivalent = await client.call_tool("ticket_create", equivalent_arguments)
                mcp_invalid = await client.call_tool(
                    "ticket_create", {"subject": "invalid-without-description"}
                )
                comparable = {"subject", "description", "priority", "status", "tenant_id"}
                self.check(
                    "generated REST and MCP enforce one application contract",
                    api_created.status_code == 201
                    and not mcp_equivalent.is_error
                    and {
                        key: api_created.json()[key] for key in comparable
                    } == {
                        key: mcp_equivalent.structured_content[key] for key in comparable
                    }
                    and api_invalid.status_code == 422
                    and mcp_invalid.is_error
                    and mcp_invalid.structured_content["error"]["code"] == "schema_mismatch",
                    accepted_fields=sorted(comparable),
                    rest_rejected_status=api_invalid.status_code,
                    mcp_rejected_code=mcp_invalid.structured_content.get("error", {}).get("code"),
                )

                malformed_nested = await client.call_tool(
                    "ticket_create",
                    {"subject": "bad nested", "description": {"unexpected": [1, 2]}},
                )
                server_field = await client.call_tool(
                    "ticket_create",
                    {
                        "subject": "bad server field",
                        "description": "must fail",
                        "created_at": "2026-01-01T00:00:00Z",
                    },
                )
                undiscovered = await client.call_tool("supportagent_list", {})
                self.check(
                    "MCP rejects malformed, server-controlled, and undiscovered operations",
                    malformed_nested.is_error
                    and malformed_nested.structured_content["error"]["code"] == "schema_mismatch"
                    and server_field.is_error
                    and server_field.structured_content["error"]["code"] == "forbidden_field"
                    and undiscovered.is_error
                    and undiscovered.structured_content["error"]["code"] == "missing_scope",
                    malformed_code=malformed_nested.structured_content.get("error", {}).get("code"),
                    server_field_code=server_field.structured_content.get("error", {}).get("code"),
                    undiscovered_code=undiscovered.structured_content.get("error", {}).get("code"),
                )

                forged = await client.call_tool(
                    "ticket_create",
                    {
                        "subject": forbidden_subject,
                        "description": "Attempted tenant override",
                        "tenant_id": "00000000-0000-0000-0000-000000000002",
                    },
                )
                self.check(
                    "MCP rejects tenant mass assignment",
                    forged.is_error
                    and forged.structured_content["error"]["code"] == "forbidden_field",
                    error=forged.structured_content,
                )
                cross = await client.call_tool("ticket_retrieve", {"pk": ids["ticket_b"]})
                self.check(
                    "MCP denies cross-tenant object identifier",
                    cross.is_error and cross.structured_content["error"]["code"] == "not_found",
                    error=cross.structured_content,
                )

                revocation_path.write_text("support-desk-mcp\n", encoding="utf-8")
                try:
                    revoked = await client.call_tool(
                        "ticket_update", {"pk": ids["ticket_a"], "status": "resolved"}
                    )
                finally:
                    revocation_path.write_text("", encoding="utf-8")
                self.check(
                    "MCP rechecks authorization after discovery",
                    revoked.is_error
                    and revoked.structured_content["error"]["category"] == "authorization",
                    error=revoked.structured_content,
                )

                replay = await client.call_tool(
                    "ticket_create",
                    {
                        "subject": created_subject,
                        "description": "Created through protocol MCP",
                        "priority": "high",
                    },
                    meta={"aksara.tool_call_id": "create-one"},
                )
                self.check(
                    "MCP rejects replayed tool-call identifier",
                    replay.is_error
                    and replay.structured_content["error"]["code"] == "repeated_tool_request",
                    error=replay.structured_content,
                )

                approval_target = await client.call_tool(
                    "ticket_create",
                    {
                        "subject": f"Approval target {uuid4().hex}",
                        "description": "Removed only after exact approval",
                    },
                )
                delete_id = str(approval_target.structured_content["id"])
                delete_arguments = {"pk": delete_id}
                approval = await self._issue_packaged_approval(
                    python,
                    approval_secret,
                    tenant_a,
                    delete_arguments,
                )
                unapproved = await client.call_tool("ticket_delete", delete_arguments)
                changed = await client.call_tool(
                    "ticket_delete", {"pk": ids["ticket_a"], "_approval_token": approval}
                )
                approved = await client.call_tool(
                    "ticket_delete", {**delete_arguments, "_approval_token": approval}
                )
                self.check(
                    "MCP approval is required and bound to exact principal tenant and arguments",
                    unapproved.is_error
                    and unapproved.structured_content["error"]["code"] == "approval_required"
                    and changed.is_error
                    and changed.structured_content["error"]["code"] == "approval_arguments_mismatch"
                    and not approved.is_error,
                    missing_code=unapproved.structured_content.get("error", {}).get("code"),
                    changed_code=changed.structured_content.get("error", {}).get("code"),
                    approved_by="support-desk-human-reviewer",
                )

                rollback = await client.call_tool("ticket_rollback_probe", {})
                self.check(
                    "failed MCP mutation returns a structured internal error",
                    rollback.is_error
                    and rollback.structured_content["error"]["code"] == "internal_error"
                    and rollback.structured_content["error"]["category"] == "internal",
                    error=rollback.structured_content,
                )

        async with httpx.AsyncClient(timeout=5) as client:
            persisted = await client.get(
                f"http://127.0.0.1:{port}/api/tickets/",
                headers={"Authorization": f"Bearer {token}"},
            )
        subjects = {row["subject"] for row in persisted.json()["results"]}
        self.check(
            "MCP database state reflects allow and deny decisions",
            created_subject in subjects
            and forbidden_subject not in subjects
            and "MCP rollback probe must not persist" not in subjects,
            authorized_persisted=created_subject in subjects,
            forbidden_persisted=forbidden_subject in subjects,
            failed_mutation_rolled_back="MCP rollback probe must not persist" not in subjects,
        )

        async def _tenant_rows(auth_token: str) -> tuple[bool, set[str]]:
            client_http = httpx2.AsyncClient(headers={"Authorization": f"Bearer {auth_token}"})
            async with client_http, Client(
                streamable_http_client(url, http_client=client_http),
                read_timeout_seconds=10,
            ) as concurrent_client:
                    result = await concurrent_client.call_tool("ticket_list", {"limit": 100})
                    return result.is_error, {
                        row["tenant_id"] for row in (result.structured_content or {}).get("results", [])
                    }

        tenant_a_result, tenant_b_result = await asyncio.gather(
            _tenant_rows(tokens[2]), _tenant_rows(tokens[3])
        )
        self.check(
            "concurrent MCP sessions isolate distinct principals and tenants",
            tenant_a_result == (False, {tenant_a})
            and tenant_b_result == (False, {tenant_b}),
            tenant_a=sorted(tenant_a_result[1]),
            tenant_b=sorted(tenant_b_result[1]),
        )

        wrong_audience, expired = await asyncio.gather(
            self._single_mcp_error(url, tokens[4], "ticket_list", {}),
            self._single_mcp_error(url, tokens[5], "ticket_list", {}),
        )
        self.check(
            "MCP rejects wrong-audience and expired credentials at invocation",
            wrong_audience == "wrong_audience" and expired == "credential_expired",
            wrong_audience=wrong_audience,
            expired=expired,
        )

        async with httpx.AsyncClient(timeout=5) as client:
            oversized = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                content=b'{' + b'"padding":"' + (b"x" * 1_048_576) + b'"}',
            )
        self.check(
            "MCP transport rejects oversized request bodies",
            oversized.status_code == 413,
            status=oversized.status_code,
        )

        records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
        rendered = audit_path.read_text(encoding="utf-8")
        self.check(
            "MCP emits correlated redacted execution audits",
            len(records) >= 6
            and any(record["run_id"] == "packaged-reference" for record in records)
            and any(record["outcome"] == "success" for record in records)
            and any(record["error_code"] == "forbidden_field" for record in records)
            and created_subject not in rendered
            and forbidden_subject not in rendered,
            records=len(records),
        )

    async def _single_mcp_error(
        self,
        url: str,
        token: str,
        tool_name: str,
        arguments: dict[str, object],
    ) -> str | None:
        import httpx2
        from mcp import Client
        from mcp.client.streamable_http import streamable_http_client

        http_client = httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"})
        async with http_client, Client(
            streamable_http_client(url, http_client=http_client),
            read_timeout_seconds=10,
        ) as client:
            result = await client.call_tool(tool_name, arguments)
            return (result.structured_content or {}).get("error", {}).get("code")

    async def _issue_packaged_approval(
        self,
        python: Path,
        secret: str,
        tenant_id: str,
        arguments: dict[str, object],
    ) -> str:
        payload = json.dumps(
            {"secret": secret, "tenant_id": tenant_id, "arguments": arguments}
        )
        code = """
import json, sys
from aksara.mcp import ApprovalManager
from aksara.security.principal import Principal
data = json.load(sys.stdin)
principal = Principal.for_mcp_agent(
    token_id='support-desk-mcp',
    human_owner_id='support-mcp-owner',
    agent_id='support-desk-reference-agent',
    tenant_id=data['tenant_id'],
    roles=('mcp',),
    scopes=('mcp:read:ticket', 'mcp:write:ticket'),
    metadata={'audience': 'support-desk'},
)
print(ApprovalManager(data['secret']).issue(
    principal=principal,
    tool_name='ticket_delete',
    arguments=data['arguments'],
    approved_by='support-desk-human-reviewer',
))
"""
        result = await asyncio.to_thread(
            subprocess.run,
            [str(python), "-I", "-c", code],
            input=payload,
            text=True,
            capture_output=True,
            check=True,
        )
        return result.stdout.strip()

    async def _concurrent_requests(
        self,
        first_port: int,
        second_port: int,
        tokens: list[str],
    ) -> None:
        async with httpx.AsyncClient(timeout=8) as client:
            calls = []
            for index in range(24):
                port = first_port if index % 2 else second_port
                token = tokens[index % 2]
                calls.append(
                    client.post(
                        f"http://127.0.0.1:{port}/api/tickets/",
                        headers={"Authorization": f"Bearer {token}"},
                        json={
                            "subject": f"Concurrent {index}",
                            "description": "Bounded concurrency probe",
                        },
                    )
                )
            responses = await asyncio.gather(*calls)
        self.check(
            "concurrent requests across app instances",
            all(response.status_code == 201 for response in responses),
            requests=len(responses),
            instances=2,
        )

    async def _graceful_inflight_shutdown(
        self,
        admin: asyncpg.Connection,
        schema: str,
        process: asyncio.subprocess.Process,
        port: int,
        token: str,
    ) -> None:
        import httpx2
        from mcp import Client
        from mcp.client.streamable_http import streamable_http_client
        from mcp.shared.exceptions import MCPError

        lock_conn = await asyncpg.connect(self.database_url)
        transaction = lock_conn.transaction()
        await transaction.start()
        try:
            await lock_conn.execute(f'SET LOCAL search_path TO "{schema}"')
            await lock_conn.execute("LOCK TABLE support_tickets IN ACCESS EXCLUSIVE MODE")
            http_client = httpx2.AsyncClient(
                headers={"Authorization": f"Bearer {token}"}
            )
            response = None
            call_error = None
            code = None
            request: asyncio.Task[Any] | None = None
            try:
                async with http_client, Client(
                    streamable_http_client(
                        f"http://127.0.0.1:{port}/mcp/", http_client=http_client
                    ),
                    read_timeout_seconds=30,
                ) as client:
                    request = asyncio.create_task(
                        client.call_tool("ticket_list", {"limit": 100})
                    )
                    await asyncio.sleep(0.2)
                    self.check(
                        "MCP invocation is in flight before shutdown",
                        not request.done(),
                    )
                    process.send_signal(signal.SIGINT)
                    await asyncio.sleep(0.2)
                    await transaction.rollback()
                    code = await asyncio.wait_for(process.wait(), timeout=30)
                    try:
                        response = await asyncio.wait_for(request, timeout=5)
                    except asyncio.CancelledError:
                        call_error = "CancelledError"
                    except TimeoutError:
                        call_error = "TimeoutError"
                    except MCPError as exc:
                        call_error = type(exc).__name__
                    except BaseExceptionGroup as exc:
                        call_error = type(exc).__name__
            except BaseExceptionGroup as exc:
                # After the in-flight call completes, the SDK client attempts a
                # session DELETE, or reports cancellation as a grouped error.
                # Uvicorn may already have closed its listener.
                call_error = call_error or type(exc).__name__
            finally:
                if request is not None:
                    if not request.done():
                        request.cancel()
                    outcome = (await asyncio.gather(request, return_exceptions=True))[0]
                    if (
                        response is None
                        and call_error is None
                        and isinstance(outcome, BaseException)
                    ):
                        call_error = type(outcome).__name__
            if code is None:
                code = await asyncio.wait_for(process.wait(), timeout=30)
            self.check(
                "graceful shutdown drains in-flight MCP invocation",
                (response is not None or call_error is not None) and code == 0,
                response_error=response.is_error if response is not None else call_error,
                exit_code=code,
            )
        finally:
            if lock_conn.is_in_transaction():
                await transaction.rollback()
            await lock_conn.close()

    async def _connection_count(self, admin: asyncpg.Connection, role: str) -> int:
        return int(
            await admin.fetchval(
                "SELECT COUNT(*) FROM pg_stat_activity WHERE usename = $1",
                role,
            )
        )


async def _main() -> int:
    args = _parser().parse_args()
    if not args.database_url:
        _parser().error("--database-url or DATABASE_URL is required")
    gate = Gate(
        wheel=args.wheel,
        database_url=args.database_url,
        evidence_output=args.evidence_output,
    )
    try:
        await gate.run()
    except Exception as exc:  # noqa: BLE001 - gate must persist failure evidence
        gate.write_evidence(status="failed", error=f"{type(exc).__name__}: {exc}")
        print(gate.redact(f"FAILED: {type(exc).__name__}: {exc}"), file=sys.stderr)
        return 1
    gate.write_evidence(status="passed")
    print(f"PASS: support desk gate evidence written to {gate.evidence_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
