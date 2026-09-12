"""Execute the guide's action fragment; authorization is covered by Admin view tests."""

import asyncio
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aksara.contrib.admin import AdminSite, ModelAdmin


def test_documented_admin_action():
    page = Path(__file__).resolve().parents[2] / 'docs/docs/admin/actions.md'
    code = re.search(r'```python title="post_actions.py"\n(.*?)```', page.read_text(), re.DOTALL)[1]
    namespace = {}
    exec(compile(code, 'post_actions.py', 'exec'), namespace)  # noqa: S102
    admin = namespace['PostAdmin'](SimpleNamespace(__name__='Post'), AdminSite(name='docs'))
    request = SimpleNamespace(state=SimpleNamespace())
    spec = admin.get_actions(request)['publish_selected']
    assert spec['allowed_permissions'] == ['change']
    queryset = SimpleNamespace(update=AsyncMock(return_value=2))
    asyncio.run(spec['func'](request, queryset))
    queryset.update.assert_awaited_once_with(is_published=True)
    assert request.state._admin_messages == [{'level': 'success', 'text': 'Published 2 posts.'}]
    assert ModelAdmin.actions == []
