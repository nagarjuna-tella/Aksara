"""Execute the local search guide without project indexing or external providers."""

import re
from pathlib import Path


def test_local_search_example():
    page = Path(__file__).resolve().parents[2] / 'docs/docs/search/semantic.md'
    code = re.search(r'```python title="local_search.py"\n(.*?)```', page.read_text(), re.DOTALL)[1]
    namespace = {}
    exec(compile(code, 'local_search.py', 'exec'), namespace)  # noqa: S102
    assert namespace['matched_ids'] == ['auth']
    index = namespace['index']
    assert index.size == 2
    assert index.search('authentication', kind='route', kinds=['model']) == []
    assert index.search('authentication', tags=['missing', 'identity'])
    assert index.search('') == []
    doc = index.get('auth')
    assert index.add_many([doc, doc]) == 2
    assert index.size == 2
    assert index.stats()['is_dirty']
    index.search('authentication', mode='semantic')
    assert not index.stats()['is_dirty']
    assert index.remove('auth') and not index.remove('auth')
    index.clear()
    assert index.size == 0
