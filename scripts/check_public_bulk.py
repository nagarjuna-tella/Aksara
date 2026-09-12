"""Execute the public bulk helpers and failure boundaries against an installed wheel and PostgreSQL."""

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
            "bulk_tickets.py": ("docs/docs/orm/bulk-operations.md", "app/bulk_tickets.py")}
PROBE = r'''
import asyncio, json, os, sys, types
from pathlib import Path
from uuid import uuid4
import asyncpg
import aksara
from aksara.db import Database
from aksara.exceptions import DatabaseError
from aksara.signals import pre_save, post_save
module=types.ModuleType('app.models')
exec(Path('models.py').read_text(),module.__dict__)
sys.modules['app']=types.ModuleType('app');sys.modules['app.models']=module
Ticket=module.Ticket
namespace={'__name__':'app.bulk_tickets','__package__':'app'}
exec(Path('bulk_tickets.py').read_text(),namespace)
checks=[]
def passed(name,condition):
    assert condition,name
    checks.append(name)
async def check_failure(awaitable):
    try: await awaitable
    except DatabaseError as error:
        assert isinstance(error.original_exception,asyncpg.CheckViolationError)
    else: raise AssertionError('Expected database CHECK failure')
async def main():
    db=Database(os.environ['DATABASE_URL'],min_size=1,max_size=2)
    await db.connect()
    events=[]
    async def receiver(sender,**kwargs): events.append(kwargs)
    pre_save.connect(receiver,sender=Ticket);post_save.connect(receiver,sender=Ticket)
    try:
        await db.execute("CREATE TABLE tutorial_tickets (id UUID PRIMARY KEY, subject VARCHAR(200) NOT NULL CHECK (subject <> 'reject-db'), description TEXT NOT NULL DEFAULT '', resolved BOOLEAN NOT NULL DEFAULT FALSE, created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ)")
        rows=await namespace['create_tickets']([' A ','B','C'],batch_size=2)
        passed('exact create helper inserts across batches',len(rows)==3 and await Ticket.objects.count()==3)
        passed('explicit normalization and returned defaults',rows[0].subject=='A' and all(r.created_at is not None and r.updated_at is not None for r in rows))
        passed('exact update helper counts rows',await namespace['append_note'](rows,'checked',batch_size=2)==3)
        passed('explicit updated fields persisted',all(r.description=='checked' and r.updated_at is not None for r in await Ticket.objects.all()))
        passed('empty helpers return without writes',await namespace['create_tickets']([])==[] and await namespace['append_note']([],'checked')==0)
        for arguments in [(['  '],{}),(['valid'],{'batch_size':0})]:
            try: await namespace['create_tickets'](arguments[0],**arguments[1])
            except ValueError: pass
            else: raise AssertionError('Expected input rejection')
        passed('invalid subjects and batch size rejected',await Ticket.objects.count()==3)
        new_id=uuid4()
        inserted,created=await namespace['import_ticket'](new_id,'Imported')
        passed('exact upsert helper inserts',created and inserted.id==new_id and not inserted.resolved)
        await Ticket.objects.filter(id=rows[0].id).update(resolved=True)
        updated,created=await namespace['import_ticket'](rows[0].id,'Changed')
        passed('upsert conflict preserves fields excluded from update',not created and updated.resolved and updated.subject=='Changed')
        passed('bulk methods bypass save signals',events==[])
        for field in ('resolved','updated_at'):
            try: await Ticket.objects.bulk_update([rows[1]],fields=[field])
            except DatabaseError as error:
                assert isinstance(error.original_exception,asyncpg.DatatypeMismatchError)
                checks.append('BULK-001 reproduced: '+field+' CASE inferred as text')
            else: raise AssertionError('Known bulk update mismatch was not reproduced')
        skipped=Ticket(id=rows[0].id,subject='Duplicate')
        fresh=Ticket(subject='Fresh')
        returned=await Ticket.objects.bulk_create([skipped,fresh],ignore_conflicts=True)
        passed('ignore conflicts returns only inserted rows',len(returned)==1 and returned[0].id==fresh.id)
        passed('partial returning does not hydrate input instances',skipped._is_new and fresh._is_new and returned[0] is not fresh)
        before=await Ticket.objects.count()
        await check_failure(namespace['create_tickets'](['Atomic-first','reject-db'],batch_size=1))
        passed('exact atomic helper rolls back earlier batch',await Ticket.objects.count()==before and not await Ticket.objects.filter(subject='Atomic-first').exists())
        unwrapped=[Ticket(subject='Committed-first'),Ticket(subject='reject-db')]
        await check_failure(Ticket.objects.bulk_create(unwrapped,batch_size=1))
        passed('unwrapped bulk call can retain earlier batch',await Ticket.objects.filter(subject='Committed-first').exists() and await Ticket.objects.count()==before+1)
        original=rows[1].updated_at
        rows[1].description='Updated without timestamp'
        await Ticket.objects.bulk_update([rows[1]],fields=['description'])
        reloaded=await Ticket.objects.get(id=rows[1].id)
        passed('bulk update does not implicitly refresh auto_now',reloaded.updated_at==original and reloaded.description=='Updated without timestamp')
    finally:
        pre_save.disconnect(receiver,sender=Ticket);post_save.disconnect(receiver,sender=Ticket)
        await db.disconnect()
    print('BULK_EVIDENCE='+json.dumps({'checks':checks,'package_version':aksara.__version__,'package_path':aksara.__file__,'known_runtime_defect':'BULK-001: Boolean/timestamp bulk_update CASE inferred as text'}))
asyncio.run(main())
'''


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("AKSARA_DATABASE_URL") or os.environ["DATABASE_URL"]
    schema = "aksara_v071_bulk_" + uuid4().hex[:12]
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
            with tempfile.TemporaryDirectory(prefix="aksara-bulk-docs-") as directory:
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
                evidence = json.loads(next(line.removeprefix("BULK_EVIDENCE=") for line in run.stdout.splitlines()
                                           if line.startswith("BULK_EVIDENCE=")))
                assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
        finally:
            await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
        assert not await connection.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = $1", schema)
    finally:
        await connection.close()
    evidence.update({"schema_version": 1, "pass": True, "runtime_boolean_timestamp_bulk_update_pass": False,
                     "source_checkout_framework_imports": False, "disposable_schema_removed": True,
                     "scope": "Exact bulk helper with real PostgreSQL create/update/upsert, conflict handling, signals and across-batch CHECK failure; Boolean/timestamp bulk_update failure is a reproduced defect, not a passing runtime contract; owned DDL and admin role, not migrations, RLS, advanced fields or concurrency proof",
                     "page_sha256": {page: hashlib.sha256((ROOT / page).read_bytes()).hexdigest() for page in [*(page for page, _ in SNIPPETS.values()), "docs/docs/orm/expressions-and-transactions.md"]},
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(evidence['checks'])} installed bulk-operation checks; disposable schema removed")


if __name__ == "__main__":
    asyncio.run(main())
