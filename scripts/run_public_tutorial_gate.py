"""Execute the progressive ticket-desk files from an independently installed wheel.

Use --python to select a clean virtual environment containing the candidate wheel.
The control process needs asyncpg and a local DATABASE_URL with role/schema DDL.
No source checkout is added to the application environment.
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import hashlib
import json
import os
import re
import secrets
import socket
import subprocess
import tempfile
import textwrap
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from urllib.request import urlopen
from uuid import UUID, uuid4

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
GUIDES = [
    (ROOT / "docs/docs/getting-started/first-project.md", 3),
    (ROOT / "docs/docs/tutorials/ticket-desk.md", 5),
    (ROOT / "docs/docs/tutorials/ticket-desk-tenancy.md", 12),
    (ROOT / "docs/docs/tutorials/ticket-desk-reports.md", 16),
    (ROOT / "docs/docs/tutorials/ticket-desk-durable.md", 22),
]
FILES = re.compile(r'^```python title="([^\"]+)"\n(.*?)^```', re.MULTILINE | re.DOTALL)


def scoped_dsn(dsn: str, schema: str, role: str | None = None, password: str = "") -> str:
    parsed = urlsplit(dsn)
    netloc = parsed.netloc
    if role is not None:
        host = parsed.hostname or "localhost"
        if ":" in host:
            host = f"[{host}]"
        netloc = f"{quote(role)}:{quote(password)}@{host}:{parsed.port or 5432}"
    query = dict(parse_qsl(parsed.query))
    query["search_path"] = schema
    return urlunsplit(parsed._replace(netloc=netloc, query=urlencode(query)))


async def run(args: argparse.Namespace) -> dict:
    dsn = os.environ.get("AKSARA_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("A local PostgreSQL DATABASE_URL is required")
    python = args.python.absolute()
    cli = python.parent / "aksara"
    suffix = uuid4().hex[:12]
    schema, role = f"aksara_v071_docs_{suffix}", f"aksara_v071_reader_{suffix}"
    password, token = secrets.token_hex(24), secrets.token_hex(32)
    admin_dsn = scoped_dsn(dsn, schema)
    app_dsn = scoped_dsn(dsn, schema, role, password)
    secret_values = [dsn, admin_dsn, app_dsn, password, token]

    def redact(text: str) -> str:
        for secret in secret_values:
            text = text.replace(secret, "[REDACTED]")
        return re.sub(r"postgres(?:ql)?://[^\s'\"]+", "[REDACTED_DSN]", text)

    environment = {
        key: value for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "DATABASE_URL", "APP_API_TOKEN"}
        and not key.startswith("AKSARA_")
    }
    environment.update({
        "AKSARA_DATABASE_URL": admin_dsn,
        "AKSARA_MCP_ENABLED": "false",
        "AKSARA_AI_ENABLED": "false",
        "AKSARA_ENABLE_STUDIO": "false",
        "APP_API_TOKEN": token,
        "PYTHONUNBUFFERED": "1",
    })
    for variable in ("APP_TENANT_B_TOKEN", "APP_READER_TOKEN", "APP_UNSCOPED_TOKEN"):
        environment[variable] = secrets.token_hex(32)
        secret_values.append(environment[variable])
    checks = []

    async def command(arguments, cwd, accepted=(0,)):
        result = await asyncio.to_thread(
            subprocess.run, [str(arg) for arg in arguments], cwd=cwd,
            env=environment, capture_output=True, text=True, timeout=45,
        )
        if result.returncode not in accepted:
            raise RuntimeError(redact(result.stdout + result.stderr)[-6000:])
        return result

    server = None
    admin = await asyncpg.connect(dsn)
    created_schema = created_role = False
    try:
        await admin.execute(f'CREATE SCHEMA "{schema}"')
        created_schema = True
        # Generated identifiers/password contain only known alphanumerics.
        await admin.execute(f'CREATE ROLE "{role}" LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD \'{password}\'')
        created_role = True
        with tempfile.TemporaryDirectory(prefix="aksara-v071-tutorial-") as directory:
            temp = Path(directory)
            probe = await command([
                python, "-I", "-c",
                "import aksara,json; print(json.dumps({'version':aksara.__version__, 'path':aksara.__file__}))",
            ], temp)
            installed = json.loads(probe.stdout)
            if Path(installed["path"]).is_relative_to(ROOT):
                raise RuntimeError("Application imports the source checkout, not an installed wheel")
            await command([cli, "--version"], temp)
            await command([cli, "startproject", "ticket_desk"], temp)
            project = temp / "ticket_desk"
            stages = []
            preserved_ticket = None
            for guide, expected_tests in GUIDES:
                files = {}
                migration_operations = None
                for title, source in FILES.findall(guide.read_text()):
                    files[title] = hashlib.sha256(source.encode()).hexdigest()
                    if title == "migration operations (replace)":
                        migration_operations = source
                        continue
                    append = title.endswith(" (append)")
                    relative = title.removesuffix(" (append)")
                    target = project / relative
                    if not target.resolve().is_relative_to(project.resolve()):
                        raise ValueError("Tutorial file must stay inside the project")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open("a" if append else "w") as stream:
                        stream.write("\n" + source if append else source)
                expected = (
                    {"app/models.py", "app/views.py", "app/urls.py", "app/auth.py",
                     "main.py (append)", "tests/test_api.py"}
                    if expected_tests == 3 else
                    {"app/models.py", "app/views.py", "app/urls.py", "app/serializers.py",
                     "tests/test_relations.py"}
                    if expected_tests == 5 else
                    {"app/models.py", "app/views.py", "app/auth.py", "app/permissions.py",
                     "app/serializers.py", "tests/test_api.py", "tests/test_tenants.py",
                     "migration operations (replace)"}
                    if expected_tests == 12 else
                    {"app/tasks.py", "app/reports.py", "main.py (append)", "tests/test_reports.py"}
                    if expected_tests == 16 else
                    {"app/identities.py", "seed_memberships.py", "app/auth.py", "app/operations.py",
                     "main.py", "worker.py", "tests/test_durable.py"}
                )
                if set(files) != expected:
                    raise RuntimeError("Tutorial file contract changed; update the journey deliberately")
                if expected_tests == 22:
                    await command([python, "seed_memberships.py"], project)
                environment["AKSARA_DATABASE_URL"] = admin_dsn
                checks.append("documented files copied without source substitutions")
                migration_args = [cli, "makemigrations", "--app", "app.models"]
                if migration_operations is not None:
                    migration_args.extend(["--name", "tenant_boundary"])
                if expected_tests < 16:
                    await command(migration_args, project)
                if migration_operations is not None:
                    candidates = list((project / "migrations").glob("*_tenant_boundary.py"))
                    if len(candidates) != 1:
                        raise RuntimeError("Expected one generated tenant migration to edit")
                    migration = candidates[0]
                    source = migration.read_text()
                    module = ast.parse(source)
                    migration_class = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "Migration")
                    assignment = next(node for node in migration_class.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "operations" for target in node.targets))
                    lines = source.splitlines(keepends=True)
                    lines[assignment.lineno - 1:assignment.end_lineno] = [textwrap.indent(migration_operations, "    ")]
                    migration.write_text("".join(lines))
                    checks.append("replaced only generated operations block as documented; preserved dependencies")
                if expected_tests < 16:
                    await command([cli, "migrate"], project)
                exists = await admin.fetchval("SELECT to_regclass($1) IS NOT NULL", f"{schema}.tutorial_tickets")
                if not exists:
                    raise RuntimeError("The documented migration did not create the ticket table")
                checks.append("documented migration commands create the table")
                await admin.execute(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"')
                await admin.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"')
                await admin.execute(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA "{schema}" TO "{role}"')
                environment["AKSARA_DATABASE_URL"] = app_dsn
                if migration_operations is not None:
                    restricted = await asyncpg.connect(app_dsn)
                    try:
                        posture = await restricted.fetchrow("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
                        assert not posture["rolsuper"] and not posture["rolbypassrls"]
                        for table in ("tutorial_agents", "tutorial_tickets"):
                            flags = await restricted.fetchrow("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = $1::regclass", f"{schema}.{table}")
                            assert flags["relrowsecurity"] and flags["relforcerowsecurity"]
                            assert await restricted.fetchval(f'SELECT count(*) FROM "{table}"') == 0
                        await restricted.execute("SELECT set_config('aksara.current_tenant_id', $1, false)", "00000000-0000-0000-0000-000000000001")
                        assert await restricted.fetchval("SELECT subject FROM tutorial_tickets WHERE id=$1", UUID(preserved_ticket)) == "Preserve across migration"
                        await restricted.execute("SELECT set_config('aksara.current_tenant_id', $1, false)", "00000000-0000-0000-0000-000000000002")
                        assert await restricted.fetchval("SELECT count(*) FROM tutorial_tickets") == 0
                        try:
                            await restricted.execute("INSERT INTO tutorial_tickets(id, subject, description, resolved, tenant_id) VALUES($1, 'denied', '', false, $2)", uuid4(), UUID("00000000-0000-0000-0000-000000000001"))
                        except asyncpg.InsufficientPrivilegeError:
                            pass
                        else:
                            raise AssertionError("RLS accepted cross-tenant raw insert")
                        checks.append("restricted role and forced RLS verified; missing tenant sees zero rows; cross-tenant raw insert denied")
                    finally:
                        await restricted.close()
                doctor = await command([cli, "doctor", "launch-check"], project, accepted=(0, 1))
                doctor_output = doctor.stdout + doctor.stderr
                warnings = {line.strip().removeprefix("⚠ ") for line in doctor_output.splitlines() if "⚠" in line}
                if "✗" in doctor_output or warnings - {
                    "Studio UI route not registered", "No AI provider configured",
                }:
                    raise RuntimeError("Unexpected Doctor finding: " + redact(doctor_output))
                for required in ("PostgreSQL connection successful", "Migrations are up to date", "app registry loaded"):
                    if required not in doctor_output:
                        raise RuntimeError("Doctor did not confirm " + required)
                if doctor.returncode == 1 and "Launch readiness: PARTIAL" not in doctor_output:
                    raise RuntimeError("Unexpected Doctor exit status")
                with socket.socket() as listener:
                    listener.bind(("127.0.0.1", 0))
                    port = listener.getsockname()[1]
                environment["APP_BASE_URL"] = f"http://127.0.0.1:{port}"
                with (temp / "server.log").open("w+") as log:
                    server = await asyncio.create_subprocess_exec(
                        str(cli), "run", "main:app", "--host", "127.0.0.1", "--port", str(port),
                        cwd=project, env=environment, stdout=log, stderr=log,
                    )
                    for _ in range(100):
                        try:
                            def ready():
                                with urlopen(environment["APP_BASE_URL"] + "/openapi.json", timeout=1) as response:
                                    return response.status == 200
                            if await asyncio.to_thread(ready):
                                break
                        except OSError:
                            pass
                        if server.returncode is not None:
                            log.seek(0)
                            raise RuntimeError(redact(log.read())[-6000:])
                        await asyncio.sleep(0.1)
                    else:
                        raise RuntimeError("Tutorial server did not become ready")
                    if preserved_ticket is not None:
                        await command([
                            python, "-c",
                            ("import sys; sys.path.insert(0, 'tests'); from test_api import call; "
                            f"status, ticket = call('/api/tickets/{preserved_ticket}'); "
                            "assert status == 200, (status, ticket); "
                            "assert ticket['subject'] == 'Preserve across migration'; "
                            "assert ticket['assigned_to_id'] is None"),
                        ], project)
                        checks.append("existing ticket survives additive relation migration with null assignee")
                    result = await command([python, "-m", "unittest", "discover", "-s", "tests", "-v"], project)
                    if f"Ran {expected_tests} tests" not in result.stderr or not result.stderr.rstrip().endswith("OK"):
                        raise RuntimeError("Expected documented public API tests to run")
                    checks.extend(["anonymous request denied", "authenticated create/read/update/delete", "field length rejected"])
                    if preserved_ticket is None:
                        seed = await command([
                            python, "-c",
                            ("import sys; sys.path.insert(0, 'tests'); from test_api import call; "
                            "status, ticket = call('/api/tickets/', 'POST', "
                            "{'subject': 'Preserve across migration'}); "
                            "assert status == 201, (status, ticket); print(ticket['id'])"),
                        ], project)
                        preserved_ticket = str(UUID(seed.stdout.strip()))
                    server.terminate()
                    await asyncio.wait_for(server.wait(), timeout=15)
                    server = None
                stages.append({
                    "guide": str(guide.relative_to(ROOT)),
                    "guide_sha256": hashlib.sha256(guide.read_bytes()).hexdigest(),
                    "files": files, "api_tests_passed": expected_tests,
                    "launch_check_exit": doctor.returncode,
                    "launch_check_output": redact(doctor_output),
                })
            return {
                "schema_version": 2, "stages": stages,
                "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "package_version": installed["version"], "source_checkout_imports": False,
                "checks": checks, "api_tests_passed": sum(stage["api_tests_passed"] for stage in stages),
                "database_role": "NOSUPERUSER NOBYPASSRLS, DML-only application role",
                "scope": "First-project, relationships, tenant-isolation, queued-report and durable-action chapters, sequential migrations in one schema. Test count includes repeated earlier regressions. Ordinary tasks, protected CSV export and explicit durable action success/retry/cancellation/reauthorization are covered. No external provider, full crash campaign or production-upgrade claim.",
                "pass": True,
            }
    finally:
        if server is not None and server.returncode is None:
            server.terminate()
            try:
                await asyncio.wait_for(server.wait(), timeout=10)
            except TimeoutError:
                server.kill()
                await server.wait()
        if created_schema:
            await admin.execute(f'DROP SCHEMA "{schema}" CASCADE')
        if created_role:
            await admin.execute(f'DROP ROLE "{role}"')
        await admin.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True, help="Python in a clean installed-wheel environment")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = asyncio.run(run(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"PASS: {result['api_tests_passed']} public API tests; package {result['package_version']}")


if __name__ == "__main__":
    main()
