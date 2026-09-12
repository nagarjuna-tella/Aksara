"""Execute the public external effect helper against an installed wheel and PostgreSQL."""

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
SNIPPETS = {"external_notifications.py": ("docs/docs/how-to/handle-external-effects.md", "app/external_notifications.py")}
PROBE = r'''
import asyncio, json, os, runpy
from pathlib import Path
from uuid import uuid4
import aksara
from aksara.db import Database
from aksara.migrations import apply_migrations
from aksara.durable import DurableActionRegistry, DurableOperationService, EffectClass, ExternalOperationExecutor, OperationState, PrincipalReference, PrincipalResolution, PrincipalResolverRegistry
from aksara.security.principal import Principal
helper=runpy.run_path('external_notifications.py')
checks=[]
def passed(name,value):
    assert value,name
    checks.append(name)
class Client:
    def __init__(self): self.calls=[]; self.accepted={}
    async def send(self, request, *, idempotency_key):
        self.calls.append(idempotency_key)
        value=self.accepted.setdefault(idempotency_key, {'message_id':'message-'+str(len(self.accepted)+1)})
        if len(self.calls)==1: raise ConnectionError('simulated acknowledgement loss after acceptance')
        return value
async def main():
    db=Database(os.environ['DATABASE_URL'],min_size=1,max_size=2)
    await db.connect()
    try:
        Path('migrations').mkdir()
        result=await apply_migrations(db,Path('migrations'),verbose=False)
        passed('internal migrations applied',not result['errors'])
        tenant=str(uuid4())
        reference=PrincipalReference(resolver_key='probe',resolver_version='1',identity_namespace='probe',principal_kind='user',subject_id='sender',tenant_id=tenant)
        async def scenario(name, *, recoverable=True, revoked=False):
            client=Client()
            adapter=helper['NotificationAdapter'](client)
            if not recoverable: adapter.supports_idempotency=False
            actions=DurableActionRegistry()
            effect=EffectClass.EXTERNAL_IDEMPOTENT if recoverable else EffectClass.EXTERNAL_NONRETRYABLE
            actions.register(helper['notification_action'](adapter,effect_class=effect))
            resolvers=PrincipalResolverRegistry()
            resolvers.register('probe','1',lambda ref:PrincipalResolution.resolved(Principal.for_user('sender',tenant_id=tenant,scopes=() if revoked else ('tickets:notify',))))
            service=DurableOperationService(db,application_namespace=name,actions=actions,resolvers=resolvers,retention_seconds=60,idempotency_seconds=60)
            operation=(await service.admit('tickets.notify','1',{'message':'Ticket updated'},reference)).operation
            claim=await service.claim(tenant_id=tenant,worker_id='public-probe',operation_id=operation.id)
            assert claim is not None
            executor=ExternalOperationExecutor(service)
            first=await executor.execute(claim)
            if revoked:
                passed('revoked scope prevents provider call',first.state is OperationState.FAILED and not client.calls)
                passed('revoked scope records authorization denial',first.error['code']=='authorization_denied')
            elif not recoverable:
                passed('unsafe recovery fails explicitly',first.state is OperationState.FAILED and first.error['code']=='external_outcome_unknown')
                passed('unknown does not imply unsent',len(client.calls)==1 and len(client.accepted)==1)
                passed('unknown outcome not automatically reclaimed',await service.claim(tenant_id=tenant,worker_id='replacement',operation_id=operation.id) is None)
            else:
                passed('lost acknowledgement schedules retry',first.state is OperationState.READY)
                passed('provider accepted before first response loss',len(client.accepted)==1 and len(client.calls)==1)
                replacement=await service.claim(tenant_id=tenant,worker_id='replacement',operation_id=operation.id)
                assert replacement is not None
                passed('replacement advances fence',replacement.fence>claim.fence)
                completed=await executor.execute(replacement)
                passed('retry succeeds',completed.state is OperationState.SUCCEEDED)
                passed('retry supplies identical downstream key',len(client.calls)==2 and client.calls[0]==client.calls[1])
                passed('simulated provider deduplicates',len(client.accepted)==1)
                passed('public helper result persisted',completed.result=={'message_id':'message-1'})
        await scenario('idempotent-public-guide')
        await scenario('unknown-public-guide',recoverable=False)
        await scenario('revoked-public-guide',revoked=True)
    finally:
        await db.disconnect()
    print('EXTERNAL_EVIDENCE='+json.dumps({'checks':checks,'package_version':aksara.__version__,'package_path':aksara.__file__}))
asyncio.run(main())
'''


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("AKSARA_DATABASE_URL") or os.environ["DATABASE_URL"]
    schema = "aksara_v071_external_" + uuid4().hex[:12]
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
            with tempfile.TemporaryDirectory(prefix="aksara-external-docs-") as directory:
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
                evidence = json.loads(next(line.removeprefix("EXTERNAL_EVIDENCE=") for line in run.stdout.splitlines()
                                           if line.startswith("EXTERNAL_EVIDENCE=")))
                assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
        finally:
            await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
        assert not await connection.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = $1", schema)
    finally:
        await connection.close()
    evidence.update({"schema_version": 1, "pass": True,
                     "source_checkout_framework_imports": False, "disposable_schema_removed": True,
                     "scope": "Installed external helper with PostgreSQL and simulated provider acceptance/acknowledgement loss; admin-role fixture, not real provider, restricted RLS or process-crash proof",
                     "page_sha256": {page: hashlib.sha256((ROOT / page).read_bytes()).hexdigest() for page, _ in SNIPPETS.values()},
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(evidence['checks'])} installed external effect checks; disposable schema removed")


if __name__ == "__main__":
    asyncio.run(main())
