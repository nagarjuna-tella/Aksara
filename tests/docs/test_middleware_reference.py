"""Execute middleware guide examples and their authority/formatting boundaries."""

import asyncio
import inspect
import json
import logging
import re
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def example(page, title):
    from aksara.conf import settings
    from aksara.middleware import request_id_var, tenant_id_var, user_id_var

    saved = vars(settings).copy()
    logger = logging.getLogger('aksara.request')
    handlers, level, propagate = logger.handlers[:], logger.level, logger.propagate
    tokens = [(var, var.set(None)) for var in (request_id_var, tenant_id_var, user_id_var)]
    try:
        settings.mcp_enabled = False
        settings.ai_agent_token = None
        settings.installed_apps = []
        source = (ROOT / 'docs/docs/middleware' / page).read_text()
        snippets = dict(re.findall(r'```python title="([^"]+)"\n(.*?)```', source, re.DOTALL))
        namespace = {'__name__': title.removesuffix('.py')}
        exec(compile(snippets[title], title, 'exec'), namespace)  # noqa: S102 - trusted repository example
        yield namespace
    finally:
        for handler in logger.handlers:
            if handler not in handlers:
                handler.close()
        logger.handlers[:] = handlers
        logger.setLevel(level)
        logger.propagate = propagate
        vars(settings).clear()
        vars(settings).update(saved)
        for var, token in reversed(tokens):
            var.reset(token)


async def request(app, path, **kwargs):
    import httpx

    from aksara.middleware import request_id_var, tenant_id_var

    # Same async context before/after the ASGI call: verify real reset, not
    # merely TestClient's isolation from the caller's context.
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url='http://localhost',
    ) as client:
        response = await client.request("GET", path, **kwargs)
    assert request_id_var.get() is None
    assert tenant_id_var.get() is None
    return response


def test_request_id_example():
    from aksara.middleware import RequestIDMiddleware

    assert set(inspect.signature(RequestIDMiddleware).parameters) == {'app', 'header_name'}
    with example('request-id.md', 'request_id_app.py') as ns:
        for value in ('local-demo', 'not a UUID', 'same-id', 'same-id', ''):
            response = asyncio.run(request(ns['app'], '/context', headers={'X-Correlation-ID': value}))
            assert response.status_code == 200
            actual = response.headers['X-Correlation-ID']
            if value:
                assert actual == value
            else:
                UUID(actual)
            assert response.json() == {'state': actual, 'context': actual}
        response = asyncio.run(request(ns['app'], '/context'))
        UUID(response.headers['X-Correlation-ID'])

        @ns['app'].get('/failure')
        async def failure():
            raise RuntimeError('deliberate documentation probe')

        response = asyncio.run(request(ns['app'], '/failure'))
        assert response.status_code == 500
        assert 'X-Correlation-ID' not in response.headers


def test_tenant_extraction_example():
    from aksara.middleware import TenantMiddleware

    assert set(inspect.signature(TenantMiddleware).parameters) == {'app', 'header_name', 'use_subdomain'}
    cases = [
        ({}, 200, None),
        ({'X-Tenant-Id': ' example '}, 200, 'example'),
        ({'Host': 'example.test.local:8000'}, 200, 'example'),
        ({'Host': 'other.test.local', 'X-Tenant-Id': 'example'}, 200, 'example'),
        ({'Host': 'www.test.local'}, 200, None),
        ({'Host': 'API.test.local'}, 200, None),
        ({'Host': 'app.test.local'}, 200, None),
        ({'Host': 'test.local'}, 200, None),
        ({'X-Tenant-Id': ''}, 400, None),
        ({'X-Tenant-Id': '  ', 'Host': 'example.test.local'}, 400, None),
    ]
    with example('tenant.md', 'tenant_context_app.py') as ns:
        for headers, status, value in cases:
            response = asyncio.run(request(ns['app'], '/context', headers=headers))
            assert response.status_code == status
            if status == 200:
                assert response.json() == {'state': value, 'context': value}
            else:
                assert 'must not be empty' in response.json()['detail']


        # Negative integration control: extraction is not a membership check.
        from types import SimpleNamespace

        from starlette.requests import Request

        from aksara.security.context import principal_from_request

        @ns['app'].get('/legacy-principal')
        async def legacy_principal(request: Request):
            request.state.user = SimpleNamespace(id='local-user', is_authenticated=True)
            return {'tenant': principal_from_request(request).tenant_id}

        response = asyncio.run(request(ns['app'], '/legacy-principal', headers={
            'X-Tenant-Id': 'unverified-selection',
        }))
        assert response.status_code == 200
        assert response.json() == {'tenant': 'unverified-selection'}


def test_logging_example():
    from aksara.conf import settings
    from aksara.middleware import LoggingMiddleware

    assert set(inspect.signature(LoggingMiddleware).parameters) == {'app', 'log_body'}
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    with example('logging.md', 'logging_app.py') as ns:
        logger = logging.getLogger('aksara.request')
        logger.handlers[:] = [Capture()]
        logger.propagate = False
        # Exercise the reserved option while keeping the documented stack.
        entry = next(m for m in ns['app'].user_middleware if m.cls is LoggingMiddleware)
        entry.kwargs['log_body'] = True

        @ns['app'].get('/failure')
        async def failure():
            raise RuntimeError('deliberate documentation probe')

        for path, status, level in [('/ping', 200, logging.INFO), ('/missing', 404, logging.WARNING),
                                    ('/failure', 500, logging.ERROR)]:
            response = asyncio.run(request(ns['app'], path + '?secret=synthetic-query-marker', headers={
                'X-Request-ID': 'local-demo', 'X-Tenant-Id': 'example',
                'Authorization': 'synthetic-header-marker',
            }, content=b'synthetic-body-marker'))
            assert response.status_code == status
            record = records[-1]
            data = record.msg
            assert record.levelno == level
            assert set(data) == {'event', 'method', 'path', 'status_code', 'duration_ms',
                                 'request_id', 'tenant_id', 'user_id'}
            assert data['event'] == 'http_request' and data['method'] == 'GET'
            assert data['path'] == path and data['status_code'] == status
            assert data['request_id'] == 'local-demo' and data['tenant_id'] == 'example'
            assert data['user_id'] is None and data['duration_ms'] >= 0
            formatted = ns['RequestJSONFormatter']().format(record)
            assert json.loads(formatted) == data
            assert 'synthetic-' not in formatted

        settings.log_json = False
        asyncio.run(request(ns['app'], '/ping'))
        assert records[-1].getMessage().startswith('HTTP GET /ping -> 200 in ')
        before = len(records)
        settings.log_requests = False
        asyncio.run(request(ns['app'], '/ping'))
        assert len(records) == before


def test_timing_example():
    with example('index.md', 'timing_app.py') as ns:
        response = asyncio.run(request(ns['app'], '/ping'))
        assert response.status_code == 200 and response.json() == {'status': 'ok'}
        assert float(response.headers['X-Response-Time']) >= 0
