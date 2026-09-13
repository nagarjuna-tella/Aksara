"""Compile and exercise the canonical Ticket Desk TypeScript SDK over HTTP."""

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
from urllib.request import urlopen
from uuid import uuid4

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
PYTHON_FENCES = re.compile(
    r'^```python title="([^\"]+)"\n(.*?)^```',
    re.MULTILINE | re.DOTALL,
)


def _scoped_database_url(database_url: str, schema: str) -> str:
    parsed = urlsplit(database_url)
    query = dict(parse_qsl(parsed.query))
    query["search_path"] = schema
    return urlunsplit(parsed._replace(query=urlencode(query)))


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--tsc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    database_url = os.environ["DATABASE_URL"]
    schema = "aksara_v072_sdk_" + uuid4().hex[:12]
    scoped_url = _scoped_database_url(database_url, schema)
    token = "sdk-gate-" + uuid4().hex
    python = args.python.absolute()
    cli = python.parent / "aksara"
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "DATABASE_URL"} and not key.startswith("AKSARA_")
    }
    env["APP_API_TOKEN"] = token
    secrets = (database_url, scoped_url, token)

    def redact(value: str) -> str:
        for secret in secrets:
            value = value.replace(secret, "[REDACTED]")
        return re.sub(r"postgres(?:ql)?://[^\s]+", "[REDACTED_DSN]", value)

    async def command(
        argv: list[str | Path],
        cwd: Path,
        *,
        timeout: int = 90,
    ) -> subprocess.CompletedProcess[str]:
        result = await asyncio.to_thread(
            subprocess.run,
            [str(item) for item in argv],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(redact(result.stdout + result.stderr)[-5000:])
        return result

    tutorial = ROOT / "docs/docs/getting-started/first-project.md"
    sdk_guide = ROOT / "docs/docs/how-to/typescript-client.md"
    tutorial_files = dict(PYTHON_FENCES.findall(tutorial.read_text()))
    sdk_files = dict(PYTHON_FENCES.findall(sdk_guide.read_text()))
    source_hashes: dict[str, str] = {}
    checks: list[str] = []
    server: asyncio.subprocess.Process | None = None
    admin = await asyncpg.connect(database_url)

    try:
        await admin.execute(f'CREATE SCHEMA "{schema}"')
        with tempfile.TemporaryDirectory(prefix="aksara-v072-sdk-") as directory:
            root = Path(directory)
            package_probe = await command(
                [
                    python,
                    "-I",
                    "-c",
                    (
                        "import aksara,json; "
                        "print(json.dumps({'version':aksara.__version__,"
                        "'path':aksara.__file__}))"
                    ),
                ],
                root,
            )
            package = json.loads(package_probe.stdout)
            package_path = Path(package.pop("path"))
            if package_path.is_relative_to(ROOT):
                raise RuntimeError("SDK gate imported Aksara from the source checkout")

            await command([cli, "startproject", "ticket_desk_sdk_probe"], root)
            project = root / "ticket_desk_sdk_probe"
            for name in ("app/models.py", "app/views.py", "app/urls.py", "app/auth.py"):
                content = tutorial_files[name]
                (project / name).write_text(content)
                source_hashes[name] = hashlib.sha256(content.encode()).hexdigest()

            main_append = tutorial_files["main.py (append)"]
            with (project / "main.py").open("a") as main_file:
                main_file.write("\n" + main_append)
            source_hashes["main.py (append)"] = hashlib.sha256(
                main_append.encode()
            ).hexdigest()

            generator = sdk_files["generate_client.py"]
            (project / "generate_client.py").write_text(generator)
            source_hashes["generate_client.py"] = hashlib.sha256(
                generator.encode()
            ).hexdigest()

            env_file = project / ".env"
            generated_env = env_file.read_text()
            generated_env = re.sub(
                r"^DATABASE_URL=.*$",
                "DATABASE_URL=" + scoped_url,
                generated_env,
                flags=re.MULTILINE,
            )
            env_file.write_text(generated_env)

            await command([cli, "makemigrations", "--app", "app.models"], project)
            await command([cli, "migrate"], project)
            await command([python, "generate_client.py"], project)
            checks.append("canonical Ticket Desk SDK generated from installed package")

            contract = r'''
import { createAksaraClient } from "./api.js";

declare const process: { env: Record<string, string | undefined> };

const baseUrl = process.env.AKSARA_SDK_BASE_URL;
const token = process.env.APP_API_TOKEN;
if (!baseUrl || !token) throw new Error("missing SDK gate configuration");

const requests: Array<{ url: string; method: string }> = [];
const recordingFetch: typeof fetch = async (input, init) => {
  requests.push({ url: String(input), method: init?.method ?? "GET" });
  return fetch(input, init);
};
const client = createAksaraClient({
  baseUrl,
  headers: { Authorization: `Bearer ${token}` },
  fetch: recordingFetch,
});

const first = await client.createTicket({ subject: "Printer offline" });
const second = await client.createTicket({
  subject: "Network offline",
  description: "Third floor",
});
const loaded = await client.getTicket(first.id);
if (loaded.subject !== "Printer offline") throw new Error("detail response mismatch");
const updated = await client.updateTicket(first.id, { resolved: true });
if (!updated.resolved) throw new Error("update response mismatch");

const filtered = await client.listTickets({
  limit: 1,
  offset: 0,
  resolved: true,
});
if (filtered.count !== 1 || filtered.results[0]?.id !== first.id) {
  throw new Error("filtered list response mismatch");
}
const next = await client.listTickets({ limit: 1, offset: 1 });
if (next.limit !== 1 || next.offset !== 1 || next.results.length !== 1) {
  throw new Error("paginated list response mismatch");
}
const queryUrl = requests.find((item) => item.url.includes("resolved=true"))?.url;
if (!queryUrl || !queryUrl.includes("limit=1") || !queryUrl.includes("offset=0")) {
  throw new Error("query serialization mismatch");
}

await client.deleteTicket(first.id);
await client.deleteTicket(second.id);
console.log(JSON.stringify({
  create: true,
  detail: true,
  update: true,
  list: true,
  pagination: true,
  filter_query: true,
  request_count: requests.length,
}));
'''
            (project / "contract.ts").write_text(contract)
            (project / "package.json").write_text('{"type":"module"}\n')
            compiler = await command([args.tsc, "--version"], project)
            await command(
                [
                    args.tsc,
                    "--strict",
                    "--lib",
                    "ES2022,DOM",
                    "--target",
                    "ES2022",
                    "--module",
                    "NodeNext",
                    "--moduleResolution",
                    "NodeNext",
                    "--outDir",
                    "compiled",
                    "api.ts",
                    "contract.ts",
                ],
                project,
            )
            checks.append("TypeScript strict compilation passed")

            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            env["AKSARA_SDK_BASE_URL"] = f"http://127.0.0.1:{port}"
            with (root / "server.log").open("w+") as server_log:
                server = await asyncio.create_subprocess_exec(
                    str(cli),
                    "run",
                    "main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    cwd=project,
                    env=env,
                    stdout=server_log,
                    stderr=server_log,
                )

                def health_status() -> int:
                    try:
                        with urlopen(
                            f"http://127.0.0.1:{port}/health",
                            timeout=1,
                        ) as response:
                            return response.status
                    except HTTPError as error:
                        return error.code

                for _ in range(120):
                    try:
                        if await asyncio.to_thread(health_status) == 200:
                            break
                    except (OSError, URLError):
                        pass
                    if server.returncode is not None:
                        server_log.seek(0)
                        raise RuntimeError(redact(server_log.read())[-5000:])
                    await asyncio.sleep(0.1)
                else:
                    raise RuntimeError("Ticket Desk SDK HTTP server did not become ready")

                runtime = await command(["node", "compiled/contract.js"], project)
                runtime_result = json.loads(runtime.stdout)
                if not all(
                    runtime_result[key]
                    for key in (
                        "create",
                        "detail",
                        "update",
                        "list",
                        "pagination",
                        "filter_query",
                    )
                ):
                    raise RuntimeError("TypeScript SDK runtime contract failed")
                checks.append("generated client CRUD and query contract passed over HTTP")
                server.terminate()
                await asyncio.wait_for(server.wait(), timeout=10)
                server = None

            evidence = {
                "schema_version": 1,
                "pass": True,
                "package": package,
                "source_checkout_framework_imports": False,
                "typescript_version": compiler.stdout.strip(),
                "compile_command": (
                    "tsc --strict --lib ES2022,DOM --target ES2022 "
                    "--module NodeNext --moduleResolution NodeNext"
                ),
                "compile_exit": 0,
                "runtime": runtime_result,
                "checks": checks,
                "input_sha256": source_hashes,
                "generated_sha256": hashlib.sha256(
                    (project / "api.ts").read_bytes()
                ).hexdigest(),
                "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "disposable_schema_removed": False,
                "credential_free": True,
            }
    finally:
        if server is not None and server.returncode is None:
            server.terminate()
            await asyncio.wait_for(server.wait(), timeout=10)
        await admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await admin.close()

    evidence["disposable_schema_removed"] = True
    serialized = json.dumps(evidence, indent=2) + "\n"
    if any(secret in serialized for secret in secrets):
        raise RuntimeError("SDK evidence contains a credential")
    args.output.write_text(serialized)
    print(f"PASS: {len(checks)} TypeScript SDK checks; disposable schema removed")


if __name__ == "__main__":
    asyncio.run(main())
