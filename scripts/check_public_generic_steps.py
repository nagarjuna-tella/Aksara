"""Execute generic-relation and persisted-step documentation with an installed wheel and PostgreSQL."""

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
SNIPPETS = {'generic_models.py': ('docs/docs/advanced/generic-relations-and-durable-workflows.md', 'app/generic_models.py'), 'generic_examples.py': ('docs/docs/advanced/generic-relations-and-durable-workflows.md', 'app/generic_examples.py'), 'step_examples.py': ('docs/docs/advanced/generic-relations-and-durable-workflows.md', 'app/step_examples.py'), 'decimal_steps.py': ('docs/docs/advanced/generic-relations-and-durable-workflows.md', 'app/decimal_steps.py')}
PROBE = r'''
import asyncio, json, os, sys, types
from pathlib import Path
from decimal import Decimal
from uuid import uuid4
import aksara
from aksara import DurableStep
from aksara.db import Database
from aksara.manager import DoesNotExist
from aksara.migrations.autodetector import model_to_create_table_operation
from aksara.workflows import ConcurrentStepError
sys.modules['app']=types.ModuleType('app')
modules={}
for filename in ('generic_models','generic_examples','step_examples','decimal_steps'):
    module=types.ModuleType('app.'+filename);sys.modules[module.__name__]=module
    exec(Path(filename+'.py').read_text(),module.__dict__);modules[filename]=module
Post=modules['generic_models'].Post;Comment=modules['generic_models'].Comment
checks=[]
def passed(name,condition):
    assert condition,name
    checks.append(name)
def forbidden():raise AssertionError('cached callback should not run')
async def main():
    db=Database(os.environ['DATABASE_URL'],min_size=1,max_size=4);await db.connect()
    try:
        for model in (Post,Comment):await model_to_create_table_operation(model).apply(db)
        post,comment=await modules['generic_examples'].create_comment_example()
        passed('exact generic example persists and resolves',comment.object_id==str(post.id) and (await comment.content_object()).title=='Hello')
        empty=await Comment.objects.create(body='Unset')
        passed('unset generic relation returns None',await empty.content_object() is None)
        other=await Post.objects.create(title='Other')
        comment.content_object=other;await comment.save()
        loaded=await Comment.objects.get(id=comment.id)
        passed('reassignment persists new target',(await loaded.content_object()).id==other.id)
        await other.delete()
        passed('instance accessor retains resolved cache',(await loaded.content_object()).id==other.id)
        fresh=await Comment.objects.get(id=comment.id)
        try:await fresh.content_object()
        except DoesNotExist:passed('fresh dangling target lookup raises DoesNotExist',True)
        else:raise AssertionError('target deletion unexpectedly cascaded or resolved')
        loaded.content_object=None;await loaded.save()
        passed('clearing generic relation persists null pair',(await Comment.objects.get(id=comment.id)).object_id is None)
        try:loaded.content_object='not a model'
        except TypeError:passed('non-model assignment rejected',True)
        else:raise AssertionError('non-model accepted')
        step=await modules['step_examples'].demonstrate_step('docs-summary')
        passed('exact step example reuses completed result',(await step.get_state('summary')).status=='completed')
        passed('new instance same identity reuses without callback',await DurableStep('docs-summary').run('summary',forbidden)=={'files':3})
        passed('callback arguments do not change cache identity',await step.run('summary',forbidden,'different input')=={'files':3})
        passed('synchronous callback supported',await step.run('sync',lambda:7)==7)
        token=uuid4()
        passed('default encoding normalizes UUID',await step.run('uuid',lambda:token)==str(token))
        decimal=modules['decimal_steps'].decimal_step('docs-decimal')
        value=await decimal.run('amount',lambda:Decimal('12.50'))
        passed('exact Decimal codec first and cached result',value==Decimal('12.50') and isinstance(value,Decimal) and await decimal.run('amount',forbidden)==value)
        def fail():raise ValueError('deliberate example failure')
        try:await step.run('retry',fail)
        except ValueError as exc:passed('ordinary failure recorded and reraised',str(exc)=='deliberate example failure' and (await step.get_state('retry')).status=='failed')
        else:raise AssertionError('failure swallowed')
        passed('explicit retry reclaims failed step',await step.run('retry',lambda:'recovered')=='recovered')
        passed('force reruns completed step',await step.run('summary',lambda:{'files':4},force=True)=={'files':4})
        passed('missing state returns None',await step.get_state('absent') is None)
        started=asyncio.Event();release=asyncio.Event()
        async def slow():started.set();await release.wait();return 'original'
        original=asyncio.create_task(step.run('concurrent',slow))
        try:
            await asyncio.wait_for(started.wait(),5)
            try:await step.run('concurrent',forbidden)
            except ConcurrentStepError:passed('normal competing claim rejected',True)
            else:raise AssertionError('competing claim accepted')
            passed('force bypasses running claim',await step.run('concurrent',lambda:'forced',force=True)=='forced')
        finally:release.set();await original
        passed('original completion can overwrite forced result',(await step.get_state('concurrent')).result=='original')
        started=asyncio.Event();release=asyncio.Event()
        cancelled=asyncio.create_task(step.run('cancelled',slow))
        await asyncio.wait_for(started.wait(),5);cancelled.cancel()
        try:await cancelled
        except asyncio.CancelledError:pass
        passed('task cancellation leaves running state',(await step.get_state('cancelled')).status=='running')
        await step.clear('summary')
        passed('clear one preserves other steps',await step.get_state('summary') is None and await step.get_state('sync') is not None)
        await step.clear()
        passed('clear all is scoped by workflow',await step.get_state('sync') is None and (await decimal.get_state('amount')).status=='completed')
    finally:await db.disconnect()
    print('GENERIC_STEP_DOC_EVIDENCE='+json.dumps({'checks':checks,'package_version':aksara.__version__,'package_path':aksara.__file__}))
asyncio.run(main())
'''


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("AKSARA_DATABASE_URL") or os.environ["DATABASE_URL"]
    schema = "aksara_v071_generic_step_" + uuid4().hex[:12]
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
            with tempfile.TemporaryDirectory(prefix="aksara-generic-step-docs-") as directory:
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
                evidence = json.loads(next(line.removeprefix("GENERIC_STEP_DOC_EVIDENCE=") for line in run.stdout.splitlines()
                                           if line.startswith("GENERIC_STEP_DOC_EVIDENCE=")))
                assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
        finally:
            await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
        assert not await connection.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = $1", schema)
    finally:
        await connection.close()
    evidence.update({"schema_version": 1, "pass": True,
                     "source_checkout_framework_imports": False, "disposable_schema_removed": True,
                     "scope": "Exact generic and step helpers, fresh/cached target resolution, JSON codec, reuse/retry/force/concurrent claims and task cancellation against PostgreSQL; admin role, not RLS, authorization, process-death recovery or Durable Operation certification",
                     "page_sha256": {page: hashlib.sha256((ROOT / page).read_bytes()).hexdigest() for page in {page for page, _ in SNIPPETS.values()}},
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(evidence['checks'])} installed generic/step-documentation checks; disposable schema removed")


if __name__ == "__main__":
    asyncio.run(main())
