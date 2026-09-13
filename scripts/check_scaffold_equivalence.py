"""Compare generated projects from public baseline and development wheels."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-python', type=Path, required=True)
    parser.add_argument('--candidate-python', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    env = {k: v for k, v in os.environ.items() if k not in {'PYTHONPATH','DATABASE_URL'} and not k.startswith('AKSARA_')}
    outputs = []
    packages = []
    with tempfile.TemporaryDirectory(prefix='aksara-scaffold-compare-') as directory:
        for index, python in enumerate((args.baseline_python,args.candidate_python)):
            root = Path(directory)/str(index); root.mkdir()
            probe = subprocess.run([str(python.absolute()),'-I','-c','import aksara,json,hashlib,pathlib,aksara.cli.scaffold as s; print(json.dumps(dict(version=aksara.__version__,path=aksara.__file__,scaffold_sha256=hashlib.sha256(pathlib.Path(s.__file__).read_bytes()).hexdigest())))'],cwd=root,env=env,capture_output=True,text=True,check=True)
            package = json.loads(probe.stdout)
            assert not Path(package.pop('path')).is_relative_to(ROOT)
            packages.append(package)
            subprocess.run([str(python.absolute().parent/'aksara'),'startproject','scaffold_probe'],cwd=root,env=env,capture_output=True,text=True,check=True)
            project=root/'scaffold_probe'
            packages[-1]['readme_sha256']=hashlib.sha256((project/'README.md').read_bytes()).hexdigest()
            files={}
            for path in project.rglob('*'):
                if path.is_file():
                    data=path.read_bytes()
                    if path.name in ('.env','.env.example'):
                        data=re.sub(rb'(?m)^AKSARA_STUDIO_SECRET_TOKEN=.*$',b'AKSARA_STUDIO_SECRET_TOKEN=[NORMALIZED]',data)
                    data=data.replace(b'0.7.2-rc1',b'[RELEASE_VERSION]')
                    data=data.replace(b'0.7.2rc1',b'[RELEASE_VERSION]')
                    data=data.replace(b'0.7.1-rc1',b'[RELEASE_VERSION]')
                    data=data.replace(b'0.7.1rc1',b'[RELEASE_VERSION]')
                    data=data.replace(b'0.7.1',b'[RELEASE_VERSION]')
                    data=data.replace(b'0.7.0',b'[RELEASE_VERSION]')
                    files[str(path.relative_to(project))]=hashlib.sha256(data).hexdigest()
            outputs.append(files)
    assert outputs[0].keys()==outputs[1].keys()
    changed=sorted(path for path in outputs[0] if outputs[0][path]!=outputs[1][path])
    assert changed==['README.md'],changed
    evidence={'schema_version':1,'pass':True,'packages':packages,'changed_generated_files':changed,
              'files_compared':len(outputs[0]),'baseline_file_sha256':outputs[0],
              'development_file_sha256':outputs[1],
              'normalization':'Generated Studio token value in .env/.env.example plus exact 0.7.0/0.7.1rc1/0.7.1/0.7.2rc1 version spellings; no other executable/config/dependency normalization',
              'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    args.output.write_text(json.dumps(evidence,indent=2)+'\n')
    print(f'PASS: {len(outputs[0])} generated files compared; only README differs')


if __name__=='__main__':
    main()
