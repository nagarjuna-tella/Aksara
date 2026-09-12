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
LOCALIZATION_CONTRACT = ROOT / "tests/docs/test_localization_reference.py"
EXCEPTION_CONTRACT = ROOT / "tests/docs/test_exception_reference.py"
AI_DEBUG_CONTRACT = ROOT / "tests/docs/test_ai_debug_reference.py"
MIDDLEWARE_CONTRACT = ROOT / "tests/docs/test_middleware_reference.py"
MODEL_META_CONTRACT = ROOT / "tests/docs/test_model_meta_reference.py"
INSPECTOR_CONTRACT = ROOT / "tests/docs/test_inspector_reference.py"
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
viewsets['test_documented_admin_mount']()
viewsets['test_documented_relation_access_shapes']()
viewsets['test_documented_field_reference_contracts']()
localization = runpy.run_path(sys.argv[3])
localization['test_localization_examples']()
exceptions = runpy.run_path(sys.argv[4])
exceptions['test_exception_reference_types']()
exceptions['test_exception_http_example']()
exceptions['test_debug_page_example_boundaries']()
ai_debug = runpy.run_path(sys.argv[5])
ai_debug['test_ai_debug_example_and_context']()
middleware = runpy.run_path(sys.argv[6])
for name in ('test_request_id_example', 'test_tenant_extraction_example', 'test_logging_example', 'test_timing_example'):
    middleware[name]()
metadata = runpy.run_path(sys.argv[7])
metadata['test_metadata_guide_example']()
import contextlib, io
inspectors = runpy.run_path(sys.argv[8])
with contextlib.redirect_stdout(io.StringIO()):
    inspectors['test_inspector_examples']()
inspectors['test_synthetic_analyze_lacks_warning']()
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
        run = subprocess.run([str(args.python.absolute()), "-I", "-c", PROBE, str(CONTRACT), str(VIEWSET_CONTRACT), str(LOCALIZATION_CONTRACT), str(EXCEPTION_CONTRACT), str(AI_DEBUG_CONTRACT), str(MIDDLEWARE_CONTRACT), str(MODEL_META_CONTRACT), str(INSPECTOR_CONTRACT)],
                             cwd=directory, env=env, text=True, capture_output=True,
                             timeout=60, check=True)
    evidence = json.loads(run.stdout)
    assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
    evidence.update({"schema_version": 1, "pass": True,
                     "source_checkout_framework_imports": False,
                     "scope": "Python fence syntax, Aksara import resolution, and documented ViewSet registration/defaults, serializer validation, anonymous denial in the explicit-check action, routing discovery, standalone signal dispatch and Admin anonymous mount, relation-access shape and field declaration/conversion and locale/timezone HTTP examples and exception type/HTTP response and debug HTML/JSON address boundaries and local rule-based advisor visibility/context checks with network connections blocked without catalogs or a database; includes exact middleware HTTP examples, extraction/absence, context reset and log record boundaries; includes exact model metadata example and introspection shapes; includes inspector declaration/trace examples and offline synthetic ANALYZE negative control; not full CRUD, arbitrary snippet execution, or API stability",
                     "contract_sha256": hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
                     "viewset_contract_sha256": hashlib.sha256(VIEWSET_CONTRACT.read_bytes()).hexdigest(),
                     "localization_contract_sha256": hashlib.sha256(LOCALIZATION_CONTRACT.read_bytes()).hexdigest(),
                     "localization_http_and_conversion_checks": "passed",
                     "exception_contract_sha256": hashlib.sha256(EXCEPTION_CONTRACT.read_bytes()).hexdigest(),
                     "exception_types_and_http_checks": "passed",
                     "ai_debug_contract_sha256": hashlib.sha256(AI_DEBUG_CONTRACT.read_bytes()).hexdigest(),
                     "ai_debug_local_advisor_checks": "passed",
                     "viewset_route_and_default_checks": "passed",
                     "middleware_contract_sha256": hashlib.sha256(MIDDLEWARE_CONTRACT.read_bytes()).hexdigest(),
                     "middleware_http_and_log_checks": "passed",
                     "model_meta_contract_sha256": hashlib.sha256(MODEL_META_CONTRACT.read_bytes()).hexdigest(),
                     "model_meta_checks": "passed",
                     "inspector_contract_sha256": hashlib.sha256(INSPECTOR_CONTRACT.read_bytes()).hexdigest(),
                     "inspector_offline_checks": "passed",
                     "runtime_synthetic_analyze_warning_present": False,
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {evidence['python_blocks']} Python fences; all documented Aksara imports resolve")


if __name__ == "__main__":
    main()
