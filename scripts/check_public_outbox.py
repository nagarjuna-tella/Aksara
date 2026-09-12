"""Execute the public durable outbox helper against an installed wheel and PostgreSQL."""

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
SNIPPETS = {"export_transitions.py": ("docs/docs/how-to/export-durable-transitions.md", "app/export_transitions.py")}
PROBE = r'''
import asyncio, json, os, runpy
from pathlib import Path
from uuid import uuid4
import aksara
from aksara.db import Database
from aksara.migrations import apply_migrations
from aksara.durable import DurableAction, DurableActionRegistry, DurableOperationService, EffectClass, PrincipalReference, OperationState
from aksara.security.principal import Principal

helper = runpy.run_path('export_transitions.py')
checks = []
def passed(name, condition):
    assert condition, name
    checks.append(name)

async def handler(context, command):
    return command

async def main():
    db = Database(os.environ['DATABASE_URL'], min_size=1, max_size=2)
    await db.connect()
    try:
        Path('migrations').mkdir()
        result = await apply_migrations(db, Path('migrations'), verbose=False)
        passed('internal migrations applied', not result['errors'])
        actions = DurableActionRegistry()
        actions.register(DurableAction(name='export.probe', version='1', handler=handler, effect_class=EffectClass.READ_ONLY))
        service = DurableOperationService(db, application_namespace='outbox-public-guide', actions=actions, retention_seconds=60, idempotency_seconds=60)
        tenant = str(uuid4())
        admitted = await service.admit('export.probe', '1', {}, PrincipalReference(resolver_key='probe', resolver_version='1', identity_namespace='probe', principal_kind='user', subject_id='operator', tenant_id=tenant))
        accepted = []
        async def sink(payload):
            accepted.append(payload)
            if len(accepted) == 1:
                raise RuntimeError('simulated acknowledgement loss after acceptance')
        exporter = helper['make_exporter'](service, sink, worker_id='public-outbox-probe')
        passed('documented defaults', exporter.claim_seconds == 30 and exporter.retry_seconds == 5)
        passed('another tenant has no eligible event', not await helper['export_one'](exporter, tenant_id=str(uuid4())))
        passed('none is not all tenants', not await helper['export_one'](exporter, tenant_id=None))
        other_service = DurableOperationService(db, application_namespace='other-namespace', actions=actions, retention_seconds=60, idempotency_seconds=60)
        other = helper['make_exporter'](other_service, sink, worker_id='other-outbox-probe')
        passed('namespace selection', not await helper['export_one'](other, tenant_id=tenant))
        passed('sink failure returns false', not await helper['export_one'](exporter, tenant_id=tenant))
        passed('retry delay prevents immediate redelivery', not await helper['export_one'](exporter, tenant_id=tenant) and len(accepted) == 1)
        current = await service.get(admitted.operation.id, tenant_id=tenant, principal=Principal.for_user('operator', tenant_id=tenant))
        passed('export failure leaves authoritative state ready', current.state is OperationState.READY)
        await asyncio.sleep(5.1)
        passed('eligible retry acknowledged', await helper['export_one'](exporter, tenant_id=tenant))
        passed('duplicate payload after acceptance ambiguity', len(accepted) == 2 and accepted[0] == accepted[1])
        passed('payload identity and scope limits', accepted[0]['operation_id'] == str(admitted.operation.id) and 'tenant_id' not in accepted[0] and 'application_namespace' not in accepted[0])
        passed('no remaining eligible event', not await helper['export_one'](exporter, tenant_id=tenant))
    finally:
        await db.disconnect()
    print('OUTBOX_EVIDENCE=' + json.dumps({'checks': checks, 'package_version': aksara.__version__, 'package_path': aksara.__file__}))
asyncio.run(main())
'''


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("AKSARA_DATABASE_URL") or os.environ["DATABASE_URL"]
    schema = "aksara_v071_outbox_" + uuid4().hex[:12]
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
            with tempfile.TemporaryDirectory(prefix="aksara-outbox-docs-") as directory:
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
                evidence = json.loads(next(line.removeprefix("OUTBOX_EVIDENCE=") for line in run.stdout.splitlines()
                                           if line.startswith("OUTBOX_EVIDENCE=")))
                assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
        finally:
            await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
        assert not await connection.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = $1", schema)
    finally:
        await connection.close()
    evidence.update({"schema_version": 1, "pass": True,
                     "source_checkout_framework_imports": False, "disposable_schema_removed": True,
                     "scope": "Installed helper with real PostgreSQL migrations/admission/export and simulated sink acknowledgement loss; admin-role fixture, not restricted-role RLS, process-crash or remote durable delivery proof",
                     "page_sha256": {page: hashlib.sha256((ROOT / page).read_bytes()).hexdigest() for page, _ in SNIPPETS.values()},
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(evidence['checks'])} installed outbox checks; disposable schema removed")


if __name__ == "__main__":
    asyncio.run(main())
