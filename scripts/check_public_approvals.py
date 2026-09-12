"""Execute the public durable approval helper against an installed wheel and PostgreSQL."""

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
SNIPPETS = {"approval_decisions.py": ("docs/docs/how-to/require-durable-approval.md", "app/approval_decisions.py")}
PROBE = r'''
import asyncio, json, os, runpy
from pathlib import Path
from datetime import UTC, datetime, timedelta
from uuid import uuid4
import aksara
from aksara.db import Database
from aksara.migrations import apply_migrations
from aksara.durable import DurableAction, DurableActionRegistry, DurableOperationService, EffectClass, PrincipalReference, OperationState, AuthorizationDenied, ApprovalConflict, OperationNotFound
from aksara.security.principal import Principal
helper=runpy.run_path('approval_decisions.py')
checks=[]
def passed(name, value):
    assert value, name
    checks.append(name)
async def denied(name, error, callback):
    try:
        await callback()
    except error:
        checks.append(name)
    else:
        raise AssertionError(name)
async def handler(context, command): return command
async def main():
    db=Database(os.environ['DATABASE_URL'], min_size=1, max_size=2)
    await db.connect()
    try:
        Path('migrations').mkdir()
        result=await apply_migrations(db, Path('migrations'), verbose=False)
        passed('internal migrations applied', not result['errors'])
        actions=DurableActionRegistry()
        actions.register(DurableAction(name='tickets.review',version='1',handler=handler,effect_class=EffectClass.READ_ONLY,required_scopes=('tickets:write',),approval_required=True,approval_authorizer=helper['can_review_ticket']))
        service=DurableOperationService(db,application_namespace='approval-guide',actions=actions,retention_seconds=60,idempotency_seconds=60)
        tenant=str(uuid4())
        def ref(subject):
            return PrincipalReference(resolver_key='probe',resolver_version='1',identity_namespace='probe',principal_kind='user',subject_id=subject,tenant_id=tenant)
        reviewer=Principal.for_user('reviewer',tenant_id=tenant,roles=('ticket-reviewer',),scopes=('tickets:write',))
        async def admit(**kwargs):
            return (await service.admit('tickets.review','1',{},ref('requester'),**kwargs)).operation
        async def decide(op, principal=reviewer, reference=None, scope=tenant, approve=True):
            return await helper['decide_ticket'](service,op.id,tenant_id=scope,current_approver=principal,approver_reference=reference or ref('reviewer'),approve=approve,reason='public helper probe')
        op=await admit()
        passed('admission waits for approval',op.state is OperationState.WAITING_FOR_APPROVAL)
        passed('waiting operation cannot be claimed',await service.claim(tenant_id=tenant,worker_id='probe',operation_id=op.id) is None)
        await denied('reviewer role required',AuthorizationDenied,lambda:decide(op,Principal.for_user('reviewer',tenant_id=tenant,scopes=('tickets:write',))))
        await denied('action scopes still required',AuthorizationDenied,lambda:decide(op,Principal.for_user('reviewer',tenant_id=tenant,roles=('ticket-reviewer',))))
        await denied('provenance must match',AuthorizationDenied,lambda:decide(op,reference=ref('another')))
        await denied('other tenant cannot select operation',OperationNotFound,lambda:decide(op,scope=str(uuid4())))
        approved=await decide(op)
        passed('approval returns ready',approved.state is OperationState.READY)
        await denied('second decision conflicts',ApprovalConflict,lambda:decide(op,approve=False))
        passed('approved operation can be claimed',await service.claim(tenant_id=tenant,worker_id='probe',operation_id=op.id) is not None)
        rejected=await decide(await admit(),approve=False)
        passed('rejection returns cancelled',rejected.state is OperationState.CANCELLED)
        expiring=await admit(approval_expires_at=datetime.now(UTC)+timedelta(seconds=0.2))
        await asyncio.sleep(0.3)
        passed('expired approval returns expired',(await decide(expiring)).state is OperationState.EXPIRED)
    finally:
        await db.disconnect()
    print('APPROVAL_EVIDENCE='+json.dumps({'checks':checks,'package_version':aksara.__version__,'package_path':aksara.__file__}))
asyncio.run(main())
'''


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("AKSARA_DATABASE_URL") or os.environ["DATABASE_URL"]
    schema = "aksara_v071_approval_" + uuid4().hex[:12]
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
            with tempfile.TemporaryDirectory(prefix="aksara-approval-docs-") as directory:
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
                evidence = json.loads(next(line.removeprefix("APPROVAL_EVIDENCE=") for line in run.stdout.splitlines()
                                           if line.startswith("APPROVAL_EVIDENCE=")))
                assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
        finally:
            await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
        assert not await connection.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = $1", schema)
    finally:
        await connection.close()
    evidence.update({"schema_version": 1, "pass": True,
                     "source_checkout_framework_imports": False, "disposable_schema_removed": True,
                     "scope": "Installed approval helper with real PostgreSQL admission, policy, decisions and expiry; admin-role fixture, not restricted-role RLS, HTTP authentication, worker execution or process-crash proof",
                     "page_sha256": {page: hashlib.sha256((ROOT / page).read_bytes()).hexdigest() for page, _ in SNIPPETS.values()},
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(evidence['checks'])} installed approval checks; disposable schema removed")


if __name__ == "__main__":
    asyncio.run(main())
