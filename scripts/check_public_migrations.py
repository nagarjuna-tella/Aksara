"""Execute the documented migration files through the installed canonical executor and PostgreSQL."""

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
SNIPPETS = {"initial.py": ("docs/docs/orm/migrations.md", "migrations/0001_ticket_schema.py"),
            "upgrade.py": ("docs/docs/orm/migrations.md", "migrations/0002_ticket_priority.py")}
PROBE = r'''
import asyncio, json, os
from pathlib import Path
import aksara
from aksara.db import Database
from aksara.migrations.executor import apply_migrations
checks=[]
def passed(name,condition):
    assert condition,name
    checks.append(name)
async def main():
    db=Database(os.environ['DATABASE_URL'],min_size=1,max_size=2)
    await db.connect()
    directory=Path('migrations');directory.mkdir()
    initial=directory/'0001_ticket_schema.py'
    initial.write_text(Path('initial.py').read_text())
    try:
        result=await apply_migrations(db,directory,include_internal=False,verbose=False)
        passed('exact initial migration applies',result['applied']==['0001_ticket_schema'] and not result['errors'])
        row_id=await db.fetchval("INSERT INTO migration_demo_tickets(subject) VALUES('Existing ticket') RETURNING id")
        (directory/'0002_ticket_priority.py').write_text(Path('upgrade.py').read_text())
        result=await apply_migrations(db,directory,include_internal=False,verbose=False)
        passed('exact upgrade migration applies',result['applied']==['0002_ticket_priority'] and not result['errors'])
        row=await db.fetchrow('SELECT subject,priority FROM migration_demo_tickets WHERE id=$1',row_id)
        passed('upgrade preserves and backfills existing row',row['subject']=='Existing ticket' and row['priority']=='normal')
        passed('future insert uses database default',await db.fetchval("INSERT INTO migration_demo_tickets(subject) VALUES('New ticket') RETURNING priority")=='normal')
        column=await db.fetchrow("SELECT is_nullable,column_default FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='migration_demo_tickets' AND column_name='priority'")
        passed('catalog nullability and default match',column['is_nullable']=='NO' and 'normal' in column['column_default'])
        passed('index created',await db.fetchval("SELECT EXISTS(SELECT 1 FROM pg_indexes WHERE schemaname=current_schema() AND indexname='migration_demo_tickets_priority_idx')"))
        passed('tracking records checksums',await db.fetchval('SELECT count(*) FROM aksara_migrations WHERE checksum IS NOT NULL')==2)
        result=await apply_migrations(db,directory,include_internal=False,verbose=False)
        passed('repeat run has no pending work',result['applied']==[] and not result['errors'])
        failure=directory/'0003_expected_failure.py'
        failure.write_text("from aksara.migrations import Migration as BaseMigration\nfrom aksara.migrations import operations as op\nclass Migration(BaseMigration):\n    dependencies=['0002_ticket_priority']\n    operations=[op.AddField(table='migration_demo_tickets',name='transient',field=op.StringField(nullable=True)),op.RunSQL(sql='SELECT 1 / 0')]\n")
        result=await apply_migrations(db,directory,include_internal=False,verbose=False)
        passed('failure names intended migration',len(result['errors'])==1 and result['errors'][0][0]=='0003_expected_failure' and 'division by zero' in str(result['errors'][0][1]).lower())
        passed('failed schema change rolled back',not await db.fetchval("SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='migration_demo_tickets' AND column_name='transient')"))
        passed('failed migration not recorded',await db.fetchval('SELECT count(*) FROM aksara_migrations')==2)
        failure.unlink()
        original=initial.read_text();initial.write_text(original+'\n# changed after application\n')
        try: await apply_migrations(db,directory,include_internal=False,verbose=False)
        except ValueError as error:
            passed('edited applied file rejected','checksum mismatch' in str(error).lower())
        else: raise AssertionError('Edited migration was accepted')
        finally: initial.write_text(original)
    finally:
        await db.disconnect()
    print('MIGRATION_DOC_EVIDENCE='+json.dumps({'checks':checks,'package_version':aksara.__version__,'package_path':aksara.__file__}))
asyncio.run(main())
'''


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("AKSARA_DATABASE_URL") or os.environ["DATABASE_URL"]
    schema = "aksara_v071_migration_docs_" + uuid4().hex[:12]
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
            with tempfile.TemporaryDirectory(prefix="aksara-migration-docs-") as directory:
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
                evidence = json.loads(next(line.removeprefix("MIGRATION_DOC_EVIDENCE=") for line in run.stdout.splitlines()
                                           if line.startswith("MIGRATION_DOC_EVIDENCE=")))
                assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
        finally:
            await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
        assert not await connection.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = $1", schema)
    finally:
        await connection.close()
    evidence.update({"schema_version": 1, "pass": True,
                     "source_checkout_framework_imports": False, "disposable_schema_removed": True,
                     "scope": "Two exact migration files through canonical executor, existing-row backfill, default/index/catalog checks, repeat run, injected failure and checksum edit; not migration CLI, internal migrations, RLS, concurrency or a historical application upgrade",
                     "page_sha256": {page: hashlib.sha256((ROOT / page).read_bytes()).hexdigest() for page in [*(page for page, _ in SNIPPETS.values()), "docs/docs/orm/migration-safety.md"]},
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(evidence['checks'])} installed migration-documentation checks; disposable schema removed")


if __name__ == "__main__":
    asyncio.run(main())
