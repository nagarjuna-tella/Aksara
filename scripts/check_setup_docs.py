"""Execute setup/layout documentation against an installed wheel and local PostgreSQL."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    'docs/docs/getting-started/installation.md',
    'docs/docs/getting-started/project-layout.md',
    'docs/docs/getting-started/database-setup.md',
    'docs/docs/getting-started/running-your-app.md',
    'docs/docs/reference/runtime-compatibility.md',
]
PROBE = '''
import inspect,json,pathlib,aksara
from aksara.db import Database
from aksara.conf import settings
print(json.dumps(dict(version=aksara.__version__, path=aksara.__file__,
    database_options=list(inspect.signature(Database).parameters),
    selected_database=__import__('urllib.parse',fromlist=['urlsplit']).urlsplit(settings.database_url or '').path)))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    python = str(args.python.absolute())
    cli = str(args.python.absolute().parent / 'aksara')
    dsn = os.environ['DATABASE_URL']
    target = urlsplit(dsn)
    name = target.path.removeprefix('/')
    assert name == 'aksara_test', 'This gate only uses the user-authorized existing test database'
    username = unquote(target.username or 'postgres')
    password = unquote(target.password or '')
    env = {k: v for k, v in os.environ.items()
           if k not in {'PYTHONPATH', 'DATABASE_URL'} and not k.startswith('AKSARA_')}
    env['DATABASE_URL'] = dsn
    checks = []

    def run(argv, cwd, *, child_env=None, stdin=None):
        result = subprocess.run(argv, cwd=cwd, env=child_env or env, input=stdin,
                                text=True, capture_output=True, timeout=60, check=False)
        # Never emit raw CLI output: it may include connection information.
        assert result.returncode == 0, f'Command failed: {Path(argv[0]).name} (exit {result.returncode})'
        return result.stdout

    with tempfile.TemporaryDirectory(prefix='aksara-setup-docs-') as directory:
        root = Path(directory)
        package = json.loads(run([python, '-I', '-c', PROBE], root))
        assert not Path(package.pop('path')).is_relative_to(ROOT)
        assert package['database_options'] == ['database_url', 'min_size', 'max_size']
        assert package.pop('selected_database') == '/aksara_test'
        assert package['version'] in run([cli, '--version'], root)
        assert 'Name: aksara-framework' in run([python, '-m', 'pip', 'show', 'aksara-framework'], root)
        checks.append('installed package/version and Database option names verified')

        run([cli, 'startproject', 'myproject'], root)
        project = root / 'myproject'
        layout = (ROOT / PAGES[1]).read_text()
        trees = re.findall(r'```text\n(.*?)```', layout, re.DOTALL)

        def files_in_tree(tree):
            directories = []
            paths = set()
            for line in tree.splitlines()[1:]:
                match = re.match(r'(.*?)[├└]── (.+)', line)
                assert match, line
                depth, filename = len(match[1]) // 4, match[2]
                directories = directories[:depth]
                if filename.endswith('/'):
                    directories.append(filename[:-1])
                else:
                    paths.add('/'.join([*directories, filename]))
            return paths

        expected = files_in_tree(trees[0])
        assert len(expected) == 18
        actual = {str(p.relative_to(project)) for p in project.rglob('*') if p.is_file()}
        assert actual == expected, sorted(actual.symmetric_difference(expected))
        before_settings = (project / 'settings.py').read_bytes()
        before_urls = (project / 'app/urls.py').read_bytes()
        run([cli, 'startapp', 'inventory'], project)
        app_files = sorted(p.name for p in (project / 'inventory').iterdir())
        assert app_files == sorted(files_in_tree(trees[1]))
        assert len(app_files) == 5
        assert (project / 'settings.py').read_bytes() == before_settings
        assert (project / 'app/urls.py').read_bytes() == before_urls
        checks.append('18 basic files and 5 startapp files; settings/routes not auto-edited')

        # Use a separate empty directory so generated defaults do not alter the
        # interactive prompt sequence. The existing database is not recreated.
        setup = root / 'interactive'
        setup.mkdir()
        output = run([cli, '--plain', '--no-color', 'dbsetup', '--host', target.hostname or 'localhost',
                      '--port', str(target.port or 5432)], setup,
                     stdin=f'{name}\n{username}\n{password}\n')
        assert 'already exists' in output and 'Writing DATABASE_URL' in output
        assert password not in output if password else True
        written = (setup / '.env').read_text().strip().split('=', 1)[1]
        parsed = urlsplit(written)
        assert parsed.path == '/aksara_test'
        assert unquote(parsed.username or '') == username
        assert unquote(parsed.password or '') == password
        checks.append('interactive dbsetup retains existing aksara_test and writes only temporary .env')

        source = (ROOT / PAGES[2]).read_text()
        block = re.search(r'```python title="check_database.py"\n(.*?)```', source, re.DOTALL)
        assert block
        (setup / 'check_database.py').write_text(block[1])
        # Exercise the documented file-loading route, without a URL in the
        # process environment; framework import reads this temporary .env.
        file_env = {k: v for k, v in env.items() if k != 'DATABASE_URL'}
        result = run([python, 'check_database.py'], setup, child_env=file_env)
        assert result.strip() == 'Database connection verified'
        checks.append('exact read-only database probe loads .env, connects and exits cleanly')

        priority_env = dict(env, DATABASE_URL='postgresql://localhost/alias_database',
                            AKSARA_DATABASE_URL='postgresql://localhost/preferred_database')
        precedence = json.loads(run([python, '-I', '-c', PROBE], setup, child_env=priority_env))
        assert precedence['selected_database'] == '/preferred_database'
        checks.append('AKSARA_DATABASE_URL wins over DATABASE_URL and the .env value')

    evidence = {
        'schema_version': 1, 'pass': True, 'package': package,
        'source_checkout_framework_imports': False, 'checks': checks,
        'basic_file_inventory': sorted(expected), 'startapp_file_inventory': app_files,
        'temporary_files_removed': True, 'existing_database_recreated': False,
        'page_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in PAGES},
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scope': 'Installed version/package inspection, real CLI file generation, interactive existing-database dbsetup, exact read-only PostgreSQL probe and URL precedence. No server provisioning, new database creation, operating-system installer, source editable install, production role, RLS or candidate certification.',
    }
    args.output.write_text(json.dumps(evidence, indent=2) + '\n')
    print(f'PASS: {len(checks)} setup checks; temporary files removed, existing database retained')


if __name__ == '__main__':
    main()
