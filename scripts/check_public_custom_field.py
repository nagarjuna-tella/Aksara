"""Execute the documented custom field and model against an installed wheel and PostgreSQL."""

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
SNIPPETS = {"fields.py": ("docs/docs/advanced/custom-fields.md", "app/fields.py"),
            "models.py": ("docs/docs/advanced/custom-fields.md", "app/models.py")}
PROBE = r'''
import asyncio, json, os, sys, types
from pathlib import Path
from datetime import datetime, timezone
import aksara
from aksara.db import Database
from aksara.exceptions import UniqueConstraintError, ValidationError
from aksara.migrations.autodetector import model_to_create_table_operation
sys.modules['app']=types.ModuleType('app')
field_module=types.ModuleType('app.fields')
exec(Path('fields.py').read_text(),field_module.__dict__)
sys.modules['app.fields']=field_module
model_module=types.ModuleType('app.models');model_module.__package__='app'
exec(Path('models.py').read_text(),model_module.__dict__)
TicketReference=model_module.TicketReference
TicketCode=field_module.TicketCode
checks=[]
def passed(name,condition):
    assert condition,name
    checks.append(name)
async def main():
    field=TicketCode()
    passed('built-in SQL representation inherited',field.sql_type=='VARCHAR(24)')
    passed('normalization round trip',field.to_db(' help-12 ')=='HELP-12' and field.to_python('HELP-12')=='HELP-12')
    passed('nullable conversion preserved',TicketCode(nullable=True).to_db(None) is None)
    for value in ('', '12-HELP', 'hello/world', 'X'*25, 12):
        try: field.to_db(value)
        except ValueError: pass
        else: raise AssertionError('Invalid code accepted')
    passed('invalid type format and length rejected',True)
    db=Database(os.environ['DATABASE_URL'],min_size=1,max_size=2)
    await db.connect()
    try:
        operation=model_to_create_table_operation(TicketReference)
        await operation.apply(db)
        column=await db.fetchrow("SELECT data_type,character_maximum_length FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='ticket_references' AND column_name='code'")
        passed('autodetected schema uses VARCHAR24',column['data_type']=='character varying' and column['character_maximum_length']==24)
        item=await TicketReference.objects.create(code=' help-12 ')
        passed('save preparation updates instance',item.code=='HELP-12')
        loaded=await TicketReference.objects.get(id=item.id)
        passed('database reload uses conversion',loaded.code=='HELP-12')
        try: await TicketReference.objects.create(code='HELP-12')
        except UniqueConstraintError: checks.append('generated unique constraint rejects normalized duplicate')
        else: raise AssertionError('Duplicate accepted')
        try: await TicketReference.objects.create(code=None)
        except ValidationError: checks.append('model rejects nonnullable value')
        else: raise AssertionError('Null accepted')
        await TicketReference.objects.filter(id=item.id).update(code=' help-13 ')
        passed('query update applies conversion',(await TicketReference.objects.get(id=item.id)).code=='HELP-13')
        rows=await TicketReference.objects.bulk_create([TicketReference(code=' help-14 ')])
        passed('bulk create prepares and reloads',rows[0].code=='HELP-14')
        rows[0].code=' help-15 '
        await TicketReference.objects.bulk_update(rows,fields=['code'])
        passed('text bulk update converts database value',(await TicketReference.objects.get(id=rows[0].id)).code=='HELP-15')
        inserted,created=await TicketReference.objects.upsert(code=' help-16 ',defaults={'updated_at':datetime.now(timezone.utc)})
        passed('upsert converts insert values',created and inserted.code=='HELP-16')
        existing,created=await TicketReference.objects.upsert(code='HELP-16',defaults={'updated_at':datetime.now(timezone.utc)})
        passed('upsert normalized conflict returns existing',not created and existing.id==inserted.id)
    finally:
        await db.disconnect()
    print('CUSTOM_FIELD_EVIDENCE='+json.dumps({'checks':checks,'package_version':aksara.__version__,'package_path':aksara.__file__}))
asyncio.run(main())
'''


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("AKSARA_DATABASE_URL") or os.environ["DATABASE_URL"]
    schema = "aksara_v071_custom_field_" + uuid4().hex[:12]
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
            with tempfile.TemporaryDirectory(prefix="aksara-custom-field-docs-") as directory:
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
                evidence = json.loads(next(line.removeprefix("CUSTOM_FIELD_EVIDENCE=") for line in run.stdout.splitlines()
                                           if line.startswith("CUSTOM_FIELD_EVIDENCE=")))
                assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
        finally:
            await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
        assert not await connection.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = $1", schema)
    finally:
        await connection.close()
    evidence.update({"schema_version": 1, "pass": True,
                     "source_checkout_framework_imports": False, "disposable_schema_removed": True,
                     "scope": "Exact field/model conversion, autodetected CreateTable operation and PostgreSQL persistence paths; admin-role fixture, not full migration CLI/history, RLS, HTTP serializer or arbitrary custom-type support",
                     "page_sha256": {page: hashlib.sha256((ROOT / page).read_bytes()).hexdigest() for page in [*(page for page, _ in SNIPPETS.values()), "docs/docs/orm/bulk-operations.md"]},
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(evidence['checks'])} installed custom-field checks; disposable schema removed")


if __name__ == "__main__":
    asyncio.run(main())
