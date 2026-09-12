"""Execute the public Admin permission and relation helper against an installed wheel and PostgreSQL."""

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
SNIPPETS = {"admin_permissions.py": ("docs/docs/admin/admin-permissions.md", "app/admin_permissions.py")}
PROBE = r'''
import asyncio, inspect, json, os, sys, types
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import aksara
from aksara import Model, fields, finalize_relations
from aksara.db import Database
from aksara.contrib.admin import AdminSite
class Author(Model):
    name=fields.String(max_length=100)
    class Meta: table_name='admin_probe_authors'
class Post(Model):
    title=fields.String(max_length=200)
    author=fields.ForeignKey(Author,nullable=True,related_name='posts')
    class Meta: table_name='admin_probe_posts'
example = {'__name__': 'relation_guide_example'}
exec(Path('relation_example.py').read_text(), example)
finalize_relations()
module=types.ModuleType('app.models');module.Author=Author
sys.modules['app']=types.ModuleType('app');sys.modules['app.models']=module
namespace={'__name__':'app.admin_permissions','__package__':'app'}
exec(Path('admin_permissions.py').read_text(),namespace)
checks=[]
def passed(name,condition):
    assert condition,name
    checks.append(name)
async def main():
    db=Database(os.environ['DATABASE_URL'],min_size=1,max_size=2)
    await db.connect()
    try:
        await db.execute('CREATE TABLE admin_probe_authors (id UUID PRIMARY KEY, name VARCHAR(100), created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ)')
        await db.execute('CREATE TABLE admin_probe_posts (id UUID PRIMARY KEY, title VARCHAR(200), author_id UUID REFERENCES admin_probe_authors(id), created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ)')
        author=await Author.objects.create(name='Owner')
        post=await Post.objects.create(title='Owned',author=author)
        unassigned=await Post.objects.create(title='Unassigned',author=None)
        admin=namespace['PostAdmin'](Post,AdminSite())
        request=SimpleNamespace(state=SimpleNamespace(user=None))
        passed('anonymous denied',not await admin.has_change_permission(request,post))
        request.state.user=SimpleNamespace(id=author.id,is_staff=True,is_superuser=False)
        passed('owner allowed with database lookup',await admin.has_change_permission(request,post))
        passed('nullable missing author denied',not await admin.has_change_permission(request,unassigned))
        request.state.user.id=uuid4()
        passed('other staff denied',not await admin.has_change_permission(request,post))
        request.state.user.is_staff=False
        passed('nonstaff denied',not await admin.has_change_permission(request,post))
        passed('forward access is stored id',post.author==author.id and post.author_id==author.id)
        try: post.get_related('author')
        except ValueError: checks.append('unloaded related access raises ValueError')
        else: raise AssertionError('unloaded access unexpectedly succeeded')
        loaded=(await Post.objects.filter(id=post.id).select_related('author').all())[0]
        related=loaded.get_related('author')
        passed('eager accessor is synchronous model',not inspect.isawaitable(related) and related.id==author.id)
        null_loaded=(await Post.objects.filter(id=unassigned.id).select_related('author').all())[0]
        passed('eager null relation is None',null_loaded.get_related('author') is None)
        passed('reverse FK filter executes and returns rows',[row.id for row in await author.posts.filter(title='Owned')]==[post.id])
        models = [example[name] for name in ('BlogAuthor', 'BlogCategory', 'BlogTag', 'BlogPost', 'BlogProfile')]
        # Test-owned DDL; this does not validate migration discovery or generation.
        for model in models:
            columns = [field.get_column_definition() for field in model._fields.values()]
            definitions = [value for value in columns if value]
            await db.execute('CREATE TABLE "' + model.__tablename__ + '" (' + ', '.join(definitions) + ')')
        BlogAuthor, BlogCategory, BlogTag, BlogPost, BlogProfile = models
        m2m = BlogPost._m2m_fields['tags']
        await db.execute(m2m.get_join_table_sql())
        await example['demo']()
        user = await BlogAuthor.objects.get(email='jane@example.com')
        blog = await BlogPost.objects.get(title='Getting Started with Python')
        passed('relation example created the post', await BlogPost.objects.count() == 1)
        passed('relation example M2M membership', {tag.name for tag in await blog.tags.all()} == {'Tutorial', 'Beginner'})
        passed('relation example reverse FK', [row.id for row in await user.posts.all()] == [blog.id])
        profile = await user.profile()
        passed('relation example reverse O2O', profile.bio == 'Tech writer')
        category = await BlogCategory.objects.get(slug='tech')
        passed('relation example self reference', [row.slug for row in await category.children.all()] == ['python'])
        tag = await BlogTag.objects.get(name='Tutorial')
        passed('relation example reverse M2M', [row.id for row in await tag.posts.all()] == [blog.id])

    finally:
        await db.disconnect()
    print('ADMIN_RELATION_EVIDENCE='+json.dumps({'checks':checks,'package_version':aksara.__version__,'package_path':aksara.__file__}))
asyncio.run(main())
'''


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("AKSARA_DATABASE_URL") or os.environ["DATABASE_URL"]
    schema = "aksara_v071_admin_relation_" + uuid4().hex[:12]
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
            with tempfile.TemporaryDirectory(prefix="aksara-admin-relation-docs-") as directory:
                root = Path(directory)
                for filename, (page, title) in SNIPPETS.items():
                    text = (ROOT / page).read_text()
                    source = re.search(r'```python title="' + re.escape(title) + r'"\n(.*?)```', text, re.DOTALL).group(1)
                    (root / filename).write_text(source)
                relation_page = (ROOT / "docs/docs/orm/relations.md").read_text()
                complete = relation_page.split('## Complete relation example', 1)[1]
                source = re.search(r'```python\n(.*?)```', complete, re.DOTALL).group(1)
                (root / 'relation_example.py').write_text(source)
                run = await asyncio.to_thread(
                    subprocess.run, [str(args.python.absolute()), "-I", "-c", PROBE],
                    cwd=root, env=env, capture_output=True, text=True, timeout=60,
                )
                if run.returncode:
                    message = (run.stderr or run.stdout).replace(scoped, "[REDACTED]").replace(dsn, "[REDACTED]")
                    raise RuntimeError(message)
                evidence = json.loads(next(line.removeprefix("ADMIN_RELATION_EVIDENCE=") for line in run.stdout.splitlines()
                                           if line.startswith("ADMIN_RELATION_EVIDENCE=")))
                assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
        finally:
            await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
        assert not await connection.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = $1", schema)
    finally:
        await connection.close()
    evidence.update({"schema_version": 1, "pass": True,
                     "source_checkout_framework_imports": False, "disposable_schema_removed": True,
                     "scope": "Installed exact Admin hook and real forward/reverse/eager FK access; test-owned DDL and admin-role fixture, plus exact complete relation example with FK/O2O/self/M2M execution; not migrations, HTTP authentication or RLS proof",
                     "page_sha256": {page: hashlib.sha256((ROOT / page).read_bytes()).hexdigest() for page in [*(page for page, _ in SNIPPETS.values()), "docs/docs/orm/relations.md"]},
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(evidence['checks'])} installed Admin/relation checks; disposable schema removed")


if __name__ == "__main__":
    asyncio.run(main())
