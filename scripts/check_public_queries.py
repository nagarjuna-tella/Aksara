"""Execute every querying-guide Python block against PostgreSQL in an installed wheel."""

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
PAGES = ("docs/docs/orm/querying.md", "docs/docs/getting-started/first-project.md", "docs/docs/orm/signals.md",
         "docs/docs/orm/expressions-and-transactions.md", "docs/docs/orm/models.md")
PROBE = r'''
import ast, asyncio, inspect, json, os, sys, types
from pathlib import Path
import aksara
from aksara.db import Database

model_module = types.ModuleType('app.models')
exec(Path('models.py').read_text(), model_module.__dict__)
sys.modules['app'] = types.ModuleType('app')
sys.modules['app.models'] = model_module
Ticket = model_module.Ticket
checks = []
def passed(name, condition):
    assert condition, name
    checks.append(name)

async def main():
    db = Database(os.environ['DATABASE_URL'], min_size=1, max_size=2)
    await db.connect()
    try:
        await db.execute('CREATE TABLE tutorial_tickets (id UUID PRIMARY KEY, subject VARCHAR(200) NOT NULL, description TEXT NOT NULL, resolved BOOLEAN NOT NULL, updated_at TIMESTAMPTZ)')
        login = await Ticket.objects.create(subject='Login help')
        await Ticket.objects.create(subject='Archived', resolved=True)
        await Ticket.objects.create(subject='Other', description='login issue')
        namespace = {'ticket_id': login.id, 'search_term': 'Login', 'unresolved_only': True}
        blocks = json.loads(Path('blocks.json').read_text())
        for index, source in enumerate(blocks, 1):
            result = eval(compile(source, f'documented-query-{index}', 'exec', flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT), namespace)
            if inspect.isawaitable(result):
                await result
            passed(f'querying block {index} executed', True)
            if index == 1:
                passed('unresolved ordered rows', [r.subject for r in namespace['tickets']] == ['Login help', 'Other'])
            elif index == 2:
                passed('get resolves identifier', namespace['ticket'].id == login.id)
                namespace['ticket_id'] = __import__('uuid').uuid4()
                await eval(compile(source, 'missing-query', 'exec', flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT), namespace)
                passed('missing get handled', namespace['ticket'] is None)
            elif index == 3:
                passed('ordered first', namespace['ticket'].id == login.id)
            elif index == 4:
                passed('OR and negation', {r.subject for r in namespace['matches']} == {'Login help', 'Other'} and len(namespace['other_tickets']) == 2)
            elif index == 5:
                passed('conditional query', [r.subject for r in namespace['rows']] == ['Login help'])
            elif index == 6:
                passed('offset beyond results', namespace['rows'] == [])
            elif index == 7:
                passed('count existence aggregate', (namespace['total'], namespace['open_count'], namespace['has_open_tickets'], namespace['summary']) == (3, 2, True, {'total': 3}))
            elif index == 8:
                passed('bounded public projection', len(namespace['public_rows']) == 3 and all(set(r) == {'id', 'subject'} for r in namespace['public_rows']))
        passed('all guide blocks covered', len(blocks) == 8)
        from aksara import transaction
        from aksara.signals import pre_save, post_save
        signal_module = types.ModuleType('app.signals')
        exec(Path('signals.py').read_text(), signal_module.__dict__)
        events = []
        async def before(sender, instance, **kwargs):
            events.append(('pre', dict(kwargs)))
        async def after(sender, instance, **kwargs):
            events.append(('post', dict(kwargs)))
        signal_module.connect_signals()
        pre_save.connect(before, sender=Ticket)
        post_save.connect(after, sender=Ticket)
        try:
            obj = await Ticket.objects.create(subject='  Normalized  ')
            passed('documented pre_save normalization persisted', (await Ticket.objects.get(id=obj.id)).subject == 'Normalized')
            passed('insert lifecycle payloads', events == [('pre', {'is_new': True}), ('post', {})])
            events.clear()
            obj.subject = '  Updated  '
            await obj.save()
            passed('update lifecycle payloads', events == [('pre', {'is_new': False}), ('post', {})])
            events.clear()
            rolled_id = None
            try:
                async with transaction.atomic():
                    rolled = await Ticket.objects.create(subject='  Rolled back  ')
                    rolled_id = rolled.id
                    passed('post_save ran before outer commit', events == [('pre', {'is_new': True}), ('post', {})])
                    raise RuntimeError('deliberate outer rollback')
            except RuntimeError as exc:
                assert str(exc) == 'deliberate outer rollback'
            passed('outer rollback removes row but not local callback observation', await Ticket.objects.get_or_none(id=rolled_id) is None and len(events) == 2)
            async with transaction.atomic():
                kept = await Ticket.objects.create(subject='Outer survives')
                try:
                    async with transaction.atomic():
                        nested = await Ticket.objects.create(subject='Inner rolled back')
                        raise RuntimeError('deliberate savepoint rollback')
                except RuntimeError as exc:
                    assert str(exc) == 'deliberate savepoint rollback'
            passed('caught inner failure preserves outer commit', await Ticket.objects.get_or_none(id=kept.id) is not None and await Ticket.objects.get_or_none(id=nested.id) is None)
        finally:
            pre_save.disconnect(before, sender=Ticket)
            post_save.disconnect(after, sender=Ticket)
            passed('documented signal disconnection', signal_module.disconnect_signals())
        # Execute the complete model-guide example with test-owned schema setup.
        model_example = {'__name__': 'model_guide_example'}
        exec(Path('model_example.py').read_text(), model_example)
        Category, Product = model_example['Category'], model_example['Product']
        await db.execute("CREATE TABLE categories (id UUID PRIMARY KEY, name VARCHAR(100) UNIQUE NOT NULL, slug VARCHAR(100) UNIQUE NOT NULL, description TEXT, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ)")
        await db.execute("CREATE TABLE products (id UUID PRIMARY KEY, name VARCHAR(200) NOT NULL, slug VARCHAR(200) UNIQUE NOT NULL, description TEXT NOT NULL, price NUMERIC(10,2) NOT NULL, sale_price NUMERIC(10,2), sku VARCHAR(50) UNIQUE NOT NULL, stock_quantity INTEGER NOT NULL, is_active BOOLEAN NOT NULL, is_featured BOOLEAN NOT NULL, category_id UUID NOT NULL REFERENCES categories(id), tags TEXT[], attributes JSONB, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ)")
        await model_example['example']()
        category = await Category.objects.get(slug='electronics')
        product = await Product.objects.get(sku='PHONE-001')
        passed('complete model example persisted both records', await Category.objects.count() == 1 and await Product.objects.count() == 1)
        passed('model example decimal and stock values', str(product.price) == '999.99' and product.stock_quantity == 100)
        passed('model example array and JSON values', product.tags == ['smartphone', 'mobile', '5g'] and product.attributes == {'color': 'black', 'storage': '256GB'})
        passed('model example forward relation is an ID', product.category == category.id)
        eager = (await Product.objects.filter(sku='PHONE-001').select_related('category').all())[0]
        passed('model example eager relation is available', eager.get_related('category').name == 'Electronics')
        first = await Product.objects.filter(sku='PHONE-001').select_related('category').first()
        try:
            first.get_related('category')
        except ValueError as exc:
            passed('first does not populate requested eager relation', 'was not prefetched' in str(exc))
        else:
            raise AssertionError('Reassess RELATION001: first now loads the relation')
    finally:
        await db.disconnect()
    print('QUERY_EVIDENCE=' + json.dumps({'checks': checks, 'package_version': aksara.__version__, 'package_path': aksara.__file__}))
asyncio.run(main())
'''


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("AKSARA_DATABASE_URL") or os.environ["DATABASE_URL"]
    schema = "aksara_v071_queries_" + uuid4().hex[:12]
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
            with tempfile.TemporaryDirectory(prefix="aksara-query-docs-") as directory:
                root = Path(directory)
                model_page = (ROOT / PAGES[1]).read_text()
                model_source = re.search(r'```python title="app/models.py"\n(.*?)```', model_page, re.DOTALL).group(1)
                (root / "models.py").write_text(model_source)
                complete = (ROOT / PAGES[4]).read_text().split('## Complete model example', 1)[1]
                example_source = re.search(r'```python\n(.*?)```', complete, re.DOTALL).group(1)
                (root / "model_example.py").write_text(example_source)
                signal_source = re.search(r'```python title="app/signals.py"\n(.*?)```', (ROOT / PAGES[2]).read_text(), re.DOTALL).group(1)
                (root / "signals.py").write_text(signal_source)
                blocks = re.findall(r'```python\n(.*?)```', (ROOT / PAGES[0]).read_text(), re.DOTALL)
                (root / "blocks.json").write_text(json.dumps(blocks))
                run = await asyncio.to_thread(
                    subprocess.run, [str(args.python.absolute()), "-I", "-c", PROBE],
                    cwd=root, env=env, capture_output=True, text=True, timeout=60,
                )
                if run.returncode:
                    message = (run.stderr or run.stdout).replace(scoped, "[REDACTED]").replace(dsn, "[REDACTED]")
                    raise RuntimeError(message)
                evidence = json.loads(next(line.removeprefix("QUERY_EVIDENCE=") for line in run.stdout.splitlines()
                                           if line.startswith("QUERY_EVIDENCE=")))
                assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
        finally:
            await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
        assert not await connection.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = $1", schema)
    finally:
        await connection.close()
    evidence.update({"schema_version": 1, "pass": True,
                     "source_checkout_framework_imports": False, "disposable_schema_removed": True,
                     "runtime_first_populates_requested_relation": False,
                     "scope": "All eight querying-guide Python blocks plus documented signal normalization, lifecycle payloads, outer rollback and nested savepoint behavior against seeded PostgreSQL; plus the exact complete Product/Category model example; test-owned schema setup, not migration, RLS, concurrent access or HTTP authorization proof",
                     "page_sha256": {page: hashlib.sha256((ROOT / page).read_bytes()).hexdigest() for page in PAGES},
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(evidence['checks'])} installed query checks; disposable schema removed")


if __name__ == "__main__":
    asyncio.run(main())
