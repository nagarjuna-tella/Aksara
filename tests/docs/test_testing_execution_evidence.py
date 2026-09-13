"""Preserve v0.7.1 testing evidence and verify current helper boundaries."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_v071_testing_guide_evidence_remains_historical():
    evidence = json.loads((ROOT / 'audit-evidence/v071/testing-execution.json').read_text())
    assert evidence['pass'] and evidence['tests_passed'] == 3
    assert evidence['source_checkout_framework_imports'] is False
    assert all(len(digest) == 64 for digest in evidence['page_sha256'].values())
    assert len(evidence['runner_sha256']) == 64


def test_v071_testing_helper_negative_evidence_remains_historical():
    evidence = json.loads((ROOT / 'audit-evidence/v071/testing-helper-execution.json').read_text())
    assert evidence['pass'] and evidence['disposable_schema_removed']
    assert evidence['source_checkout_framework_imports'] is False
    assert evidence['probe_owned_connections_closed'] is True
    assert evidence['runtime_rollback_isolation_pass'] is False
    assert evidence['runtime_cleanup_disconnect_pass'] is False
    assert set(evidence['checks']) == {
        'normal exit leaves write committed', 'normal exit leaves helper pool usable',
        'exception exit leaves write committed', 'exception exit leaves helper pool usable',
        'cleanup=False disconnects normally',
    }
    assert set(evidence['source_sha256']) == {'aksara/testing.py'}
    assert all(len(digest) == 64 for digest in evidence['source_sha256'].values())
    assert len(evidence['runner_sha256']) == 64


def test_current_testing_guide_states_rollback_and_process_boundaries():
    guide = (ROOT / 'docs/docs/advanced/testing.md').read_text()
    assert 'pins same-task `Database` and ORM work to one transaction' in guide
    assert 'successful, exceptional, or cancelled exits' in guide
    assert 'separate worker processes' in guide
    assert 'cleanup=False' in guide and 'closes the pool' in guide
