"""Keep executed query-profiling guidance tied to its exact installed-wheel evidence."""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_query_profiling_evidence_is_current():
    path = ROOT / 'audit-evidence/v071/query-profiling-execution.json'
    evidence = json.loads(path.read_text())
    assert evidence['pass'] and evidence['standalone_documented_script_pass']
    assert evidence['read_only_database'] and not evidence['database_objects_created']
    assert evidence['source_checkout_framework_imports'] is False
    for name, digest in evidence['page_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    assert evidence['runner_sha256'] == hashlib.sha256(
        (ROOT / 'scripts/check_public_query_profiling.py').read_bytes()
    ).hexdigest()
    assert {
        'exact two-query example executes',
        'capture records parameters without timing',
        'tracing records timing and unredacted parameters',
        'capture works while trace disabled',
        'session snapshots count cap and slow threshold',
        'direct driver calls bypass both collectors',
        'failed database call recorded',
        'nested capture excludes inner calls from outer',
        'capture includes calls from another task',
        'exact middleware example correlates request',
        'reused client request ID replaces stored batch',
        'explicit PostgreSQL plan query executes',
    } <= set(evidence['checks'])
    assert not re.search(r'postgres(?:ql)?://[^\s]+:[^\s]+@', path.read_text())
