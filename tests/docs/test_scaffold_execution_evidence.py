"""Keep scaffold startup and equivalence tied to the current template."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_scaffold_execution_evidence_is_current():
    startup = json.loads((ROOT / 'audit-evidence/v071/scaffold-startup.json').read_text())
    comparison = json.loads((ROOT / 'audit-evidence/v071/scaffold-wheel-equivalence.json').read_text())
    source_hash = hashlib.sha256((ROOT / 'aksara/cli/scaffold.py').read_bytes()).hexdigest()
    assert startup['pass'] and startup['disposable_schema_removed']
    assert startup['package']['scaffold_sha256'] == source_hash
    assert comparison['pass'] and comparison['packages'][1]['scaffold_sha256'] == source_hash
    assert comparison['changed_generated_files'] == ['README.md']
    assert comparison['files_compared'] == 18
    assert startup['readme_sha256'] == comparison['development_file_sha256']['README.md']
    assert startup['surfaces']['/mcp/'] == startup['surfaces']['/studio/ui'] == 404
    for evidence, script in ((startup, 'check_scaffold_startup.py'), (comparison, 'check_scaffold_equivalence.py')):
        assert evidence['runner_sha256'] == hashlib.sha256((ROOT / 'scripts' / script).read_bytes()).hexdigest()


def test_development_wheel_tutorial_evidence_is_current():
    evidence = json.loads((ROOT / 'audit-evidence/v071/development-wheel-tutorial.json').read_text())
    assert evidence['pass'] and evidence['source_checkout_imports'] is False
    assert len(evidence['stages']) == 6
    assert evidence['api_tests_passed'] == sum(stage['api_tests_passed'] for stage in evidence['stages'])
    assert evidence['runner_sha256'] == hashlib.sha256((ROOT / 'scripts/run_public_tutorial_gate.py').read_bytes()).hexdigest()
    for stage in evidence['stages']:
        assert stage['guide_sha256'] == hashlib.sha256((ROOT / stage['guide']).read_bytes()).hexdigest()
