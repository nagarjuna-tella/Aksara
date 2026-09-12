"""Execute inspector examples and document the synthetic ANALYZE negative control."""

import re
from pathlib import Path
from unittest.mock import patch

from aksara.db import Database
from aksara.inspectors import explain_query
from aksara.registry import ModelRegistry

ROOT = Path(__file__).resolve().parents[2]


def test_inspector_examples():
    saved = ModelRegistry.snapshot()
    try:
        for page in ('models', 'query'):
            source = (ROOT / f'docs/docs/inspectors/{page}.md').read_text()
            code = re.search(r'```python title="[^"]+"\n(.*?)```', source, re.DOTALL)[1]
            namespace = {}
            exec(compile(code, page, 'exec'), namespace)  # noqa: S102
            if page == 'models':
                summary = namespace['summary']
                assert summary.name == 'InspectedDocument'
                assert summary.table_name == 'inspected_documents'
                assert summary.pk_field == 'id'
                assert any(c.kind == 'unique' and c.columns == ['title'] for c in summary.constraints)
            else:
                assert namespace['stats'].total_queries >= 0
    finally:
        ModelRegistry.clear()
        for model in saved.values():
            ModelRegistry.register(model)


def test_synthetic_analyze_lacks_warning():
    with patch.object(Database, 'get_instance', return_value=None):
        normal = explain_query('SELECT definitely_invalid_syntax')
        assert normal.estimated_cost == 35.5
        assert any('Synthetic' in warning for warning in normal.warnings)
        analyzed = explain_query('SELECT definitely_invalid_syntax', analyze=True)
        assert analyzed.plan == normal.plan
        assert analyzed.plan_type == 'EXPLAIN ANALYZE'
        assert analyzed.warnings == []
