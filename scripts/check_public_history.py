"""Execute the public durable history helper against an installed wheel and PostgreSQL."""

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
SNIPPETS = {"operation_history.py": ("docs/docs/how-to/inspect-durable-history.md", "app/operation_history.py")}
PROBE = r'''
import asyncio, json, os, runpy
from pathlib import Path
from uuid import uuid4
import aksara
from aksara.db import Database
from aksara.migrations import apply_migrations
from aksara.durable import DurableAction, DurableActionRegistry, DurableOperationService, EffectClass, PrincipalReference, AuthorizationDenied, OperationNotFound
from aksara.security.principal import Principal
helper=runpy.run_path('operation_history.py')
checks=[]
def passed(name, value):
    assert value,name
    checks.append(name)
async def denied(name,error,callback):
    try: await callback()
    except error: checks.append(name)
    else: raise AssertionError(name)
async def handler(context,command): return command
async def main():
    db=Database(os.environ['DATABASE_URL'],min_size=1,max_size=2)
    await db.connect()
    try:
        Path('migrations').mkdir()
        result=await apply_migrations(db,Path('migrations'),verbose=False)
        passed('internal migrations applied',not result['errors'])
        actions=DurableActionRegistry()
        actions.register(DurableAction(name='history.probe',version='1',handler=handler,effect_class=EffectClass.READ_ONLY,required_scopes=('history:read',)))
        service=DurableOperationService(db,application_namespace='history-guide',actions=actions,retention_seconds=60,idempotency_seconds=60)
        tenant=str(uuid4())
        reference=PrincipalReference(resolver_key='probe',resolver_version='1',identity_namespace='probe',principal_kind='user',subject_id='viewer',tenant_id=tenant)
        viewer=Principal.for_user('viewer',tenant_id=tenant,scopes=('history:read',))
        op=(await service.admit('history.probe','1',{},reference)).operation
        async def inspect(**kwargs):
            return await helper['inspect_operation'](kwargs.pop('service',service),op.id,tenant_id=kwargs.pop('tenant_id',tenant),viewer=kwargs.pop('viewer',viewer),**kwargs)
        initial=await inspect()
        passed('current state and initial transition',initial['state']=='ready' and initial['recent_transitions'][0]['from_state'] is None)
        passed('projection serializes to JSON',bool(json.dumps(initial)))
        await denied('registered action scope checked',AuthorizationDenied,lambda:inspect(viewer=Principal.for_user('viewer',tenant_id=tenant)))
        await denied('different tenant cannot select operation',OperationNotFound,lambda:inspect(tenant_id=str(uuid4())))
        await denied('none is not all tenants',OperationNotFound,lambda:inspect(tenant_id=None))
        other=DurableOperationService(db,application_namespace='other',actions=actions,retention_seconds=60,idempotency_seconds=60)
        await denied('different namespace cannot select operation',OperationNotFound,lambda:inspect(service=other))
        await service.request_cancellation(op.id,tenant_id=tenant,principal=viewer,requester_reference=reference)
        current=await inspect()
        passed('cancellation reflected in state and history',current['state']=='cancelled' and current['recent_transitions'][0]['to_state']=='cancelled')
        passed('history is newest first',current['recent_transitions'][0]['state_version']>current['recent_transitions'][-1]['state_version'])
        passed('limit truncates recent list',len((await inspect(limit=1))['recent_transitions'])==1)
        await denied('zero limit rejected',ValueError,lambda:inspect(limit=0))
        await denied('above maximum limit rejected',ValueError,lambda:inspect(limit=201))
        retired=DurableOperationService(db,application_namespace='history-guide',actions=DurableActionRegistry(),retention_seconds=60,idempotency_seconds=60)
        without_scope=Principal.for_user('another-viewer',tenant_id=tenant)
        passed('retired terminal action permits same tenant read without removed scope',(await inspect(service=retired,viewer=without_scope))['state']=='cancelled')
    finally:
        await db.disconnect()
    print('HISTORY_EVIDENCE='+json.dumps({'checks':checks,'package_version':aksara.__version__,'package_path':aksara.__file__}))
asyncio.run(main())
'''


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("AKSARA_DATABASE_URL") or os.environ["DATABASE_URL"]
    schema = "aksara_v071_history_" + uuid4().hex[:12]
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
            with tempfile.TemporaryDirectory(prefix="aksara-history-docs-") as directory:
                root = Path(directory)
                for filename, (page, title) in SNIPPETS.items():
                    text = (ROOT / page).read_text()
                    source = re.search(r'```python title="' + re.escape(title) + r'"\n(.*?)```', text, re.DOTALL).group(1)
                    (root / filename).write_text(source)
                run = await asyncio.to_thread(
                    subprocess.run, [str(args.python.absolute()), "-I", "-c", PROBE],
                    cwd=root, env=env, capture_output=True, text=True, timeout=60,
                )
                if run.returncode:
                    message = (run.stderr or run.stdout).replace(scoped, "[REDACTED]").replace(dsn, "[REDACTED]")
                    raise RuntimeError(message)
                evidence = json.loads(next(line.removeprefix("HISTORY_EVIDENCE=") for line in run.stdout.splitlines()
                                           if line.startswith("HISTORY_EVIDENCE=")))
                assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
        finally:
            await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
        assert not await connection.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = $1", schema)
    finally:
        await connection.close()
    evidence.update({"schema_version": 1, "pass": True,
                     "source_checkout_framework_imports": False, "disposable_schema_removed": True,
                     "scope": "Installed history helper with PostgreSQL admission/cancellation, scoped reads, limits and retired-action policy; admin-role fixture, not restricted RLS, HTTP authentication, retention campaign or atomic snapshot proof",
                     "page_sha256": {page: hashlib.sha256((ROOT / page).read_bytes()).hexdigest() for page, _ in SNIPPETS.values()},
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(evidence['checks'])} installed history checks; disposable schema removed")


if __name__ == "__main__":
    asyncio.run(main())
