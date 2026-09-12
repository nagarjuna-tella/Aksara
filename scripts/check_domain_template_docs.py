"""Generate domain templates from an installed wheel and execute their public setup commands."""

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
from urllib.request import Request, urlopen
from uuid import uuid4

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
PAGES = {
    'blog': 'docs/docs/patterns/blog.md',
    'crm': 'docs/docs/patterns/crm.md',
    'multitenant': 'docs/docs/patterns/multitenant.md',
}


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--require-updated-readme', action='store_true', help='Require generated README commands to match the checked pattern page')
    args = parser.parse_args()
    python = str(args.python.absolute())
    cli = str(args.python.absolute().parent / 'aksara')
    dsn = os.environ.get('AKSARA_DATABASE_URL') or os.environ['DATABASE_URL']
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('AKSARA_', 'OPENAI_', 'ANTHROPIC_', 'AZURE_', 'OLLAMA_'))
           and k not in {'DATABASE_URL', 'PYTHONPATH', 'AI_DEFAULT_PROVIDER'}}
    observations = []
    admin = await asyncpg.connect(dsn)
    try:
        for name, page in PAGES.items():
            schema = 'aksara_v071_template_' + uuid4().hex[:12]
            parsed = urlsplit(dsn)
            query = dict(parse_qsl(parsed.query)); query['search_path'] = schema
            scoped = urlunsplit(parsed._replace(query=urlencode(query)))
            env.update(DATABASE_URL=scoped, AKSARA_DATABASE_URL=scoped)
            server = None

            def redact(value, scoped_dsn=scoped):
                return re.sub(r'postgres(?:ql)?://[^\s]+', '[REDACTED_DSN]',
                              value.replace(scoped_dsn, '[REDACTED]').replace(dsn, '[REDACTED]'))

            async def command(argv, cwd):
                run = await asyncio.to_thread(subprocess.run, argv, cwd=cwd, env=env,
                                              capture_output=True, text=True, timeout=60, check=False)
                if run.returncode:
                    raise RuntimeError(redact(run.stdout + run.stderr)[-4000:])
                return run

            await admin.execute(f'CREATE SCHEMA "{schema}"')
            try:
                with tempfile.TemporaryDirectory(prefix='aksara-domain-template-') as directory:
                    root = Path(directory)
                    probe = await command([python, '-I', '-c',
                        'import aksara,json;print(json.dumps(dict(version=aksara.__version__,path=aksara.__file__)))'], root)
                    package = json.loads(probe.stdout)
                    assert not Path(package.pop('path')).is_relative_to(ROOT)
                    listed = await command([cli, 'templates', 'list'], root)
                    assert all(template in listed.stdout for template in ('basic', 'blog', 'crm', 'multitenant'))
                    blocks = re.findall(r'```bash\n(.*?)```', (ROOT / page).read_text(), re.DOTALL)
                    commands = [shlex.split(line) for line in blocks[0].splitlines() if line.strip()]
                    assert len(commands) == 5
                    assert commands[0][0:2] == ['aksara', 'startproject']
                    assert commands[0][-2:] == ['--template', name]
                    project = root / commands[0][2]
                    await command([cli, *commands[0][1:]], root)
                    assert commands[1] == ['cd', project.name]
                    if args.require_updated_readme:
                        readme = (project / 'README.md').read_text()
                        readme_blocks = re.findall(r'```bash\n(.*?)```', readme, re.DOTALL)
                        startup = next(block for block in readme_blocks if block.startswith('aksara makemigrations'))
                        assert [shlex.split(line) for line in startup.splitlines()] == commands[2:5]
                    files = sorted(str(p.relative_to(project)) for p in project.rglob('*') if p.is_file())
                    assert all((project / filename).is_file() for filename in ('models.py', 'main.py', 'settings.py'))
                    assert not any((project / filename).exists() for filename in ('pyproject.toml', '.env', 'app'))
                    discovery = None
                    if name == 'multitenant':
                        inspected = await command([python, '-I', '-c', """
import sys,os,json
sys.path.insert(0,os.getcwd())
from aksara.cli.main import discover_models
from aksara.registry import ModelRegistry
import models
def identity(model):return {'module':model.__module__,'table':model.__tablename__}
before=identity(ModelRegistry.get('User'))
discover_models('models',silent=True)
after=identity(ModelRegistry.get('User'))
print('DISCOVERY='+json.dumps({'declared_user':identity(models.User),'before':before,'after':after}))
"""], project)
                        discovery = json.loads(next(line.removeprefix('DISCOVERY=') for line in inspected.stdout.splitlines() if line.startswith('DISCOVERY=')))
                        assert discovery['declared_user']['table'] == 'tenant_users'
                        assert discovery['before']['table'] == 'tenant_users'
                        assert discovery['after']['table'] == 'aksara_users', discovery
                    for argv in commands[2:4]:
                        await command([cli, *argv[1:]], project)
                    tables = await admin.fetch('SELECT tablename FROM pg_tables WHERE schemaname=$1 ORDER BY tablename', schema)
                    table_names = [row['tablename'] for row in tables]
                    expected = {'blog': {'posts', 'comments'}, 'crm': {'customers', 'deals', 'activities'},
                                'multitenant': {'tenants', 'tenant_users', 'projects'}}[name]
                    missing_tables = sorted(expected - set(table_names))
                    assert missing_tables == (['tenant_users'] if name == 'multitenant' else []), (name, table_names)
                    resources = {'blog': ('posts', 'comments'), 'crm': ('customers', 'deals', 'activities'),
                                 'multitenant': ('tenants', 'users', 'projects')}[name]
                    with socket.socket() as sock:
                        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
                    argv = commands[4].copy()
                    assert argv[:3] == ['aksara', 'run', 'main:app']
                    argv[argv.index('--port') + 1] = str(port)
                    with (root / 'server.log').open('w+') as log:
                        server = await asyncio.create_subprocess_exec(cli, *argv[1:], cwd=project, env=env,
                                                                     stdout=log, stderr=log)

                        def request(path, *, payload=None, request_port=port):
                            req = Request(f'http://127.0.0.1:{request_port}' + path,
                                          data=json.dumps(payload).encode() if payload is not None else None,
                                          headers={'Content-Type': 'application/json'})
                            try:
                                with urlopen(req, timeout=2) as response:
                                    return response.status, json.loads(response.read())
                            except HTTPError as error:
                                return error.code, None

                        for _ in range(100):
                            try:
                                if (await asyncio.to_thread(request, '/health'))[0] == 200:
                                    break
                            except (OSError, URLError):
                                pass
                            if server.returncode is not None:
                                log.seek(0); raise RuntimeError(redact(log.read())[-4000:])
                            await asyncio.sleep(0.1)
                        else:
                            log.seek(0); raise RuntimeError('Template server did not become ready: ' + redact(log.read())[-4000:])
                        curl_commands = [shlex.split(line) for line in blocks[1].splitlines() if line.strip()]
                        assert len(curl_commands) == 2
                        bodies = []
                        for curl_argv in curl_commands:
                            assert curl_argv[:2] == ['curl', '--fail']
                            curl_argv = [arg.replace(':8000/', ':' + str(port) + '/') for arg in curl_argv]
                            result = await command(curl_argv, project)
                            bodies.append(json.loads(result.stdout))
                        health, openapi = bodies
                        assert health['status'] == 'healthy'
                        paths = openapi['paths']
                        for resource in resources:
                            assert 'get' in paths[f'/api/{resource}/']
                            detail = next(path for path in paths if path.startswith(f'/api/{resource}/{{'))
                            assert 'patch' in paths[detail] and 'put' not in paths[detail]
                        denied = None
                        if name in ('blog', 'crm'):
                            resource, payload = ('posts', {'title': 'Draft', 'slug': 'draft', 'content': 'Example post', 'tags': []}) if name == 'blog' else ('customers', {'name': 'Example'})
                            denied, _ = await asyncio.to_thread(request, '/api/' + resource + '/', payload=payload)
                            assert denied == 403, (name, denied)
                        server.terminate(); await asyncio.wait_for(server.wait(), 10); server = None
                    observations.append({
                        'template': name, 'package': package, 'generated_files': files,
                        'flat_layout_without_package_metadata': True,
                        'generated_readme_commands_verified': args.require_updated_readme,
                        'documented_commands': commands, 'documented_curl_commands_executed': True,
                        'template_listing_executed': True, 'port_substitution': 'ephemeral local port for server isolation',
                        'migration_commands_exit_zero': True, 'tables': table_names,
                        'missing_declared_tables': missing_tables, 'template_schema_complete': not missing_tables,
                        'model_discovery': discovery,
                        'health_status': 200, 'openapi_status': 200,
                        'generated_update_method': 'PATCH', 'unauthenticated_create_status': denied,
                        'server_stopped': True,
                    })
            finally:
                if server is not None and server.returncode is None:
                    server.terminate(); await asyncio.wait_for(server.wait(), 10)
                await admin.execute(f'DROP SCHEMA "{schema}" CASCADE')
            assert not await admin.fetchval('SELECT 1 FROM pg_namespace WHERE nspname=$1', schema)
    finally:
        await admin.close()
    evidence = {
        'schema_version': 1, 'pass': True, 'source_checkout_framework_imports': False,
        'disposable_schemas_removed': True, 'templates': observations,
        'all_template_schemas_complete': False,
        'known_defects': ['MIGRATION-001: multitenant User name collision omits tenant_users'],
        'scope': 'Three installed domain-template copies, exact setup commands with ephemeral ports, real PostgreSQL migrations including expected multitenant missing-table defect, health/OpenAPI and blog/CRM anonymous create denial; not positive CRUD, custom action authorization, tenant isolation, provider execution or production readiness',
        'page_sha256': {page: hashlib.sha256((ROOT / page).read_bytes()).hexdigest() for page in PAGES.values()},
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    args.output.write_text(json.dumps(evidence, indent=2) + '\n')
    print('PASS: 3 domain-template observations verified; multitenant schema incomplete as recorded; disposable schemas removed')


if __name__ == '__main__':
    asyncio.run(main())
