"""Execute the soft-delete guide and its documented limitations against an installed wheel and PostgreSQL."""

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
SNIPPETS = {name: ('docs/docs/orm/soft-deletes.md', title) for name, title in
            [('models.py', 'soft_delete_models.py'), ('restore.py', 'restore_document.py'),
             ('queries.py', 'soft_delete_queries.py')]}
PROBE = r'''
import asyncio, json, os
from pathlib import Path
import aksara
from aksara.db import Database
from aksara.contrib.soft_delete import with_deleted, only_deleted
namespace={}
for filename in ('models.py','restore.py','queries.py'):
    exec(Path(filename).read_text(),namespace)
Document=namespace['ArchivedDocument']
checks=[]
def passed(name, condition):
    assert condition,name
    checks.append(name)
async def main():
    db=Database(os.environ['DATABASE_URL'],min_size=1,max_size=2)
    await db.connect()
    try:
        await db.execute('CREATE TABLE archived_documents (id UUID PRIMARY KEY, title TEXT NOT NULL, updated_at TIMESTAMPTZ, deleted_at TIMESTAMPTZ)')
        draft=await Document.objects.create(title='Draft')
        other=await Document.objects.create(title='Other')
        restored=await namespace['delete_and_restore'](draft.id)
        passed('exact delete and restore function',restored.id==draft.id and restored.deleted_at is None)
        await draft.delete()
        passed('default visibility excludes marked row',await Document.objects.count()==1)
        passed('exact active query',await namespace['active'].all()==[])
        passed('exact including-deleted query',[r.id for r in await namespace['including_deleted'].all()]==[draft.id])
        passed('exact deleted-only query',[r.id for r in await namespace['deleted_only'].all()]==[draft.id])
        await other.delete()
        for helper in (with_deleted,only_deleted):
            rows=await helper(Document.objects.filter(id=draft.id)).all()
            passed('SOFTDELETE001 '+helper.__name__+' loses id restriction',{r.id for r in rows}=={draft.id,other.id})
        await other.undelete()
        count=await Document.objects.filter(id=other.id).delete()
        passed('queryset delete physically removes row',count==1 and await db.fetchval('SELECT count(*) FROM archived_documents WHERE id=$1',other.id)==0)
        for method in ('delete','undelete'):
            try: await getattr(Document(title='Unsaved'),method)()
            except ValueError: checks.append('unsaved '+method+' rejected')
            else: raise AssertionError('unsaved instance accepted')
    finally:
        await db.disconnect()
    print('SOFT_EVIDENCE='+json.dumps({'checks':checks,'package_version':aksara.__version__,'package_path':aksara.__file__}))
asyncio.run(main())
'''


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("AKSARA_DATABASE_URL") or os.environ["DATABASE_URL"]
    assert urlsplit(dsn).path == "/aksara_test", "Use the authorized test database"
    schema = "aksara_v071_soft_delete_" + uuid4().hex[:12]
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
            with tempfile.TemporaryDirectory(prefix="aksara-soft_delete-docs-") as directory:
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
                evidence = json.loads(next(line.removeprefix("SOFT_EVIDENCE=") for line in run.stdout.splitlines()
                                           if line.startswith("SOFT_EVIDENCE=")))
                assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
        finally:
            await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
        assert not await connection.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = $1", schema)
    finally:
        await connection.close()
    evidence.update({"schema_version": 1, "pass": True,
                     "runtime_queryset_helper_preserves_filters": False,
                     "source_checkout_framework_imports": False, "disposable_schema_removed": True,
                     "scope": "Exact soft-delete guide fences against PostgreSQL; owned schema, admin role; no RLS or concurrency proof. Helper filter loss is a reproduced defect.",
                     "page_sha256": {page: hashlib.sha256((ROOT / page).read_bytes()).hexdigest() for page, _ in SNIPPETS.values()},
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(evidence['checks'])} installed soft_delete-operation checks; disposable schema removed")


if __name__ == "__main__":
    asyncio.run(main())
