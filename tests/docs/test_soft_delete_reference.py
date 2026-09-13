"""Exercise exact guide query builders and preserve the documented negative control."""

import re
from pathlib import Path

from aksara.contrib.soft_delete import only_deleted, with_deleted
from aksara.registry import ModelRegistry


def test_soft_delete_guide_query_boundaries():
    source = (Path(__file__).resolve().parents[2] / 'docs/docs/orm/soft-deletes.md').read_text()
    snippets = dict(re.findall(r'```python title="([^"]+)"\n(.*?)```', source, re.DOTALL))
    saved = ModelRegistry.snapshot()
    namespace = {}
    try:
        for title, code in snippets.items():
            exec(compile(code, title, 'exec'), namespace)  # noqa: S102 - trusted documentation
        model = namespace['ArchivedDocument']
        assert 'deleted_at' in model._fields
        for name in ('active', 'including_deleted', 'deleted_only'):
            sql, values = namespace[name]._build_where_clause()
            assert 'Draft' in values
            assert 'title' in sql
            if name == 'active':
                assert 'IS NULL' in sql
            elif name == 'deleted_only':
                assert 'IS NOT NULL' in sql
            else:
                assert 'deleted_at' not in sql
        # SOFTDELETE001: visibility transforms preserve existing restrictions.
        for helper in (with_deleted, only_deleted):
            sql, values = helper(model.objects.filter(title='Draft'))._build_where_clause()
            assert 'Draft' in values
            assert 'title' in sql
    finally:
        ModelRegistry.clear()
        for model in saved.values():
            ModelRegistry.register(model)


def test_v071_soft_delete_evidence_remains_historical():
    import hashlib
    import json

    root = Path(__file__).resolve().parents[2]
    data = json.loads((root / 'audit-evidence/v071/soft-delete-execution.json').read_text())
    assert data['pass'] and data['disposable_schema_removed']
    assert data['source_checkout_framework_imports'] is False
    assert data['runtime_queryset_helper_preserves_filters'] is False
    assert len(data['checks']) == 10
    assert set(data['page_sha256']) == {'docs/docs/orm/soft-deletes.md'}
    assert all(len(digest) == 64 for digest in data['page_sha256'].values())
    assert data['runner_sha256'] == hashlib.sha256(
        (root / 'scripts/check_public_soft_delete.py').read_bytes()
    ).hexdigest()
