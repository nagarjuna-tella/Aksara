"""Prove the documented first-user journey from a built Aksara wheel."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import asyncpg
import httpx

ROOT = Path(__file__).resolve().parent.parent

MODEL_SOURCE = '''from aksara import Model, fields


class Task(Model):
    title = fields.String(max_length=200, ai_description="Short task title")
    done = fields.Boolean(default=False, ai_description="Completion state")

    class Meta:
        table_name = "quickstart_tasks"
        ai_agent_exposed = True
'''

VIEW_SOURCE = '''from aksara import ModelViewSet

from .models import Task


class TaskViewSet(ModelViewSet):
    model = Task
    prefix = "/api/tasks"
    ai_exposed = True
'''

URL_SOURCE = '''from aksara import include_viewset

from .views import TaskViewSet


urlpatterns = [TaskViewSet]


def register_routes(app):
    for viewset in urlpatterns:
        include_viewset(app, viewset)
'''

AUTH_SOURCE = '''import hmac
import os
from types import SimpleNamespace

from starlette.middleware.base import BaseHTTPMiddleware

from aksara.context_state import tenant_id_var, user_id_var
from aksara.security.principal import Principal


class QuickstartAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        expected = os.environ.get("APP_MCP_TOKEN", "")
        valid = (
            scheme.lower() == "bearer"
            and bool(expected)
            and hmac.compare_digest(token, expected)
        )
        if valid:
            principal = Principal.for_mcp_agent(
                token_id="quickstart-token",
                human_owner_id="quickstart-owner",
                agent_id="quickstart-agent",
                scopes=("mcp:read:task", "mcp:write:task"),
                metadata={
                    "audience": os.getenv(
                        "AKSARA_MCP_TOKEN_AUDIENCE", "task-api"
                    )
                },
            )
        else:
            principal = Principal.anonymous()

        user = SimpleNamespace(
            id=principal.human_owner_id,
            is_authenticated=principal.is_authenticated,
            is_staff=False,
            is_superuser=False,
        )
        request.state.user = user
        request.state.principal = principal
        request.state.tenant_id = principal.tenant_id
        request.state.auth_method = principal.auth_method
        request.state.is_ai_agent = principal.is_ai_agent
        tenant_token = tenant_id_var.set(principal.tenant_id)
        user_token = user_id_var.set(principal.human_owner_id)
        try:
            return await call_next(request)
        finally:
            user_id_var.reset(user_token)
            tenant_id_var.reset(tenant_token)
'''

MCP_PROBE = '''import asyncio
import json
import sys

import httpx
from mcp import Client
from mcp.client.streamable_http import streamable_http_client


async def main():
    endpoint, token, title = sys.argv[1:4]
    http_client = httpx.AsyncClient(
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    async with http_client, Client(
        streamable_http_client(endpoint, http_client=http_client)
    ) as client:
        tools = await client.list_tools()
        names = sorted(tool.name for tool in tools.tools)
        result = await client.call_tool(
            "task_create",
            {"title": title, "done": False},
        )
        print(json.dumps({
            "tools": names,
            "is_error": bool(result.is_error),
            "content_blocks": len(result.content),
        }, sort_keys=True))


asyncio.run(main())
'''

SNIPPET_PROBE = '''from aksara import Model, ModelViewSet, configure, fields, include_viewset
from aksara.security.principal import Principal
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

assert Model and ModelViewSet and configure and fields and include_viewset
assert Principal and Client and streamable_http_client
'''


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument(
        "--database-url",
        default=os.getenv("AKSARA_DATABASE_URL") or os.getenv("DATABASE_URL"),
        help="Administrative PostgreSQL URL (or set AKSARA_DATABASE_URL/DATABASE_URL)",
    )
    parser.add_argument(
        "--candidate-sha",
        default=os.getenv("GITHUB_SHA"),
        help="Commit represented by the wheel; defaults to git HEAD",
    )
    parser.add_argument(
        "--evidence-output",
        type=Path,
        default=ROOT / "audit-evidence" / "v070" / "installed-package-gate.json",
    )
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _schema_dsn(base: str, schema: str, application_name: str) -> str:
    parsed = urlsplit(base)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update(
        {
            "application_name": application_name,
            "options": f"-csearch_path={schema}",
        }
    )
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class InstalledPackageGate:
    def __init__(
        self,
        *,
        wheel: Path,
        database_url: str,
        candidate_sha: str,
        evidence_output: Path,
    ) -> None:
        self.wheel = wheel.resolve()
        self.database_url = database_url
        self.candidate_sha = candidate_sha
        self.evidence_output = evidence_output.resolve()
        self.started_at = datetime.now(UTC)
        self.checks: list[dict[str, Any]] = []
        self.results: dict[str, Any] = {}
        self.secrets: list[str] = [database_url]

    def check(self, name: str, condition: bool, **details: Any) -> None:
        self.checks.append(
            {
                "name": name,
                "status": "pass" if condition else "fail",
                "details": details,
            }
        )
        if not condition:
            raise AssertionError(f"installed-package gate failed: {name}")

    def redact(self, value: str) -> str:
        redacted = value
        for secret in self.secrets:
            if secret:
                redacted = redacted.replace(secret, "[REDACTED]")
        return redacted

    def write_evidence(self, status: str, error: str | None = None) -> None:
        payload = {
            "schema_version": 1,
            "gate": "v070-installed-package-truth",
            "status": status,
            "candidate_sha": self.candidate_sha,
            "started_at": self.started_at.isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
            "artifact": {
                "filename": self.wheel.name,
                "sha256": _sha256(self.wheel) if self.wheel.is_file() else None,
            },
            "environment": self.results.get("environment", {}),
            "package_version": self.results.get("package_version"),
            "results": {
                key: value
                for key, value in self.results.items()
                if key not in {"environment", "package_version"}
            },
            "checks": self.checks,
            "error": self.redact(error) if error else None,
        }
        self.evidence_output.parent.mkdir(parents=True, exist_ok=True)
        self.evidence_output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    async def command(
        self,
        args: list[str | Path],
        *,
        cwd: Path,
        env: dict[str, str],
        accepted_codes: tuple[int, ...] = (0,),
    ) -> subprocess.CompletedProcess[str]:
        result = await asyncio.to_thread(
            subprocess.run,
            [str(item) for item in args],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode not in accepted_codes:
            output = self.redact(result.stderr or result.stdout)
            raise RuntimeError(
                f"command failed ({result.returncode}): {args[0]}\n{output[-4000:]}"
            )
        return result

    async def run(self) -> None:
        if not self.wheel.is_file():
            raise FileNotFoundError(self.wheel)
        if not self.database_url:
            raise RuntimeError("--database-url or a database URL environment variable is required")

        suffix = uuid4().hex[:10]
        schema = f"aksara_v061_{suffix}"
        application_name = f"aksara-v061-gate-{suffix}"
        app_dsn = _schema_dsn(self.database_url, schema, application_name)
        token = uuid4().hex + uuid4().hex
        created_title = f"installed-wheel-{suffix}"
        self.secrets.extend([app_dsn, token])

        temp_root = Path(tempfile.mkdtemp(prefix="aksara-v061-gate-"))
        venv = temp_root / "venv"
        python = venv / "bin" / "python"
        cli = venv / "bin" / "aksara"
        project = temp_root / "truth_app"
        server: asyncio.subprocess.Process | None = None
        server_log = temp_root / "server.log"
        log_handle: Any | None = None
        admin: asyncpg.Connection | None = None

        clean_env = {
            key: value
            for key, value in os.environ.items()
            if key not in {"PYTHONHOME", "PYTHONPATH", "DATABASE_URL", "AKSARA_DATABASE_URL"}
        }
        clean_env.update(
            {
                "AKSARA_DATABASE_URL": app_dsn,
                "DATABASE_URL": "postgresql://compatibility-alias.invalid/ignored",
                "AKSARA_DEBUG": "true",
                "AKSARA_POOL_MIN_SIZE": "1",
                "AKSARA_POOL_MAX_SIZE": "3",
                "AKSARA_MCP_ENABLED": "true",
                "AKSARA_MCP_TOKEN_AUDIENCE": "task-api",
                "AKSARA_AI_ENABLED": "false",
                "AKSARA_ENABLE_STUDIO": "false",
                "AKSARA_SUPPRESS_BRAND": "1",
                "APP_MCP_TOKEN": token,
                "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                "PYTHONUNBUFFERED": "1",
            }
        )

        try:
            admin = await asyncpg.connect(self.database_url)
            postgres_version = await admin.fetchval("SHOW server_version")
            await admin.execute(f'CREATE SCHEMA "{schema}"')
            self.results["environment"] = {
                "gate_python": sys.version.split()[0],
                "postgresql": str(postgres_version),
                "database": urlsplit(self.database_url).path.lstrip("/"),
                "isolated_schema": True,
            }

            await self.command([sys.executable, "-m", "venv", venv], cwd=temp_root, env=clean_env)
            await self.command(
                [python, "-m", "pip", "install", "--quiet", "--force-reinstall", self.wheel],
                cwd=temp_root,
                env=clean_env,
            )

            import_probe = await self.command(
                [
                    python,
                    "-I",
                    "-c",
                    (
                        "import json,pathlib,aksara; "
                        "print(json.dumps({'version':aksara.__version__,"
                        "'path':str(pathlib.Path(aksara.__file__).resolve())}))"
                    ),
                ],
                cwd=temp_root,
                env=clean_env,
            )
            installed = json.loads(import_probe.stdout)
            self.results["package_version"] = installed["version"]
            self.check(
                "wheel import comes from isolated environment",
                str(venv) in installed["path"] and str(ROOT) not in installed["path"],
                import_location="isolated-venv",
                version=installed["version"],
            )
            self.check(
                "candidate package version",
                installed["version"] == "0.7.1rc1",
                version=installed["version"],
            )

            version_result = await self.command([cli, "--version"], cwd=temp_root, env=clean_env)
            help_result = await self.command([cli, "--help"], cwd=temp_root, env=clean_env)
            self.check(
                "CLI version and commands",
                "0.7.1rc1" in version_result.stdout
                and "startproject" in help_result.stdout
                and "doctor" in help_result.stdout,
                version="0.7.1rc1",
                startproject=True,
                doctor=True,
            )
            self.results["cli"] = {
                "version": "0.7.1rc1",
                "help": "pass",
                "startproject_command": True,
                "doctor_command": True,
            }

            await self.command(
                [cli, "startproject", "truth_app", "--directory", temp_root],
                cwd=temp_root,
                env=clean_env,
            )
            (project / "app" / "models.py").write_text(MODEL_SOURCE, encoding="utf-8")
            (project / "app" / "views.py").write_text(VIEW_SOURCE, encoding="utf-8")
            (project / "app" / "urls.py").write_text(URL_SOURCE, encoding="utf-8")
            (project / "app" / "auth.py").write_text(AUTH_SOURCE, encoding="utf-8")
            (project / ".env").write_text(
                """# Values are supplied by the installed-package gate environment.
AKSARA_MCP_ENABLED=true
AKSARA_MCP_TOKEN_AUDIENCE=task-api
AKSARA_AI_ENABLED=false
AKSARA_ENABLE_STUDIO=false
""",
                encoding="utf-8",
            )
            main_path = project / "main.py"
            main_source = main_path.read_text(encoding="utf-8")
            main_source = main_source.replace(
                "from settings import settings, INSTALLED_APPS\n",
                "from settings import settings, INSTALLED_APPS\nfrom app.auth import QuickstartAuthMiddleware\n",
                1,
            )
            main_source = main_source.replace(
                "# Register routes from app/urls.py\nregister_routes(app)",
                (
                    "# Resolve application credentials before REST or MCP execution.\n"
                    "app.add_middleware(QuickstartAuthMiddleware)\n\n"
                    "# Register routes from app/urls.py\nregister_routes(app)"
                ),
                1,
            )
            main_path.write_text(main_source, encoding="utf-8")

            for source_path in project.rglob("*.py"):
                compile(source_path.read_text(encoding="utf-8"), str(source_path), "exec")
            scaffold_readme = (project / "README.md").read_text(encoding="utf-8")
            scaffold_settings = (project / "settings.py").read_text(encoding="utf-8")
            self.check(
                "scaffold teaches global configuration and distinct tool surfaces",
                "configure(installed_apps=INSTALLED_APPS)" in scaffold_settings
                and "AKSARA =" not in scaffold_settings
                and "/mcp/" in scaffold_readme
                and "/ai/tools/mcp" in scaffold_readme,
                global_settings=True,
                protocol_path="/mcp/",
                catalog_path="/ai/tools/mcp",
            )
            self.results["project_scaffold"] = {
                "command": "pass",
                "python_compile": "pass",
                "global_settings": True,
                "stable_core_defaults": True,
            }

            snippet_path = temp_root / "snippet_probe.py"
            snippet_path.write_text(SNIPPET_PROBE, encoding="utf-8")
            await self.command([python, "-I", snippet_path], cwd=temp_root, env=clean_env)
            self.check(
                "canonical documentation imports resolve from wheel",
                True,
                source="installed-wheel",
            )
            self.results["docs_snippets"] = {
                "canonical_imports": "pass",
                "source_checkout_imports": False,
            }

            await self.command(
                [cli, "makemigrations", "--app", "app.models"],
                cwd=project,
                env=clean_env,
            )
            migration_files = sorted((project / "migrations").glob("*.py"))
            self.check(
                "model migration generated",
                any(path.name != "__init__.py" for path in migration_files),
                generated_files=len([path for path in migration_files if path.name != "__init__.py"]),
            )
            await self.command([cli, "migrate"], cwd=project, env=clean_env)
            table_exists = await admin.fetchval(
                "SELECT to_regclass($1) IS NOT NULL",
                f"{schema}.quickstart_tasks",
            )
            self.check(
                "PostgreSQL migration applied",
                bool(table_exists),
                table="quickstart_tasks",
                namespaced_database_precedence=True,
            )
            self.results["migration"] = {
                "generation": "pass",
                "application": "pass",
                "table": "quickstart_tasks",
                "database_alias_precedence": "AKSARA_DATABASE_URL",
            }

            app_import = await self.command(
                [
                    python,
                    "-c",
                    (
                        "import json,main; "
                        "print(json.dumps({'title':main.app.title,"
                        "'mcp':main.settings.mcp_enabled,"
                        "'ai':main.settings.ai_enabled,"
                        "'studio':main.settings.enable_studio}))"
                    ),
                ],
                cwd=project,
                env=clean_env,
            )
            imported_app = json.loads(app_import.stdout.splitlines()[-1])
            self.check(
                "generated application imports from installed package",
                imported_app["mcp"] is True
                and imported_app["ai"] is False
                and imported_app["studio"] is False,
                mcp_enabled=True,
                ai_enabled=False,
                studio_enabled=False,
            )

            doctor = await self.command(
                [cli, "doctor", "launch-check", "--format", "json"],
                cwd=project,
                env=clean_env,
                accepted_codes=(0, 1),
            )
            doctor_report = json.loads(doctor.stdout)
            doctor_errors = [
                check for check in doctor_report["checks"] if check["status"] == "error"
            ]
            checks_by_name = {check["name"]: check for check in doctor_report["checks"]}
            self.check(
                "Doctor validates generated project",
                not doctor_errors
                and checks_by_name["connection"]["status"] == "ok"
                and checks_by_name["migrations"]["status"] == "ok"
                and checks_by_name["mcp_catalog"]["status"] == "ok",
                status=doctor_report["status"],
                checks=len(doctor_report["checks"]),
                errors=0,
            )
            self.results["doctor"] = {
                "command": "launch-check --format json",
                "status": doctor_report["status"],
                "checks": len(doctor_report["checks"]),
                "errors": 0,
            }

            port = _unused_port()
            log_handle = server_log.open("wb")
            server = await asyncio.create_subprocess_exec(
                str(python),
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--timeout-graceful-shutdown",
                "10",
                cwd=project,
                env=clean_env,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            await self.wait_ready(port)

            headers = {"Authorization": f"Bearer {token}"}
            async with httpx.AsyncClient(timeout=10, headers=headers) as client:
                health = await client.get(f"http://127.0.0.1:{port}/health")
                openapi = await client.get(f"http://127.0.0.1:{port}/openapi.json")
                initial = await client.get(f"http://127.0.0.1:{port}/api/tasks/")
                catalog = await client.get(f"http://127.0.0.1:{port}/ai/tools/mcp")
            openapi_body = openapi.json()
            initial_body = initial.json()
            catalog_body = catalog.json()
            self.check(
                "generated REST and OpenAPI paths respond",
                health.status_code == 200
                and openapi.status_code == 200
                and initial.status_code == 200
                and any(path.startswith("/api/tasks") for path in openapi_body["paths"]),
                health=health.status_code,
                openapi=openapi.status_code,
                rest_list=initial.status_code,
            )
            self.check(
                "tool inspection catalog is HTTP JSON",
                catalog.status_code == 200
                and "task_create" in {
                    tool["name"] for tool in catalog_body.get("tools", [])
                },
                status=catalog.status_code,
                path="/ai/tools/mcp",
            )
            self.results["rest"] = {
                "health": health.status_code,
                "openapi": openapi.status_code,
                "initial_list": initial.status_code,
                "initial_count": initial_body.get("count", 0),
                "catalog": catalog.status_code,
            }

            mcp_probe_path = temp_root / "mcp_probe.py"
            mcp_probe_path.write_text(MCP_PROBE, encoding="utf-8")
            mcp_result = await self.command(
                [
                    python,
                    "-I",
                    mcp_probe_path,
                    f"http://127.0.0.1:{port}/mcp/",
                    token,
                    created_title,
                ],
                cwd=temp_root,
                env=clean_env,
            )
            mcp_report = json.loads(mcp_result.stdout.splitlines()[-1])
            self.check(
                "official MCP client discovers and invokes generated tool",
                "task_create" in mcp_report["tools"] and not mcp_report["is_error"],
                endpoint="/mcp/",
                tool="task_create",
                discovered_tools=len(mcp_report["tools"]),
                call_error=mcp_report["is_error"],
            )

            async with httpx.AsyncClient(timeout=10, headers=headers) as client:
                persisted = await client.get(f"http://127.0.0.1:{port}/api/tasks/")
            persisted_body = persisted.json()
            records = persisted_body.get("results", persisted_body.get("items", []))
            self.check(
                "MCP mutation is visible through generated REST",
                persisted.status_code == 200
                and any(record.get("title") == created_title for record in records),
                rest_status=persisted.status_code,
                persisted=True,
            )
            self.results["mcp_client"] = {
                "sdk": "official mcp package installed from wheel dependencies",
                "endpoint": "/mcp/",
                "discovery": "pass",
                "tool": "task_create",
                "invocation": "pass",
                "rest_persistence": "pass",
            }

            server.send_signal(signal.SIGINT)
            try:
                await asyncio.wait_for(server.wait(), timeout=20)
            except TimeoutError:
                server.kill()
                await server.wait()
                raise
            self.check(
                "application shuts down cleanly",
                server.returncode == 0,
                exit_code=server.returncode,
            )
            server = None
            await asyncio.sleep(0.1)
            active = await admin.fetchval(
                """
                SELECT COUNT(*) FROM pg_stat_activity
                WHERE application_name = $1 AND pid <> pg_backend_pid()
                """,
                application_name,
            )
            self.check(
                "shutdown releases PostgreSQL connections",
                int(active or 0) == 0,
                active_connections=int(active or 0),
            )
            self.results["shutdown"] = {
                "signal": "SIGINT",
                "exit_code": 0,
                "active_database_connections": 0,
            }
        finally:
            if server is not None and server.returncode is None:
                server.kill()
                await server.wait()
            if log_handle is not None:
                log_handle.close()
            if admin is not None:
                await admin.execute(
                    """
                    SELECT pg_terminate_backend(pid) FROM pg_stat_activity
                    WHERE application_name = $1 AND pid <> pg_backend_pid()
                    """,
                    application_name,
                )
                await admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
                await admin.close()
            shutil.rmtree(temp_root, ignore_errors=True)

    async def wait_ready(self, port: int, timeout: float = 20) -> None:
        deadline = asyncio.get_running_loop().time() + timeout
        async with httpx.AsyncClient(timeout=1) as client:
            while asyncio.get_running_loop().time() < deadline:
                try:
                    response = await client.get(f"http://127.0.0.1:{port}/health")
                    if response.status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.05)
        raise TimeoutError(f"generated application on port {port} did not become ready")


async def _main() -> int:
    args = _parser().parse_args()
    candidate_sha = args.candidate_sha or _git_head()
    gate = InstalledPackageGate(
        wheel=args.wheel,
        database_url=args.database_url,
        candidate_sha=candidate_sha,
        evidence_output=args.evidence_output,
    )
    try:
        await gate.run()
    except BaseException as exc:
        gate.write_evidence("fail", f"{type(exc).__name__}: {exc}")
        raise
    gate.write_evidence("pass")
    print(f"installed-package gate: PASS ({len(gate.checks)} checks)")
    print(f"evidence: {gate.evidence_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
