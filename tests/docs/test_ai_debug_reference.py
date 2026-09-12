"""Execute the local advisor example and verify the documented context limits."""

import asyncio
import re
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / 'docs/docs/debugging/ai-debug.md'


def test_ai_debug_example_and_context():
    import httpx
    from starlette.requests import Request

    from aksara.ai.debug import (
        RuleBasedAiDebugAdvisor,
        build_ai_debug_context,
        default_advisor,
    )
    from aksara.conf import settings

    original = vars(settings).copy()
    source = re.search(r'```python title="ai_debug_example.py"\n(.*?)```', PAGE.read_text(), re.DOTALL)[1]
    namespace = {'__name__': 'ai_debug_example'}
    exec(compile(source, 'ai_debug_example.py', 'exec'), namespace)  # noqa: S102 - trusted repository example

    async def check():
        assert isinstance(default_advisor, RuleBasedAiDebugAdvisor)
        for show_advisor, global_debug in ((True, True), (False, True), (True, False)):
            app = namespace['create_debug_ai_example'](show_advisor=show_advisor)
            settings.debug = global_debug
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://example.test') as client:
                response = await client.get('/diagnostic-example', headers={'Accept': 'text/html'})
                assert response.status_code == 500
                assert 'deliberate diagnostic example' in response.text
                assert ('data-tab="ai-debug"' in response.text) is (show_advisor and global_debug)
                response = await client.get('/diagnostic-example', headers={'Accept': 'application/json'})
                assert response.status_code == 500
                assert 'AI Debug' not in response.text
        request = Request({'type': 'http', 'method': 'POST', 'scheme': 'http',
                           'path': '/context', 'query_string': b'note=docs-private-query',
                           'headers': [(b'authorization', b'docs-private-token')],
                           'server': ('example.test', 80)})
        request._body = b'docs-private-body'
        try:
            raise ValueError('docs-private-exception')
        except ValueError as error:
            context = await build_ai_debug_context(request, error, 500)
        assert context.request.headers['authorization'] == '***'
        assert context.request.query_params['note'] == 'docs-private-query'
        assert context.request.body_preview == 'docs-private-body'
        assert context.exception.message == 'docs-private-exception'
        assert context.traceback_frames
        assert all(frame.locals_preview is None for frame in context.traceback_frames)

    try:
        with (
            patch('socket.socket.connect', side_effect=AssertionError('Unexpected network connection')),
            patch('socket.create_connection', side_effect=AssertionError('Unexpected network connection')),
        ):
            asyncio.run(check())
    finally:
        vars(settings).clear()
        vars(settings).update(original)
