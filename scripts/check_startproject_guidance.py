"""Compare installed-wheel project generation while verifying updated CLI guidance."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = '''
import aksara,json,hashlib
from pathlib import Path
package=Path(aksara.__file__).parent
files=('cli/main.py','cli/scaffold.py','cli/templates/__init__.py')
print(json.dumps({'version':aksara.__version__,'path':str(package),
 'source_sha256':{'aksara/'+name:hashlib.sha256((package/name).read_bytes()).hexdigest() for name in files}}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-python', type=Path, required=True)
    parser.add_argument('--development-python', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    env = {key: value for key, value in os.environ.items()
           if key not in {'PYTHONPATH', 'DATABASE_URL'} and not key.startswith('AKSARA_')}
    packages, generations = [], []
    with tempfile.TemporaryDirectory(prefix='aksara-cli-guidance-') as directory:
        for index, python in enumerate((args.baseline_python, args.development_python)):
            root = Path(directory) / str(index); root.mkdir()
            cli = str(python.absolute().parent / 'aksara')

            def command(argv, command_root=root):
                return subprocess.run(argv, cwd=command_root, env=env, text=True, capture_output=True,
                                      timeout=60, check=True)

            package = json.loads(command([str(python.absolute()), '-I', '-c', PROBE]).stdout)
            assert not Path(package.pop('path')).is_relative_to(ROOT)
            packages.append(package)
            help_text = command([cli, 'startproject', '--help']).stdout
            listing = command([cli, 'templates', 'list']).stdout
            outputs = {}
            for template in ('basic', 'blog', 'crm', 'multitenant'):
                name = 'guidance_' + template
                output = command([cli, 'startproject', name, '--template', template]).stdout
                files = {}
                for path in (root / name).rglob('*'):
                    if path.is_file():
                        data = path.read_bytes()
                        if path.name in {'.env', '.env.example'}:
                            data = re.sub(rb'(?m)^AKSARA_STUDIO_SECRET_TOKEN=.*$',
                                          b'AKSARA_STUDIO_SECRET_TOKEN=[NORMALIZED]', data)
                        files[str(path.relative_to(root / name))] = hashlib.sha256(data).hexdigest()
                assert files
                outputs[template] = files
                if index == 1:
                    assert 'pip install -e' not in output
                    assert 'basic template only' in output
                    assert 'domain modules live at project root' in output
                    assert 'template-specific command' in output
                    assert '/getting-started/patterns/' in output
                    assert ('app/models.py' in files) is (template == 'basic')
                    assert ('pyproject.toml' in files) is (template == 'basic')
                    if template != 'basic':
                        readme = (root / name / 'README.md').read_text()
                        assert 'aksara makemigrations --app models --output migrations' in readme
                        assert '--app app.models' not in readme
                        assert readme == (ROOT / 'examples' / template / 'README.md').read_text()
            generations.append(outputs)
            if index == 1:
                assert 'flat example modules' in help_text
                assert 'known isolation and migration' in help_text
                assert '--app models --output migrations' in help_text
                assert 'Customer/Deal/Activity demonstration' in listing
                assert 'Historical tenant example' in listing
    comparisons = []
    for template in generations[0]:
        before, after = generations[0][template], generations[1][template]
        assert before.keys() == after.keys(), template
        changed = sorted(name for name in before if before[name] != after[name])
        assert changed == ['README.md'], (template, changed)
        comparisons.append({'template': template, 'files_compared': len(before),
                            'changed_files': changed, 'baseline_sha256': before, 'development_sha256': after})
    for name, digest in packages[1]['source_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    evidence = {
        'schema_version': 1, 'pass': True, 'packages': packages, 'comparisons': comparisons,
        'cli_guidance_verified': True, 'source_checkout_framework_imports': False,
        'source_sha256': {**packages[1]['source_sha256'],
                          **{f'examples/{name}/README.md': hashlib.sha256((ROOT / 'examples' / name / 'README.md').read_bytes()).hexdigest() for name in ('blog', 'crm', 'multitenant')}},
        'normalization': 'Generated Studio token in .env/.env.example only; no code/config/default normalization',
        'scope': 'Four CLI generations, help/list/post-generation guidance and byte hashes; only README differs from released wheel, including earlier documentation work. No database or runtime startup certification in this gate.',
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    args.output.write_text(json.dumps(evidence, indent=2) + '\n')
    print('PASS: help/list/generation guidance verified; four template outputs differ only in README')


if __name__ == '__main__':
    main()
