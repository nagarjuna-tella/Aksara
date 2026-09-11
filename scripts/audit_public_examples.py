"""Exercise source example startup against an independently installed framework.

Records observations, including known limitations; a successful audit process is
not a claim that every example is a production-ready application.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ("basic_app", "blog", "crm", "multitenant", "ai_providers")
PROBE = '''
import asyncio, importlib, json
import httpx, aksara
from pathlib import Path

async def main():
    module = importlib.import_module('examples.' + NAME + '.main')
    app = module.app
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url='http://localhost') as client:
            responses = []
            for method, path, payload, headers in REQUESTS:
                response = await client.request(method, path, json=payload, headers=headers)
                responses.append({'method': method, 'path': path, 'status': response.status_code, 'example_key_supplied': bool(headers)})
    print('AUDIT_JSON=' + json.dumps({'package_version': aksara.__version__, 'framework_path': str(Path(aksara.__file__).resolve()), 'startup': 'completed', 'responses': responses}))

asyncio.run(main())
'''


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("AKSARA_DATABASE_URL") or os.environ["DATABASE_URL"]
    python = args.python.absolute()
    connection = await asyncpg.connect(dsn)
    observations = []
    try:
        for name in EXAMPLES:
            schema = "aksara_v071_example_" + uuid4().hex[:12]
            await connection.execute(f'CREATE SCHEMA "{schema}"')
            try:
                parsed = urlsplit(dsn)
                query = dict(parse_qsl(parsed.query)); query["search_path"] = schema
                scoped = urlunsplit(parsed._replace(query=urlencode(query)))
                env = {k: v for k, v in os.environ.items()
                       if not k.startswith(("AKSARA_", "OPENAI_", "ANTHROPIC_", "AZURE_", "OLLAMA_"))
                       and k not in {"DATABASE_URL", "PYTHONPATH", "AI_DEFAULT_PROVIDER"}}
                env.update(DATABASE_URL=scoped, AKSARA_DATABASE_URL=scoped,
                           BLOG_API_KEY="audit-blog-local", CRM_API_KEY="audit-crm-local")
                with tempfile.TemporaryDirectory(prefix="aksara-example-audit-") as raw:
                    root = Path(raw)
                    target = root / "examples" / name
                    target.parent.mkdir()
                    (target.parent / "__init__.py").write_text("")
                    shutil.copytree(ROOT / "examples" / name, target,
                                    ignore=shutil.ignore_patterns("__pycache__", ".venv", ".env"))
                    entry = {"example": name, "files": {
                        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in sorted((ROOT / "examples" / name).rglob("*"))
                        if p.is_file() and (p.suffix in {".py", ".md"})
                    }}

                    async def command(arguments, cwd=root, environment=env):
                        return await asyncio.to_thread(subprocess.run, [str(v) for v in arguments],
                                                       cwd=cwd, env=environment, capture_output=True,
                                                       text=True, timeout=45)

                    migration_results = []
                    if name != "ai_providers":
                        directory = target / "migrations"
                        if not list(directory.glob("[!_]*.py")):
                            generated = await command([python.parent / "aksara", "makemigrations", "--app",
                                                       f"examples.{name}.models", "--output", directory])
                            migration_results.append({"command": "makemigrations", "exit": generated.returncode})
                        applied = await command([python.parent / "aksara", "migrate", "--migrations-dir", directory])
                        migration_results.append({"command": "migrate", "exit": applied.returncode})
                    entry["migrations"] = migration_results
                    requests = [("GET", "/health", None, {}), ("GET", "/openapi.json", None, {})]
                    cases = {
                        "basic_app": ("/api/users/", {"email": "demo@example.com", "name": "Demo User"}, {}),
                        "blog": ("/api/posts/", {"title": "Hello Aksara", "slug": "hello-aksara", "content": "First post", "tags": ["intro"]}, {"X-API-Key": "audit-blog-local"}),
                        "crm": ("/api/customers/", {"name": "Acme Corp", "email": "hello@example.com", "industry": "SaaS"}, {"X-API-Key": "audit-crm-local"}),
                    }
                    if name in cases:
                        path, payload, headers = cases[name]
                        requests.extend([("POST", path, payload, {}), ("POST", path, payload, headers)])
                    if name == "ai_providers":
                        requests.extend([("GET", "/ai/status", None, {}), ("GET", "/ai/providers", None, {})])
                    probe = root / "probe.py"
                    probe.write_text(PROBE.replace("NAME", repr(name)).replace("REQUESTS", repr(requests)))
                    result = await command([python, probe])
                    entry["probe_exit"] = result.returncode
                    marker = next((line.removeprefix("AUDIT_JSON=") for line in result.stdout.splitlines()
                                   if line.startswith("AUDIT_JSON=")), None)
                    if marker:
                        facts = json.loads(marker)
                        assert not Path(facts.pop("framework_path")).is_relative_to(ROOT)
                        entry.update(facts)
                    else:
                        # Record exception class/message only, with connection strings removed.
                        error = (result.stderr or result.stdout).strip().splitlines()
                        entry["error"] = error[-1].replace(scoped, "[REDACTED]").replace(dsn, "[REDACTED]") if error else "No probe result"
                    observations.append(entry)
                    print(name, json.dumps({k: v for k, v in entry.items() if k != "files"}), flush=True)
            finally:
                await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
    finally:
        await connection.close()
    passed = all(
        item["probe_exit"] == 0 and item.get("startup") == "completed"
        and len(item.get("responses", [])) >= 2
        and all(result["exit"] == 0 for result in item["migrations"])
        and all(response["status"] == (403 if response["method"] == "POST" else 200)
                for response in item.get("responses", []))
        for item in observations
    )
    args.output.write_text(json.dumps({"schema_version": 1, "pass": passed,
        "scope": "Local PostgreSQL startup and selected routes; schema-owner credentials, not RLS/security certification; providers not called",
        "source_checkout_framework_imports": False,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "observations": observations}, indent=2) + "\n")
    if not passed:
        raise SystemExit("Example startup or documented denial contract changed; inspect the evidence")


if __name__ == "__main__":
    asyncio.run(main())
