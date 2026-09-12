"""Execute the fixture import/export failure boundaries against an installed wheel and PostgreSQL."""

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
SNIPPETS = {'fixture_notes.py': ('docs/docs/orm/fixtures.md', 'fixture_notes.py')}
PROBE = r'''
import asyncio, json, os
from uuid import uuid4
import aksara
from pathlib import Path
from aksara import transaction
from aksara.db import Database
from aksara.fixtures import dump_data, dump_database, load_data
from aksara.manager import DoesNotExist
import yaml
namespace={}
exec(Path('fixture_notes.py').read_text(),namespace)
FixtureNote=namespace['FixtureNote']
checks=[]
def passed(name,condition):
    assert condition,name
    checks.append(name)
async def main():
    db=Database(os.environ['DATABASE_URL'],min_size=1,max_size=2)
    await db.connect()
    try:
        await db.execute('CREATE TABLE fixture_notes (id UUID PRIMARY KEY, title TEXT NOT NULL, updated_at TIMESTAMPTZ)')
        stats=await namespace['seed_note']('Original')
        passed('exact guide seed inserts',stats=={'loaded':1,'errors':0,'skipped':0})
        row=await FixtureNote.objects.get(title='Original')
        exported=await namespace['export_notes']()
        passed('JSON export includes primary key and selected fields',json.loads(exported)==[{'model':'FixtureNote','pk':str(row.id),'fields':{'title':'Original'}}])
        payload=json.loads(exported);payload[0]['fields']['title']='Changed'
        stats=await load_data(json.dumps(payload),strict=True)
        passed('existing primary key updated',stats['loaded']==1 and (await FixtureNote.objects.get(id=row.id)).title=='Changed')
        await FixtureNote.objects.filter(id=row.id).delete()
        stats=await load_data(exported)
        passed('FIXTURE001 exported primary key is not restored to empty table',stats=={'loaded':0,'errors':1,'skipped':0} and await FixtureNote.objects.count()==0)
        seed={'model':'FixtureNote','fields':{'title':'Seed'}}
        stats=await load_data(json.dumps(seed),strict=True)
        passed('omitted primary key inserts',stats['loaded']==1 and await FixtureNote.objects.count()==1)
        text=await dump_data(FixtureNote,format='yaml')
        try: await load_data(text,format='yaml',strict=True)
        except yaml.constructor.ConstructorError: checks.append('FIXTURE002 UUID YAML dump rejected by safe loader')
        else: raise AssertionError('Expected unsafe YAML tag rejection')
        try: await dump_database()
        except AttributeError as error:
            passed('FIXTURE003 registry iteration supplies names not models',"objects" in str(error))
        else: raise AssertionError('Expected registry iteration failure')
        subset=json.loads(await dump_database(models=['FixtureNote']))
        passed('explicit model names export',len(subset)==1)
        invalid={'model':'FixtureNote','pk':str(uuid4()),'fields':{'title':'Missing'}}
        before=await FixtureNote.objects.count()
        try: await load_data(json.dumps([seed,invalid]),strict=True)
        except DoesNotExist: pass
        else: raise AssertionError('Expected missing primary key failure')
        passed('strict mode leaves earlier successful insert',await FixtureNote.objects.count()==before+1)
        before=await FixtureNote.objects.count()
        try:
            async with transaction.atomic():
                await load_data(json.dumps([seed,invalid]),strict=True)
        except DoesNotExist: pass
        else: raise AssertionError('Expected transaction failure')
        passed('outer atomic transaction rolls back earlier insert',await FixtureNote.objects.count()==before)
        for strict in (False,True):
            try: await load_data('{',strict=strict)
            except json.JSONDecodeError: checks.append('malformed JSON raises with strict='+str(strict))
            else: raise AssertionError('Malformed input accepted')
        stats=await load_data(json.dumps(seed),models={'Other':FixtureNote},strict=True)
        passed('models mapping is not an allowlist',stats['loaded']==1)
    finally: await db.disconnect()
    print('FIXTURE_EVIDENCE='+json.dumps({'checks':checks,'package_version':aksara.__version__,'package_path':aksara.__file__}))
asyncio.run(main())
'''


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("AKSARA_DATABASE_URL") or os.environ["DATABASE_URL"]
    assert urlsplit(dsn).path == "/aksara_test", "Use the authorized test database"
    schema = "aksara_v071_fixtures_" + uuid4().hex[:12]
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
            with tempfile.TemporaryDirectory(prefix="aksara-fixtures-docs-") as directory:
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
                evidence = json.loads(next(line.removeprefix("FIXTURE_EVIDENCE=") for line in run.stdout.splitlines()
                                           if line.startswith("FIXTURE_EVIDENCE=")))
                assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
        finally:
            await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
        assert not await connection.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = $1", schema)
    finally:
        await connection.close()
    evidence.update({"schema_version": 1, "pass": True,
                     "runtime_export_restore_roundtrip": False,
                     "source_checkout_framework_imports": False, "disposable_schema_removed": True,
                     "scope": "Fixture API observations against PostgreSQL; owned schema and admin role. Exact guide seed/export helpers plus API error and transaction boundaries; no migration, RLS or concurrency proof. Export/restore, YAML and registry defects are negative controls.",
                     "page_sha256": {page: hashlib.sha256((ROOT / page).read_bytes()).hexdigest() for page, _ in SNIPPETS.values()},
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(evidence['checks'])} installed fixtures-operation checks; disposable schema removed")


if __name__ == "__main__":
    asyncio.run(main())
