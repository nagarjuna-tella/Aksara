"""Tie CLI instructional changes to installed generation equivalence evidence."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_v071_startproject_guidance_evidence_remains_historical():
    data = json.loads((ROOT / 'audit-evidence/v071/startproject-guidance.json').read_text())
    assert data['pass'] and data['cli_guidance_verified']
    apps = data['startapp_comparison']
    assert apps['files_identical'] and apps['help_verified']
    assert apps['baseline'] == apps['development']
    assert len(apps['development']['files']) == 5
    assert data['source_checkout_framework_imports'] is False
    assert {row['template'] for row in data['comparisons']} == {'basic', 'blog', 'crm', 'multitenant'}
    for row in data['comparisons']:
        assert row['changed_files'] == ['README.md']
        assert row['baseline_sha256'].keys() == row['development_sha256'].keys()
        assert row['files_compared'] == len(row['baseline_sha256'])
        for filename, digest in row['baseline_sha256'].items():
            if filename != 'README.md':
                assert row['development_sha256'][filename] == digest
    assert data['source_sha256']
    assert all(len(digest) == 64 for digest in data['source_sha256'].values())
    assert len(data['runner_sha256']) == 64


def test_v071_runtime_scope_evidence_remains_historical():
    data = json.loads((ROOT / 'audit-evidence/v071/runtime-scope.json').read_text())
    assert data['pass'] and data['runtime_logic_changed'] is False
    assert data['dependencies_changed'] is False
    assert set(data['changed_production_files']) == {
        'aksara/_version.py', 'aksara/cli/main.py', 'aksara/cli/scaffold.py',
        'aksara/cli/templates/__init__.py', 'pyproject.toml',
    }
    assert data['source_sha256']
    assert all(len(digest) == 64 for digest in data['source_sha256'].values())
    assert len(data['runner_sha256']) == 64


def test_v071_updated_readme_startup_evidence_remains_historical():
    data = json.loads((ROOT / 'audit-evidence/v071/cli-help-domain-template-execution.json').read_text())
    assert data['pass'] and data['disposable_schemas_removed']
    assert data['all_template_schemas_complete'] is False
    assert len(data['templates']) == 3
    assert all(row['generated_readme_commands_verified'] for row in data['templates'])
    assert data['page_sha256']
    assert all(len(digest) == 64 for digest in data['page_sha256'].values())
    assert len(data['runner_sha256']) == 64
    basic = json.loads((ROOT / 'audit-evidence/v071/cli-help-scaffold-startup.json').read_text())
    assert basic['pass'] and basic['disposable_schema_removed']
    assert len(basic['checks']) == 5
    assert len(basic['runner_sha256']) == 64
