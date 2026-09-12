"""Verify exact domain-template setup evidence without hiding the known migration failure."""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_domain_template_evidence_is_current():
    path = ROOT / 'audit-evidence/v071/domain-template-execution.json'
    evidence = json.loads(path.read_text())
    assert evidence['pass'] and evidence['disposable_schemas_removed']
    assert evidence['source_checkout_framework_imports'] is False
    assert evidence['all_template_schemas_complete'] is False
    for name, digest in evidence['page_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    assert evidence['runner_sha256'] == hashlib.sha256(
        (ROOT / 'scripts/check_domain_template_docs.py').read_bytes()
    ).hexdigest()
    entries = {entry['template']: entry for entry in evidence['templates']}
    assert set(entries) == {'blog', 'crm', 'multitenant'}
    for name, entry in entries.items():
        assert entry['flat_layout_without_package_metadata'] and entry['server_stopped']
        assert entry['migration_commands_exit_zero']
        assert entry['documented_curl_commands_executed'] and entry['template_listing_executed']
        assert entry['health_status'] == entry['openapi_status'] == 200
        assert entry['generated_update_method'] == 'PATCH'
        assert entry['template_schema_complete'] is (name != 'multitenant')
        if name != 'multitenant':
            assert entry['unauthenticated_create_status'] == 403
            assert not entry['missing_declared_tables']
    tenant = entries['multitenant']
    assert tenant['missing_declared_tables'] == ['tenant_users']
    assert tenant['model_discovery']['before']['table'] == 'tenant_users'
    assert tenant['model_discovery']['after']['table'] == 'aksara_users'
    assert tenant['model_discovery']['after']['module'] == 'aksara.contrib.auth.models'
    assert not re.search(r'postgres(?:ql)?://[^\s]+:[^\s]+@', path.read_text())
