"""Validate all generated project packages and the basic scaffold journey."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import socket
import subprocess
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from uuid import uuid4

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = (
    ("basic", "northwind_portal"),
    ("blog", "editorial_workspace"),
    ("crm", "customer_workspace"),
    ("multitenant", "tenant_workspace"),
)


def _scoped_database_url(database_url: str, schema: str) -> str:
    parsed = urlsplit(database_url)
    query = dict(parse_qsl(parsed.query))
    query["search_path"] = schema
    return urlunsplit(parsed._replace(query=urlencode(query)))


def _venv_python(environment: Path) -> Path:
    return environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _venv_cli(environment: Path) -> Path:
    return environment / ("Scripts/aksara.exe" if os.name == "nt" else "bin/aksara")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-python", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    database_url = os.environ["DATABASE_URL"]
    schema = "aksara_v072_scaffold_" + uuid4().hex[:12]
    scoped_url = _scoped_database_url(database_url, schema)
    secrets = (database_url, scoped_url)
    base_python = args.base_python.absolute()
    wheel = args.wheel.absolute()
    clean_env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "DATABASE_URL", "AKSARA_DATABASE_URL"}
        and not key.startswith("AKSARA_")
    }

    def redact(value: str) -> str:
        for secret in secrets:
            value = value.replace(secret, "[REDACTED]")
        return re.sub(r"postgres(?:ql)?://[^\s]+", "[REDACTED_DSN]", value)

    async def command(
        argv: list[str | Path],
        cwd: Path,
        *,
        env: dict[str, str] | None = None,
        timeout: int = 180,
    ) -> subprocess.CompletedProcess[str]:
        result = await asyncio.to_thread(
            subprocess.run,
            [str(item) for item in argv],
            cwd=cwd,
            env=env or clean_env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(redact(result.stdout + result.stderr)[-6000:])
        return result

    async def create_candidate_environment(path: Path) -> tuple[Path, Path]:
        await command([base_python, "-m", "venv", path], path.parent)
        python = _venv_python(path)
        await command(
            [
                python,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                wheel,
            ],
            path.parent,
        )
        cli = _venv_cli(path)
        probe = await command(
            [
                python,
                "-I",
                "-c",
                (
                    "import aksara,json; print(json.dumps({"
                    "'version':aksara.__version__,'path':aksara.__file__}))"
                ),
            ],
            path.parent,
        )
        package = json.loads(probe.stdout)
        if Path(package["path"]).is_relative_to(ROOT):
            raise RuntimeError("Scaffold gate imported Aksara from the checkout")
        return python, cli

    template_results: list[dict[str, object]] = []
    basic_result: dict[str, object] = {}
    admin = await asyncpg.connect(database_url)
    server: asyncio.subprocess.Process | None = None

    try:
        await admin.execute(f'CREATE SCHEMA "{schema}"')
        with tempfile.TemporaryDirectory(prefix="aksara-v072-scaffold-") as directory:
            root = Path(directory)
            for template, project_name in TEMPLATES:
                environment = root / f"env-{template}"
                python, cli = await create_candidate_environment(environment)
                await command(
                    [cli, "startproject", project_name, "--template", template],
                    root,
                )
                project = root / project_name
                metadata = (project / "pyproject.toml").read_text()
                if 'requires-python = ">=3.11,<3.15"' not in metadata:
                    raise RuntimeError(f"{template} scaffold has the wrong Python policy")

                await command(
                    [
                        python,
                        "-m",
                        "pip",
                        "install",
                        "--disable-pip-version-check",
                        "-e",
                        ".[dev]",
                    ],
                    project,
                )
                version = await command([cli, "--version"], project)
                if "0.7." not in version.stdout:
                    raise RuntimeError(f"{template} scaffold CLI did not report Aksara")

                if template == "basic":
                    (project / "app/models.py").write_text(
                        "from aksara import Model, fields\n\n"
                        "class ScaffoldItem(Model):\n"
                        "    name = fields.String(max_length=120)\n\n"
                        "    class Meta:\n"
                        "        table_name = 'v072_scaffold_items'\n"
                    )
                    (project / "app/views.py").write_text(
                        "from aksara import ModelViewSet\n"
                        "from aksara.permissions import AllowAny\n"
                        "from .models import ScaffoldItem\n\n"
                        "class ScaffoldItemViewSet(ModelViewSet):\n"
                        "    model = ScaffoldItem\n"
                        "    prefix = '/api/items'\n"
                        "    permission_classes = [AllowAny]\n"
                        "    stream_enabled = False\n"
                    )
                    (project / "app/urls.py").write_text(
                        "from aksara import include_viewset\n"
                        "from .views import ScaffoldItemViewSet\n\n"
                        "urlpatterns = [ScaffoldItemViewSet]\n\n"
                        "def register_routes(app):\n"
                        "    for viewset in urlpatterns:\n"
                        "        include_viewset(app, viewset)\n"
                    )
                    (project / "tests").mkdir(exist_ok=True)
                    (project / "tests/test_generated_project.py").write_text(
                        "def test_generated_application_imports():\n"
                        "    from main import app\n"
                        "    assert app is not None\n"
                    )
                    env_file = project / ".env"
                    env_file.write_text(
                        re.sub(
                            r"^DATABASE_URL=.*$",
                            "DATABASE_URL=" + scoped_url,
                            env_file.read_text(),
                            flags=re.MULTILINE,
                        )
                    )
                    await command(
                        [cli, "makemigrations", "--app", "app.models"],
                        project,
                    )
                    await command([cli, "migrate"], project)
                    tests = await command([python, "-m", "pytest", "-q"], project)
                    if "1 passed" not in tests.stdout:
                        raise RuntimeError("generated scaffold test did not pass")

                    with socket.socket() as sock:
                        sock.bind(("127.0.0.1", 0))
                        port = sock.getsockname()[1]
                    with (root / "basic-server.log").open("w+") as log:
                        server = await asyncio.create_subprocess_exec(
                            str(cli),
                            "run",
                            "main:app",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            str(port),
                            cwd=project,
                            env=clean_env,
                            stdout=log,
                            stderr=log,
                        )

                        def request(
                            path: str,
                            payload: bytes | None = None,
                            server_port: int = port,
                        ) -> tuple[int, str]:
                            req = Request(
                                f"http://127.0.0.1:{server_port}{path}",
                                data=payload,
                                headers={"Content-Type": "application/json"},
                                method="POST" if payload is not None else "GET",
                            )
                            try:
                                response = urlopen(req, timeout=2)
                            except HTTPError as error:
                                response = error
                            with response:
                                return response.status, response.read().decode()

                        for _ in range(120):
                            try:
                                status, _ = await asyncio.to_thread(request, "/health")
                                if status == 200:
                                    break
                            except (OSError, URLError):
                                pass
                            if server.returncode is not None:
                                log.seek(0)
                                raise RuntimeError(redact(log.read())[-6000:])
                            await asyncio.sleep(0.1)
                        else:
                            raise RuntimeError("generated scaffold server did not become ready")

                        health_status, health_body = await asyncio.to_thread(
                            request, "/health"
                        )
                        created_status, created_body = await asyncio.to_thread(
                            request,
                            "/api/items/",
                            b'{"name":"candidate smoke"}',
                        )
                        list_status, list_body = await asyncio.to_thread(
                            request, "/api/items/"
                        )
                        if (health_status, created_status, list_status) != (200, 201, 200):
                            raise RuntimeError("generated scaffold HTTP contract failed")
                        if json.loads(health_body)["status"] != "healthy":
                            raise RuntimeError("generated scaffold health response failed")
                        if json.loads(created_body)["name"] != "candidate smoke":
                            raise RuntimeError("generated scaffold create response failed")
                        if json.loads(list_body)["count"] != 1:
                            raise RuntimeError("generated scaffold list response failed")
                        server.terminate()
                        await asyncio.wait_for(server.wait(), timeout=10)
                        server = None

                    basic_result = {
                        "editable_tests": "1 passed",
                        "makemigrations": True,
                        "migrate": True,
                        "health": 200,
                        "create": 201,
                        "list": 200,
                    }

                wheel_dir = project / "generated-dist"
                wheel_dir.mkdir()
                await command(
                    [
                        python,
                        "-m",
                        "pip",
                        "wheel",
                        "--disable-pip-version-check",
                        "--no-deps",
                        "--wheel-dir",
                        wheel_dir,
                        ".",
                    ],
                    project,
                )
                generated_wheels = list(wheel_dir.glob("*.whl"))
                if len(generated_wheels) != 1:
                    raise RuntimeError(f"{template} did not build exactly one wheel")
                generated_wheel = generated_wheels[0]

                installed_environment = root / f"installed-{template}"
                installed_python, _ = await create_candidate_environment(
                    installed_environment
                )
                await command(
                    [
                        installed_python,
                        "-m",
                        "pip",
                        "install",
                        "--disable-pip-version-check",
                        "--no-deps",
                        generated_wheel,
                    ],
                    root,
                )
                installed_env = dict(clean_env)
                installed_env["DATABASE_URL"] = scoped_url
                import_probe = await command(
                    [
                        installed_python,
                        "-I",
                        "-c",
                        (
                            "import json,main,settings; "
                            "print(json.dumps({'main':main.__file__,"
                            "'settings':settings.__file__}))"
                        ),
                    ],
                    root,
                    env=installed_env,
                )
                imported = json.loads(import_probe.stdout)
                if any(Path(path).is_relative_to(project) for path in imported.values()):
                    raise RuntimeError(f"{template} wheel import used the source project")

                if template == "basic":
                    with socket.socket() as sock:
                        sock.bind(("127.0.0.1", 0))
                        installed_port = sock.getsockname()[1]
                    with (root / "installed-basic-server.log").open("w+") as log:
                        server = await asyncio.create_subprocess_exec(
                            str(installed_python),
                            "-m",
                            "uvicorn",
                            "main:app",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            str(installed_port),
                            cwd=root,
                            env=installed_env,
                            stdout=log,
                            stderr=log,
                        )

                        def installed_request(
                            path: str,
                            server_port: int = installed_port,
                        ) -> tuple[int, str]:
                            try:
                                response = urlopen(
                                    f"http://127.0.0.1:{server_port}{path}",
                                    timeout=2,
                                )
                            except HTTPError as error:
                                response = error
                            with response:
                                return response.status, response.read().decode()

                        for _ in range(120):
                            try:
                                status, _ = await asyncio.to_thread(
                                    installed_request,
                                    "/health",
                                )
                                if status == 200:
                                    break
                            except (OSError, URLError):
                                pass
                            if server.returncode is not None:
                                log.seek(0)
                                raise RuntimeError(redact(log.read())[-6000:])
                            await asyncio.sleep(0.1)
                        else:
                            raise RuntimeError(
                                "installed generated wheel server did not become ready"
                            )

                        installed_health, _ = await asyncio.to_thread(
                            installed_request,
                            "/health",
                        )
                        installed_list, installed_list_body = await asyncio.to_thread(
                            installed_request,
                            "/api/items/",
                        )
                        if installed_health != 200 or installed_list != 200:
                            raise RuntimeError("installed generated wheel HTTP failed")
                        if json.loads(installed_list_body)["count"] != 1:
                            raise RuntimeError(
                                "installed generated wheel did not read migrated data"
                            )
                        server.terminate()
                        await asyncio.wait_for(server.wait(), timeout=10)
                        server = None
                    basic_result["installed_wheel_health"] = 200
                    basic_result["installed_wheel_list"] = 200

                template_results.append(
                    {
                        "template": template,
                        "project_name": project_name,
                        "editable_install": True,
                        "wheel": generated_wheel.name,
                        "wheel_sha256": hashlib.sha256(
                            generated_wheel.read_bytes()
                        ).hexdigest(),
                        "installed_import": True,
                        "source_project_imports": False,
                    }
                )
    finally:
        if server is not None and server.returncode is None:
            server.terminate()
            await asyncio.wait_for(server.wait(), timeout=10)
        await admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await admin.close()

    evidence = {
        "schema_version": 1,
        "pass": True,
        "candidate_wheel": wheel.name,
        "candidate_wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "templates": template_results,
        "basic_journey": basic_result,
        "disposable_schema_removed": True,
        "source_checkout_framework_imports": False,
        "credential_free": True,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    serialized = json.dumps(evidence, indent=2) + "\n"
    if any(secret in serialized for secret in secrets):
        raise RuntimeError("Scaffold evidence contains a credential")
    args.output.write_text(serialized)
    print(f"PASS: {len(template_results)} scaffold packages and basic HTTP journey")


if __name__ == "__main__":
    asyncio.run(main())
