"""Record whether an unchanged generated project supports its editable install."""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    python = str(args.python.absolute())
    cli = str(args.python.absolute().parent / 'aksara')
    env = {k: v for k, v in os.environ.items() if k not in {'PYTHONPATH', 'DATABASE_URL'} and not k.startswith('AKSARA_')}
    with tempfile.TemporaryDirectory(prefix='aksara-scaffold-install-') as directory:
        root = Path(directory)
        probe = subprocess.run([python, '-I', '-c', 'import aksara,json,hashlib,pathlib,aksara.cli.scaffold as scaffold; print(json.dumps(dict(version=aksara.__version__,path=aksara.__file__,scaffold_sha256=hashlib.sha256(pathlib.Path(scaffold.__file__).read_bytes()).hexdigest())))'],cwd=root,env=env,capture_output=True,text=True,check=True)
        package = json.loads(probe.stdout)
        assert not Path(package.pop('path')).is_relative_to(ROOT)
        subprocess.run([cli, 'startproject', 'scaffold_probe'],cwd=root,env=env,capture_output=True,text=True,check=True)
        project = root / 'scaffold_probe'
        run = subprocess.run([python, '-m', 'pip', 'install', '-e', '.[dev]'],cwd=project,env=env,capture_output=True,text=True,timeout=120,check=False)
        output = run.stdout + run.stderr
        evidence = {
            'schema_version': 1, 'package': package,
            'editable_install_success': run.returncode == 0, 'exit_code': run.returncode,
            'hatch_file_selection_error': 'Unable to determine which files to ship inside the wheel' in output,
            'missing_project_package': 'no directory that matches the name of your project (scaffold_probe)' in output,
            'generated_pyproject_sha256': hashlib.sha256((project / 'pyproject.toml').read_bytes()).hexdigest(),
            'source_checkout_framework_imports': False,
            'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': 'Unchanged generated project editable packaging only; failure does not test server startup or dependency-only local development',
        }
    args.output.write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence))
    raise SystemExit(run.returncode)


if __name__ == '__main__':
    main()
