"""Run public Python syntax/import contracts against an isolated installed wheel."""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "tests/docs/test_installed_package_truth.py"
VIEWSET_CONTRACT = ROOT / "tests/docs/test_viewset_reference.py"
PROBE = r'''
import hashlib, json, runpy, sys
import aksara
module = runpy.run_path(sys.argv[1])
module['test_public_python_fences_are_syntactically_executable']()
module['test_public_aksara_imports_resolve']()
viewsets = runpy.run_path(sys.argv[2])
viewsets['test_viewset_example_registers_documented_routes']()
viewsets['test_documented_viewset_defaults_and_hooks']()
viewsets['test_documented_serializer_validation']()
viewsets['test_custom_action_example_checks_anonymous_identity']()
viewsets['test_documented_routing_registration_and_discovery']()
viewsets['test_documented_signal_dispatch_example']()
viewsets['test_documented_orm_query_shape']()
viewsets['test_documented_model_defaults']()
viewsets['test_documented_admin_permission_and_mount']()
blocks = list(module['_python_blocks']())
pages = {str(path.relative_to(module['ROOT'])): hashlib.sha256(path.read_bytes()).hexdigest()
         for path in module['_public_markdown']()}
print(json.dumps({'package_version': aksara.__version__, 'package_path': aksara.__file__,
                  'python_blocks': len(blocks), 'page_sha256': pages}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    env = {k: v for k, v in os.environ.items()
           if k not in {"PYTHONPATH", "DATABASE_URL"} and not k.startswith("AKSARA_")}
    with tempfile.TemporaryDirectory(prefix="aksara-doc-imports-") as directory:
        run = subprocess.run([str(args.python.absolute()), "-I", "-c", PROBE, str(CONTRACT), str(VIEWSET_CONTRACT)],
                             cwd=directory, env=env, text=True, capture_output=True,
                             timeout=60, check=True)
    evidence = json.loads(run.stdout)
    assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
    evidence.update({"schema_version": 1, "pass": True,
                     "source_checkout_framework_imports": False,
                     "scope": "Python fence syntax, Aksara import resolution, and documented ViewSet registration/defaults, serializer validation, anonymous denial in the explicit-check action, routing discovery, standalone signal dispatch and Admin hook/anonymous mount checks; not full CRUD, arbitrary snippet execution, or API stability",
                     "contract_sha256": hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
                     "viewset_contract_sha256": hashlib.sha256(VIEWSET_CONTRACT.read_bytes()).hexdigest(),
                     "viewset_route_and_default_checks": "passed",
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {evidence['python_blocks']} Python fences; all documented Aksara imports resolve")


if __name__ == "__main__":
    main()
