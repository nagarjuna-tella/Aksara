"""Execute the documented media model against an installed wheel, PostgreSQL and disposable local storage."""

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
SNIPPETS = {"models.py": ("docs/docs/advanced/media-and-email.md", "app/asset_models.py")}
PROBE = r'''
import asyncio, io, json, os
from pathlib import Path
import aksara
from PIL import Image
from aksara import transaction
from aksara.conf import configure
from aksara.db import Database
from aksara.migrations.autodetector import model_to_create_table_operation
from aksara.storage import FieldFile
configure(media_storage='filesystem',media_root=str(Path('media').resolve()),media_url='/media/')
namespace={'__name__':'documented_assets'}
exec(Path('models.py').read_text(),namespace)
Asset=namespace['Asset']
checks=[]
def passed(name,condition):
    assert condition,name
    checks.append(name)
async def main():
    db=Database(os.environ['DATABASE_URL'],min_size=1,max_size=2)
    await db.connect()
    try:
        await model_to_create_table_operation(Asset).apply(db)
        stream=io.BytesIO();Image.new('RGB',(2,2),(10,20,30)).save(stream,format='PNG')
        asset=await Asset.objects.create(name='First',file=('report.pdf',b'%PDF-demo'),preview=('preview.png',stream.getvalue()))
        passed('file and image uploads stored',await asset.file.exists() and await asset.preview.exists())
        passed('public wrappers expose names',isinstance(asset.file,FieldFile) and asset.file.name.startswith('assets/') and asset.preview.name.startswith('previews/'))
        passed('wrapper read and size',await asset.file.read()==b'%PDF-demo' and await asset.file.size()==9)
        loaded=await Asset.objects.get(id=asset.id)
        passed('database reload wraps stored reference',loaded.file.name==asset.file.name and loaded.preview.name==asset.preview.name)
        with Image.open(io.BytesIO(await loaded.preview.read())) as image:
            passed('image content survives persistence',image.size==(2,2))
        old_file=asset.file.name
        storage=asset.file.storage
        asset.file=('replacement.pdf',b'%PDF-new')
        await asset.save()
        passed('replacement preserves old stored file',await storage.exists(old_file) and await asset.file.read()==b'%PDF-new')
        old_preview=asset.preview.name
        await asset.preview.delete()
        passed('wrapper deletion clears in-memory reference',asset.preview.name is None and not await storage.exists(old_preview))
        reloaded=await Asset.objects.get(id=asset.id)
        passed('wrapper deletion does not persist database clearing',reloaded.preview.name==old_preview and not await reloaded.preview.exists())
        await asset.save()
        passed('explicit save persists nullable clearing',(await Asset.objects.get(id=asset.id)).preview.name is None)
        rollback_asset=None
        try:
            async with transaction.atomic():
                rollback_asset=await Asset.objects.create(name='Rollback',file=('rollback.pdf',b'%PDF-rollback'))
                raise RuntimeError('intentional rollback')
        except RuntimeError as error:
            assert str(error)=='intentional rollback'
        passed('rollback removes database row',not await Asset.objects.filter(id=rollback_asset.id).exists())
        passed('rollback leaves externally stored bytes',await rollback_asset.file.exists())
        retained=asset.file.name
        await asset.delete()
        passed('model deletion leaves stored bytes',await storage.exists(retained))
        # Image validation must happen before this invalid upload is stored.
        before=set(Path('media').rglob('*'))
        try: await Asset.objects.create(name='Invalid',file='assets/already-stored.pdf',preview=('bad.png',b'not an image'))
        except ValueError: pass
        else: raise AssertionError('Invalid image accepted')
        passed('invalid image creates no file or row',set(Path('media').rglob('*'))==before and not await Asset.objects.filter(name='Invalid').exists())
        for name in (old_file,retained,rollback_asset.file.name): await storage.delete(name)
        passed('explicit orphan cleanup removes files',not any(path.is_file() for path in Path('media').rglob('*')))
    finally:
        await db.disconnect()
    print('MEDIA_LIFECYCLE_EVIDENCE='+json.dumps({'checks':checks,'package_version':aksara.__version__,'package_path':aksara.__file__}))
asyncio.run(main())
'''


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("AKSARA_DATABASE_URL") or os.environ["DATABASE_URL"]
    schema = "aksara_v071_media_" + uuid4().hex[:12]
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
            with tempfile.TemporaryDirectory(prefix="aksara-media-lifecycle-") as directory:
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
                evidence = json.loads(next(line.removeprefix("MEDIA_LIFECYCLE_EVIDENCE=") for line in run.stdout.splitlines()
                                           if line.startswith("MEDIA_LIFECYCLE_EVIDENCE=")))
                assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
        finally:
            await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
        assert not await connection.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = $1", schema)
    finally:
        await connection.close()
    evidence.update({"schema_version": 1, "pass": True,
                     "source_checkout_framework_imports": False, "disposable_schema_removed": True,
                     "scope": "Exact media model, autodetected CreateTable operation, PostgreSQL persistence and local file/image lifecycle; not full migration history, RLS, protected HTTP uploads, S3, SMTP or content-safety certification",
                     "page_sha256": {page: hashlib.sha256((ROOT / page).read_bytes()).hexdigest() for page in [*(page for page, _ in SNIPPETS.values()), "docs/docs/orm/fields.md"]},
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(evidence['checks'])} installed media-lifecycle checks; disposable schema removed")


if __name__ == "__main__":
    asyncio.run(main())
