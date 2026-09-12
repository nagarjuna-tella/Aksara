"""Execute all Array, JSON and Vector field-reference blocks against an installed wheel and PostgreSQL."""

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
PAGE = "docs/docs/orm/fields.md"
PROBE = r'''
import ast, asyncio, inspect, json, os
from pathlib import Path
import aksara
from aksara import Model, fields
from aksara.db import Database
from aksara.exceptions import ValidationError
from aksara.migrations.autodetector import model_to_create_table_operation
checks=[]
def passed(name,condition):
    assert condition,name
    checks.append(name)
async def execute_block(source,namespace,db):
    tree=ast.parse(source)
    for statement in tree.body:
        unit=ast.Module(body=[statement],type_ignores=[])
        result=eval(compile(unit,'documented-advanced-field','exec',flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT),namespace)
        if inspect.isawaitable(result): await result
        if isinstance(statement,ast.ClassDef):
            await model_to_create_table_operation(namespace[statement.name]).apply(db)
async def rejected(model,**kwargs):
    before=await model.objects.count()
    try: await model.objects.create(**kwargs)
    except ValidationError: pass
    else: raise AssertionError('Expected model ValidationError')
    assert await model.objects.count()==before
async def main():
    db=Database(os.environ['DATABASE_URL'],min_size=1,max_size=2)
    await db.connect()
    try:
        sections=json.loads(Path('sections.json').read_text())
        namespaces={}
        for name,blocks in sections.items():
            namespace={'__name__':'documented_'+name.lower(),'Model':Model,'fields':fields}
            for block in blocks: await execute_block(block,namespace,db)
            namespaces[name]=namespace
            passed('all '+name+' guide blocks execute',True)
        from datetime import time, timedelta
        time_ns=namespaces['Time']
        schedule=await time_ns['Schedule'].objects.get(id=time_ns['schedule'].id)
        passed('Time guide persisted clock value',schedule.alarm==time(7,30))
        duration_ns=namespaces['Duration']
        recipe=await duration_ns['Recipe'].objects.get(id=duration_ns['recipe'].id)
        passed('Duration guide persisted interval',recipe.prep_time==timedelta(minutes=30))
        user_ns=namespaces['JSON'];User=user_ns['User']
        passed('nested JSON query returns created row',[r.id for r in user_ns['dark_mode_users']]==[user_ns['user'].id])
        for value in ['draft',3.14,True,{'nested':[None,'value']}]:
            row=await User.objects.create(preferences=value)
            passed('JSON round trip '+type(value).__name__,(await User.objects.get(id=row.id)).preferences==value)
        await rejected(User,preferences={'bad':float('nan')})
        passed('nonfinite JSON rejected before insertion',True)
        array_ns=namespaces['Array'];Article=array_ns['Article']
        loaded=await Article.objects.get(id=array_ns['article'].id)
        passed('array append persists through save',loaded.tags==['python','async','orm','database'] and loaded.view_counts==[100,250,180])
        for values in ([None],[True],['1'],[[1]]):
            await rejected(Article,tags=[],view_counts=values)
        passed('array null bool wrong type and nested values rejected',True)
        vector_ns=namespaces['Vector'];Document=vector_ns['Document']
        document=await Document.objects.get(id=vector_ns['document'].id)
        passed('vector reload has configured dimensions',len(document.embedding)==3 and all(abs(a-b)<1e-6 for a,b in zip(document.embedding,[.12,.33,.98])))
        for values in ([1,2],[True,2,3],[float('inf'),2,3],[]):
            await rejected(Document,title='Invalid',embedding=values)
        passed('vector dimension bool nonfinite and empty values rejected',True)
        await Document.objects.filter(id=document.id).update(embedding=[1,2,3])
        document=await Document.objects.get(id=document.id)
        passed('vector queryset update persists',document.embedding==[1,2,3])
        document.embedding=[4,5,6]
        await Document.objects.bulk_update([document],fields=['embedding'])
        passed('explicit vector CASE cast persists',(await Document.objects.get(id=document.id)).embedding==[4,5,6])
        messages=[]
        validation={'Model':Model,'fields':fields,'print':lambda value: messages.append(str(value))}
        code=compile(Path('validation.py').read_text(),'documented-validation','exec',flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
        await eval(code,validation)
        passed('validation fragment catches both field errors',len(messages)==2 and 'email' in messages[0] and 'age' in messages[1])
        catalog={'__name__':'catalog_models'}
        exec(Path('catalog_models.py').read_text(),catalog)
        Category,Product=catalog['Category'],catalog['Product']
        for model in (Category,Product):
            await model_to_create_table_operation(model).apply(db)
        category=await Category.objects.create(name='Tools')
        product=await Product.objects.create(name='Hammer',slug='hammer',price='12.34',sku='HAMMER-1',category=category)
        loaded=await Product.objects.get(id=product.id)
        passed('catalog model decimal and enum persist',str(loaded.price)=='12.34' and loaded.status==catalog['ProductStatus'].DRAFT)
        passed('catalog model defaults and nullable fields',loaded.quantity==0 and loaded.metadata=={} and loaded.compare_at_price is None and loaded.description is None)
        passed('catalog model foreign key persists',loaded.category_id==category.id)
    finally:
        await db.disconnect()
    print('ADVANCED_FIELDS_EVIDENCE='+json.dumps({'checks':checks,'package_version':aksara.__version__,'package_path':aksara.__file__}))
asyncio.run(main())
'''


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("AKSARA_DATABASE_URL") or os.environ["DATABASE_URL"]
    schema = "aksara_v071_advanced_field_" + uuid4().hex[:12]
    connection = await asyncpg.connect(dsn)
    try:
        extension = await connection.fetchrow("SELECT e.extversion, n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='vector'")
        if not extension:
            raise RuntimeError('Installed pgvector extension is required; this gate must not silently skip it')
        await connection.execute(f'CREATE SCHEMA "{schema}"')
        try:
            url = urlsplit(dsn)
            query = dict(parse_qsl(url.query))
            query["search_path"] = schema + "," + '"' + extension["nspname"].replace('"', '""') + '"'
            scoped = urlunsplit(url._replace(query=urlencode(query)))
            env = {k: v for k, v in os.environ.items()
                   if k not in {"PYTHONPATH", "DATABASE_URL"} and not k.startswith("AKSARA_")}
            env["DATABASE_URL"] = scoped
            with tempfile.TemporaryDirectory(prefix="aksara-advanced-field-docs-") as directory:
                root = Path(directory)
                text = (ROOT / PAGE).read_text()
                sections = {}
                for name in ('JSON', 'Array', 'Vector', 'Time', 'Duration'):
                    body = text.split('### ' + name + '\n', 1)[1].split('\n### ', 1)[0]
                    sections[name] = re.findall(r'```python\n(.*?)```', body, re.DOTALL)
                assert {name: len(blocks) for name, blocks in sections.items()} == {'JSON': 3, 'Array': 2, 'Vector': 2, 'Time': 2, 'Duration': 2}
                (root / 'sections.json').write_text(json.dumps(sections))
                validation = text.split('## Field Validation',1)[1].split('## Complete Example',1)[0]
                (root / 'validation.py').write_text(re.search(r'```python\n(.*?)```',validation,re.DOTALL).group(1))
                catalog = re.search(r'```python title="app/catalog_models.py"\n(.*?)```',text,re.DOTALL).group(1)
                (root / 'catalog_models.py').write_text(catalog)
                run = await asyncio.to_thread(
                    subprocess.run, [str(args.python.absolute()), "-I", "-c", PROBE],
                    cwd=root, env=env, capture_output=True, text=True, timeout=60, check=False,
                )
                if run.returncode:
                    message = (run.stderr or run.stdout).replace(scoped, "[REDACTED]").replace(dsn, "[REDACTED]")
                    raise RuntimeError(message)
                evidence = json.loads(next(line.removeprefix("ADVANCED_FIELDS_EVIDENCE=") for line in run.stdout.splitlines()
                                           if line.startswith("ADVANCED_FIELDS_EVIDENCE=")))
                assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
        finally:
            await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
        assert not await connection.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = $1", schema)
    finally:
        await connection.close()
    evidence.update({"schema_version": 1, "pass": True, "pgvector_version": extension["extversion"],
                     "source_checkout_framework_imports": False, "disposable_schema_removed": True,
                     "scope": "All eleven JSON/Array/Vector/Time/Duration guide blocks, autodetected CreateTable operations and selected PostgreSQL writes/rejections plus the exact validation fragment and catalog model declarations; existing pgvector, admin role, not full migration CLI/history, RLS, HTTP serializer or all advanced-field paths",
                     "page_sha256": {PAGE: hashlib.sha256((ROOT / PAGE).read_bytes()).hexdigest()},
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(evidence['checks'])} installed advanced-field checks; disposable schema removed")


if __name__ == "__main__":
    asyncio.run(main())
