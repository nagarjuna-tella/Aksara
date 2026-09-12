"""Run the generated README dependency, migration and local server setup path."""

import argparse
import asyncio
import hashlib
import json
import os
import re
import shlex
import socket
import subprocess
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import urlopen
from uuid import uuid4

import asyncpg

ROOT = Path(__file__).resolve().parents[1]


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    python = str(args.python.absolute())
    cli = str(args.python.absolute().parent / 'aksara')
    dsn = os.environ['DATABASE_URL']
    schema = 'aksara_v071_scaffold_' + uuid4().hex[:12]
    parsed = urlsplit(dsn)
    query = dict(parse_qsl(parsed.query)); query['search_path'] = schema
    scoped = urlunsplit(parsed._replace(query=urlencode(query)))
    env = {k: v for k, v in os.environ.items() if k not in {'PYTHONPATH', 'DATABASE_URL'} and not k.startswith('AKSARA_')}
    secrets = [dsn, scoped]
    def redact(value):
        for secret in secrets:
            value = value.replace(secret, '[REDACTED]')
        return re.sub(r'postgres(?:ql)?://[^\s]+', '[REDACTED_DSN]', value)
    checks = []
    async def command(argv, cwd, accepted=(0,)):
        run = await asyncio.to_thread(subprocess.run, argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=60, check=False)
        if run.returncode not in accepted:
            raise RuntimeError(redact(run.stdout + run.stderr)[-4000:])
        return run
    admin = await asyncpg.connect(dsn)
    server = None
    try:
        await admin.execute(f'CREATE SCHEMA "{schema}"')
        try:
            with tempfile.TemporaryDirectory(prefix='aksara-scaffold-startup-') as directory:
                root = Path(directory)
                probe = await command([python, '-I', '-c', 'import aksara,json,hashlib,pathlib,aksara.cli.scaffold as s; print(json.dumps(dict(version=aksara.__version__,path=aksara.__file__,scaffold_sha256=hashlib.sha256(pathlib.Path(s.__file__).read_bytes()).hexdigest())))'],root)
                package = json.loads(probe.stdout)
                assert not Path(package.pop('path')).is_relative_to(ROOT)
                await command([cli, 'startproject', 'scaffold_probe'],root)
                project = root / 'scaffold_probe'
                readme = (project / 'README.md').read_text()
                install = next(line for line in readme.splitlines() if line.startswith('pip install '))
                await command([python, '-m', 'pip', *shlex.split(install)[1:]],project)
                checks.append('exact README dependency install succeeds')
                envfile = project / '.env'
                original = envfile.read_text()
                for line in original.splitlines():
                    if line.startswith('AKSARA_STUDIO_SECRET_TOKEN='):
                        secrets.append(line.split('=',1)[1])
                envfile.write_text(re.sub(r'^DATABASE_URL=.*$', 'DATABASE_URL='+scoped, original, flags=re.MULTILINE))
                await command([cli, 'makemigrations', '--app', 'app.models'],project)
                await command([cli, 'migrate'],project)
                checks.append('documented migration commands succeed on generated stubs')
                doctor = await command([cli, 'doctor', 'launch-check'],project,accepted=(0,1))
                doctor_text = redact(doctor.stdout + doctor.stderr)
                assert 'PostgreSQL connection successful' in doctor_text and 'Migrations are up to date' in doctor_text
                assert '✗' not in doctor_text
                checks.append('Doctor confirms database and migrations without failures')
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
                with (root/'server.log').open('w+') as log:
                    server = await asyncio.create_subprocess_exec(cli,'dev','--no-reload','--port',str(port),cwd=project,env=env,stdout=log,stderr=log)
                    def status(path):
                        try:
                            with urlopen(f'http://127.0.0.1:{port}'+path,timeout=1) as response:
                                return response.status
                        except HTTPError as error:
                            return error.code
                    for _ in range(100):
                        try:
                            if await asyncio.to_thread(status,'/docs')==200: break
                        except (OSError,URLError): pass
                        if server.returncode is not None:
                            log.seek(0); raise RuntimeError(redact(log.read())[-4000:])
                        await asyncio.sleep(0.1)
                    else: raise RuntimeError('Scaffold dev server did not become ready')
                    surfaces={path:await asyncio.to_thread(status,path) for path in ('/','/docs','/admin/','/ai/tools/mcp','/mcp/','/studio/ui')}
                    assert surfaces=={'/':200,'/docs':200,'/admin/':200,'/ai/tools/mcp':200,'/mcp/':404,'/studio/ui':404},surfaces
                    checks.append('documented default surfaces match; admin follows login redirect')
                    server.terminate(); await asyncio.wait_for(server.wait(),10); server=None
                    checks.append('development server stops cleanly')
                evidence={'schema_version':1,'pass':True,'package':package,'checks':checks,'surfaces':surfaces,'doctor_exit':doctor.returncode,'doctor_output':doctor_text,'readme_sha256':hashlib.sha256(readme.encode()).hexdigest(),'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'scope':'Generated stubs, exact dependency install, .env database edit, migrations, Doctor and dev --no-reload with ephemeral port; no application resource, interactive dbsetup, production role, reload watcher or application packaging claim'}
        finally:
            if server is not None and server.returncode is None:
                server.terminate(); await asyncio.wait_for(server.wait(),10)
            await admin.execute(f'DROP SCHEMA "{schema}" CASCADE')
        assert not await admin.fetchval('SELECT 1 FROM pg_namespace WHERE nspname=$1',schema)
    finally:
        await admin.close()
    evidence['disposable_schema_removed']=True
    args.output.write_text(json.dumps(evidence,indent=2)+'\n')
    print(f"PASS: {len(checks)} scaffold startup checks; schema removed")


if __name__ == '__main__':
    asyncio.run(main())
