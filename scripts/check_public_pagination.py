"""Execute the exact documented pagination ViewSet over HTTP with an installed wheel and PostgreSQL."""

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
            "views.py": ("docs/docs/api/pagination.md", "app/pagination_views.py")}
PROBE = r'''
import asyncio, json, os, sys, types
from pathlib import Path
from uuid import UUID
import aksara, httpx
from fastapi import FastAPI, Request
from aksara import include_viewset
from aksara.api.pagination import PageNumberPagination,CursorPagination,LimitOffsetPagination
from aksara.db import Database
from aksara.migrations.autodetector import model_to_create_table_operation
from aksara.testing import create_test_user
sys.modules['app']=types.ModuleType('app')
module=types.ModuleType('app.models');exec(Path('models.py').read_text(),module.__dict__)
sys.modules['app.models']=module;Ticket=module.Ticket
namespace={'__name__':'app.pagination_views','__package__':'app'}
exec(Path('views.py').read_text(),namespace)
Base=namespace['TicketViewSet']
class PageView(Base): prefix='/api/pages';pagination_class=PageNumberPagination
class CursorView(Base): prefix='/api/cursors';pagination_class=CursorPagination
class OffsetView(Base): prefix='/api/offsets';pagination_class=LimitOffsetPagination
app=FastAPI()
@app.middleware('http')
async def identity(request,call_next):
    request.state.user=create_test_user()
    return await call_next(request)
for view in (Base,PageView,CursorView,OffsetView):include_viewset(app,view)
checks=[]
def passed(name,condition):
    assert condition,name
    checks.append(name)
def request(query):
    result=Request({'type':'http','method':'GET','path':'/','query_string':query.encode(),'headers':[]})
    result.state.user=create_test_user()
    return result
async def main():
    db=Database(os.environ['DATABASE_URL'],min_size=1,max_size=2);await db.connect()
    try:
        await model_to_create_table_operation(Ticket).apply(db)
        for n in (1,2,3):await Ticket.objects.create(id=UUID(int=n),subject=str(n))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            response=await client.get('/api/tickets/?limit=1&offset=1');data=response.json()
            passed('documented default pagination works',response.status_code==200 and data['count']==3 and data['limit']==1 and data['offset']==1 and data['results'][0]['subject']=='2')
            response=await client.get('/api/offsets/?limit=1&offset=1')
            passed('explicit limit offset metadata preserved',response.status_code==200 and response.json()==data)
            response=await client.get('/api/pages/?page=2&size=1');data=response.json()
            passed('page number selects second row',response.status_code==200 and data['results'][0]['subject']=='2')
            passed('PAGINATION-001 page metadata discarded',not {'page','size','total_pages'} & data.keys() and data['limit'] is None and data['offset'] is None)
            direct=await PageView().list(request('page=2&size=1'))
            passed('direct view retains page metadata',direct['page']==2 and direct['size']==1 and direct['total_pages']==3)
            direct=await CursorView().list(request('page_size=1'))
            passed('direct view provides next cursor','next_cursor' in direct and direct['results'][0]['subject']=='1')
            response=await client.get('/api/cursors/?page_size=1');data=response.json()
            passed('PAGINATION-001 HTTP next cursor discarded',response.status_code==200 and 'next_cursor' not in data and data['limit'] is None)
            from urllib.parse import urlencode
            next_page=await CursorView().list(request(urlencode({'page_size':1,'cursor':direct['next_cursor']})))
            passed('ascending id cursor advances and counts remaining',next_page['results'][0]['subject']=='2' and next_page['count']==2)
    finally:await db.disconnect()
    print('PAGINATION_DOC_EVIDENCE='+json.dumps({'checks':checks,'package_version':aksara.__version__,'package_path':aksara.__file__}))
asyncio.run(main())
'''


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("AKSARA_DATABASE_URL") or os.environ["DATABASE_URL"]
    schema = "aksara_v071_pagination_" + uuid4().hex[:12]
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
            with tempfile.TemporaryDirectory(prefix="aksara-pagination-docs-") as directory:
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
                evidence = json.loads(next(line.removeprefix("PAGINATION_DOC_EVIDENCE=") for line in run.stdout.splitlines()
                                           if line.startswith("PAGINATION_DOC_EVIDENCE=")))
                assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
        finally:
            await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
        assert not await connection.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = $1", schema)
    finally:
        await connection.close()
    evidence.update({"schema_version": 1, "pass": True, "runtime_custom_pagination_metadata_pass": False,
                     "source_checkout_framework_imports": False, "disposable_schema_removed": True,
                     "scope": "Default/limit-offset success and reproduced page/cursor response metadata loss through real HTTP versus direct calls; synthetic identity, admin role, not credential validation, RLS, concurrency or performance proof",
                     "page_sha256": {page: hashlib.sha256((ROOT / page).read_bytes()).hexdigest() for page in [*(page for page, _ in SNIPPETS.values()), "docs/docs/api/viewsets.md"]},
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(evidence['checks'])} installed pagination-documentation checks; disposable schema removed")


if __name__ == "__main__":
    asyncio.run(main())
