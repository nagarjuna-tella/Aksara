"""Tie CLI instructional changes to installed generation equivalence evidence."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_startproject_guidance_evidence_is_current():
    data = json.loads((ROOT / 'audit-evidence/v071/startproject-guidance.json').read_text())
    assert data['pass'] and data['cli_guidance_verified']
    assert data['source_checkout_framework_imports'] is False
    assert {row['template'] for row in data['comparisons']} == {'basic', 'blog', 'crm', 'multitenant'}
    for row in data['comparisons']:
        assert row['changed_files'] == ['README.md']
        assert row['baseline_sha256'].keys() == row['development_sha256'].keys()
        assert row['files_compared'] == len(row['baseline_sha256'])
        for filename, digest in row['baseline_sha256'].items():
            if filename != 'README.md':
                assert row['development_sha256'][filename] == digest
    for name, digest in data['source_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    assert data['runner_sha256'] == hashlib.sha256(
        (ROOT / 'scripts/check_startproject_guidance.py').read_bytes()
    ).hexdigest()


def test_runtime_scope_evidence_is_current():
    data = json.loads((ROOT / 'audit-evidence/v071/runtime-scope.json').read_text())
    assert data['pass'] and data['runtime_logic_changed'] is False
    assert data['dependencies_changed'] is False
    assert set(data['changed_production_files']) == {
        'aksara/cli/main.py', 'aksara/cli/scaffold.py', 'aksara/cli/templates/__init__.py',
    }
    for name, digest in data['source_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    assert data['runner_sha256'] == hashlib.sha256(
        (ROOT / 'scripts/check_v071_runtime_scope.py').read_bytes()
    ).hexdigest()


def test_updated_readme_startup_evidence_is_current():
    data = json.loads((ROOT / 'audit-evidence/v071/cli-help-domain-template-execution.json').read_text())
    assert data['pass'] and data['disposable_schemas_removed']
    assert data['all_template_schemas_complete'] is False
    assert len(data['templates']) == 3
    assert all(row['generated_readme_commands_verified'] for row in data['templates'])
    for name, digest in data['page_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    assert data['runner_sha256'] == hashlib.sha256(
        (ROOT / 'scripts/check_domain_template_docs.py').read_bytes()
    ).hexdigest()
    basic = json.loads((ROOT / 'audit-evidence/v071/cli-help-scaffold-startup.json').read_text())
    assert basic['pass'] and basic['disposable_schema_removed']
    assert len(basic['checks']) == 5
    assert basic['runner_sha256'] == hashlib.sha256(
        (ROOT / 'scripts/check_scaffold_startup.py').read_bytes()
    ).hexdigest()
