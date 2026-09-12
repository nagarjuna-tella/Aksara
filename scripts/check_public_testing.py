"""Run the testing guide's exact pytest example against an isolated installed wheel."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'docs/docs/advanced/testing.md'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = re.search(r'```python title="tests/test_ticket_rules.py"\n(.*?)```', PAGE.read_text(), re.DOTALL)[1]
    env = {k: v for k, v in os.environ.items()
           if k not in {'PYTHONPATH', 'DATABASE_URL', 'PYTEST_ADDOPTS'} and not k.startswith('AKSARA_')}
    env['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    with tempfile.TemporaryDirectory(prefix='aksara-testing-guide-') as directory:
        root = Path(directory)
        (root / 'tests').mkdir()
        (root / 'tests/test_ticket_rules.py').write_text(source)
        package = subprocess.run(
            [str(args.python.absolute()), '-I', '-c',
             'import aksara,json;print(json.dumps({"version":aksara.__version__,"path":aksara.__file__}))'],
            cwd=root, env=env, capture_output=True, text=True, check=True,
        )
        package = json.loads(package.stdout)
        assert not Path(package.pop('path')).is_relative_to(ROOT)
        run = subprocess.run(
            [str(args.python.absolute()), '-I', '-m', 'pytest', 'tests/test_ticket_rules.py', '-q'],
            cwd=root, env=env, capture_output=True, text=True, timeout=60, check=False,
        )
        if run.returncode:
            raise RuntimeError(run.stdout + run.stderr)
        assert '3 passed' in run.stdout, run.stdout
    evidence = {
        'schema_version': 1, 'pass': True, 'package_version': package['version'],
        'source_checkout_framework_imports': False, 'tests_passed': 3,
        'scope': 'Exact standalone serializer and permission unit tests; no database, HTTP authentication, RLS or rollback-isolation proof',
        'command': 'python -I -m pytest tests/test_ticket_rules.py -q',
        'page_sha256': {str(PAGE.relative_to(ROOT)): hashlib.sha256(PAGE.read_bytes()).hexdigest()},
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    args.output.write_text(json.dumps(evidence, indent=2) + '\n')
    print('PASS: 3 exact testing-guide unit tests against installed wheel')


if __name__ == '__main__':
    main()
