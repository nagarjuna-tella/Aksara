"""Execute the exact documented filtered ViewSet over HTTP with an installed wheel and PostgreSQL."""

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
SNIPPETS = {"models.py": ("docs/docs/getting-started/first-project.md", "app/models.py"),
            "views.py": ("docs/docs/api/filtering.md", "app/search_views.py")}
PROBE = r'''
import asyncio, json, os, sys, types
from pathlib import Path
from uuid import uuid4
import aksara
import httpx
from fastapi import FastAPI
from aksara import include_viewset
from aksara.db import Database
from aksara.migrations.autodetector import model_to_create_table_operation
from aksara.testing import create_test_user
sys.modules['app']=types.ModuleType('app')
module=types.ModuleType('app.models');exec(Path('models.py').read_text(),module.__dict__)
sys.modules['app.models']=module
Ticket=module.Ticket
namespace={'__name__':'app.search_views','__package__':'app'}
exec(Path('views.py').read_text(),namespace)
app=FastAPI()
@app.middleware('http')
async def fixture_identity(request,call_next):
    request.state.user=create_test_user(id=uuid4()) if request.headers.get('authorization')=='Fixture authenticated' else None
    return await call_next(request)
include_viewset(app,namespace['TicketViewSet'])
checks=[]
def passed(name,condition):
    assert condition,name
    checks.append(name)
async def main():
    db=Database(os.environ['DATABASE_URL'],min_size=1,max_size=2)
    await db.connect()
    try:
        await model_to_create_table_operation(Ticket).apply(db)
        await Ticket.objects.create(subject='Login help',description='Browser')
        await Ticket.objects.create(subject='Printer issue',description='Office')
        await Ticket.objects.create(subject='Closed login',description='Browser',resolved=True)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            response=await client.get('/api/tickets/')
            passed('anonymous generated list denied',response.status_code==403)
            client.headers['Authorization']='Fixture authenticated'
            response=await client.get('/api/tickets/')
            data=response.json()
            passed('default ordered envelope',response.status_code==200 and data['count']==3 and [r['subject'] for r in data['results']]==['Closed login','Login help','Printer issue'] and data['limit']==20 and data['offset']==0)
            response=await client.get('/api/tickets/',params={'resolved':'false'})
            passed('boolean filtering',response.status_code==200 and response.json()['count']==2 and all(not r['resolved'] for r in response.json()['results']))
            response=await client.get('/api/tickets/',params={'search':'login'})
            passed('direct text search',response.status_code==200 and response.json()['count']==2)
            response=await client.get('/api/tickets/',params={'resolved':'false','search':'login','ordering':'-subject'})
            passed('combined documented filters',response.status_code==200 and [r['subject'] for r in response.json()['results']]==['Login help'])
            response=await client.get('/api/tickets/',params={'ordering':'-subject'})
            passed('descending ordering',response.status_code==200 and [r['subject'] for r in response.json()['results']]==['Printer issue','Login help','Closed login'])
            response=await client.get('/api/tickets/',params={'subject':'Printer issue'})
            passed('router filter allowlist excludes subject',response.status_code==200 and response.json()['count']==3)
            response=await client.get('/api/tickets/',params={'limit':1,'offset':1})
            passed('paginated filtered count and slice',response.status_code==200 and response.json()['count']==3 and [r['subject'] for r in response.json()['results']]==['Login help'])
            for params in ({'limit':0},{'limit':101},{'offset':-1}):
                response=await client.get('/api/tickets/',params=params)
                assert response.status_code==422
            passed('pagination bounds rejected',True)
            response=await client.get('/api/tickets/',params={'ordering':'description'})
            passed('unallowed ordering ignored without rejection',response.status_code==200 and response.json()['count']==3)
        try: await Ticket.objects.search('login',['author__name']).all()
        except ValueError as error:
            passed('relation search path rejected','Unknown search field' in str(error))
        else: raise AssertionError('Unexpected relation search support')
    finally:
        await db.disconnect()
    print('FILTER_DOC_EVIDENCE='+json.dumps({'checks':checks,'package_version':aksara.__version__,'package_path':aksara.__file__}))
asyncio.run(main())
'''


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("AKSARA_DATABASE_URL") or os.environ["DATABASE_URL"]
    schema = "aksara_v071_filters_" + uuid4().hex[:12]
    connection = await asyncpg.connect(dsn)
    try:
        await connection.execute(f'CREATE SCHEMA "{schema}"')
        try:
            url = urlsplit(dsn)
            query = dict(parse_qsl(url.query))
            query["search_path"] = schema
            scoped = urlunsplit(url._replace(query=urlencode(query)))
            env = {k: v for k, v in os.environ.items()
                   if k not in {"PYTHONPATH", "DATABASE_URL"} and not k.startswith("AKSARA_")}
            env["DATABASE_URL"] = scoped
            with tempfile.TemporaryDirectory(prefix="aksara-filter-docs-") as directory:
                root = Path(directory)
                for filename, (page, title) in SNIPPETS.items():
                    text = (ROOT / page).read_text()
                    source = re.search(r'```python title="' + re.escape(title) + r'"\n(.*?)```', text, re.DOTALL).group(1)
                    (root / filename).write_text(source)
                run = await asyncio.to_thread(
                    subprocess.run, [str(args.python.absolute()), "-I", "-c", PROBE],
                    cwd=root, env=env, capture_output=True, text=True, timeout=60, check=False,
                )
                if run.returncode:
                    message = (run.stderr or run.stdout).replace(scoped, "[REDACTED]").replace(dsn, "[REDACTED]")
                    raise RuntimeError(message)
                evidence = json.loads(next(line.removeprefix("FILTER_DOC_EVIDENCE=") for line in run.stdout.splitlines()
                                           if line.startswith("FILTER_DOC_EVIDENCE=")))
                assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
        finally:
            await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
        assert not await connection.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = $1", schema)
    finally:
        await connection.close()
    evidence.update({"schema_version": 1, "pass": True,
                     "source_checkout_framework_imports": False, "disposable_schema_removed": True,
                     "scope": "Exact model/ViewSet with real ASGI requests and PostgreSQL filtering/search/ordering/pagination; synthetic test identity and admin-role fixture, not credential validation, RLS, every coercion or adversarial filter syntax",
                     "page_sha256": {page: hashlib.sha256((ROOT / page).read_bytes()).hexdigest() for page in [*(page for page, _ in SNIPPETS.values()), "docs/docs/api/viewsets.md"]},
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(evidence['checks'])} installed filter-documentation checks; disposable schema removed")


if __name__ == "__main__":
    asyncio.run(main())
