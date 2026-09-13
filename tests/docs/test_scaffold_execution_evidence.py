"""Keep scaffold startup and equivalence tied to the current template."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_scaffold_execution_evidence_preserves_v071_results():
    startup = json.loads((ROOT / 'audit-evidence/v071/scaffold-startup.json').read_text())
    comparison = json.loads((ROOT / 'audit-evidence/v071/scaffold-wheel-equivalence.json').read_text())
    assert startup['pass'] and startup['disposable_schema_removed']
    assert len(startup['package']['scaffold_sha256']) == 64
    assert comparison['pass'] and len(comparison['packages'][1]['scaffold_sha256']) == 64
    assert comparison['changed_generated_files'] == ['README.md']
    assert comparison['files_compared'] == 18
    assert startup['readme_sha256'] == comparison['packages'][1]['readme_sha256']
    assert startup['surfaces']['/mcp/'] == startup['surfaces']['/studio/ui'] == 404
    assert len(startup['runner_sha256']) == 64
    assert len(comparison['runner_sha256']) == 64


def test_development_wheel_tutorial_evidence_preserves_v071_results():
    evidence = json.loads((ROOT / 'audit-evidence/v071/development-wheel-tutorial.json').read_text())
    assert evidence['pass'] and evidence['source_checkout_imports'] is False
    assert len(evidence['stages']) == 6
    assert evidence['api_tests_passed'] == sum(stage['api_tests_passed'] for stage in evidence['stages'])
    assert len(evidence['runner_sha256']) == 64
    assert all(len(stage['guide_sha256']) == 64 for stage in evidence['stages'])


def test_v072_scaffold_gate_covers_package_and_installed_server_paths():
    runner = (ROOT / 'scripts/run_v072_scaffold_gate.py').read_text()

    assert '"pip",' in runner
    assert '"install",' in runner
    assert '"-e",' in runner
    assert '"wheel",' in runner
    assert 'installed_wheel_health' in runner
    for template in ('basic', 'blog', 'crm', 'multitenant'):
        assert f'("{template}",' in runner
