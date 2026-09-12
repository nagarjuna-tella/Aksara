"""Check the published exception families and exact no-database HTTP example."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / 'docs/docs/reference/exceptions.md'


def test_exception_reference_types():
    import asyncpg

    from aksara import Model, exceptions
    from aksara.manager import DoesNotExist, MultipleObjectsReturned

    hierarchy = {
        'AksaraError': Exception,
        'ConfigurationError': exceptions.AksaraError,
        'ImproperlyConfigured': exceptions.ConfigurationError,
        'DatabaseError': exceptions.AksaraError,
        'ConnectionError': exceptions.DatabaseError,
        'UniqueConstraintError': exceptions.DatabaseError,
        'ForeignKeyConstraintError': exceptions.DatabaseError,
        'NotNullConstraintError': exceptions.DatabaseError,
        'CheckConstraintError': exceptions.DatabaseError,
        'QueryError': exceptions.DatabaseError,
        'ValidationError': exceptions.AksaraError,
        'RestrictedError': exceptions.AksaraError,
    }
    for name, base in hierarchy.items():
        assert getattr(exceptions, name).__bases__ == (base,)
        assert f'| `{name}` |' in PAGE.read_text()
    assert not issubclass(DoesNotExist, exceptions.AksaraError)
    assert not issubclass(MultipleObjectsReturned, exceptions.AksaraError)
    assert not hasattr(Model, 'DoesNotExist')
    error = exceptions.ValidationError('Invalid ticket', errors={'subject': 'Required'})
    assert error.errors == {'subject': 'Required'}
    assert not hasattr(error, 'detail') and not hasattr(error, 'status_code')
    # Mapping check only: no SQL is executed or database failure synthesized.
    original = asyncpg.CheckViolationError('check constraint violation')
    mapped = exceptions.map_database_error(original)
    assert type(mapped) is exceptions.DatabaseError
    assert mapped.original_exception is original


def test_exception_http_example():
    from starlette.testclient import TestClient

    from aksara.exceptions import RestrictedError
    from aksara.manager import MultipleObjectsReturned

    source = re.search(r'```python title="error_examples.py"\n(.*?)```', PAGE.read_text(), re.DOTALL)[1]
    namespace = {'__name__': 'error_examples'}
    exec(compile(source, 'error_examples.py', 'exec'), namespace)  # noqa: S102 - trusted repository example
    app = namespace['app']

    @app.get('/test-multiple')
    async def multiple():
        raise MultipleObjectsReturned('Multiple tickets')

    @app.get('/test-restricted')
    async def restricted():
        raise RestrictedError('Cannot delete', model_name='Ticket', related_model='Note', related_count=1)

    @app.get('/test-schema')
    async def schema(limit: int):
        return {'limit': limit}

    with TestClient(app) as client:
        expected = {
            '/validation': (422, {'detail': 'Invalid ticket (subject: Required)',
                                  'errors': {'subject': 'Required'}, 'code': 'validation_error'}),
            '/conflict': (409, {'detail': "Unique constraint violated on field 'reference'",
                               'field': 'reference', 'code': 'unique_constraint_violated'}),
            '/missing': (404, {'detail': 'Ticket not found'}),
            '/http': (403, {'error': {'status': 403, 'message': 'Not permitted', 'type': 'http_exception'}}),
            '/custom': (409, {'code': 'ticket_closed', 'detail': 'Ticket is closed'}),
            '/test-multiple': (500, {'detail': 'Multiple tickets'}),
        }
        for path, (status, body) in expected.items():
            response = client.get(path, headers={'Accept': 'application/json'})
            assert response.status_code == status
            assert response.json() == body
        response = client.get('/test-restricted', headers={'Accept': 'application/json'})
        assert response.status_code == 409
        assert response.json()['code'] == 'delete_restricted'
        assert response.json()['related_count'] == 1
        response = client.get('/test-schema?limit=wrong', headers={'Accept': 'application/json'})
        assert response.status_code == 422
        assert response.json()['error']['type'] == 'validation_error'
        assert response.json()['error']['errors'][0]['loc'] == ['query', 'limit']
        response = client.get('/http', headers={'Accept': 'text/html'})
        assert response.status_code == 403
        assert response.headers['content-type'].startswith('text/html')


def test_debug_page_example_boundaries():
    import asyncio

    import httpx

    page = ROOT / 'docs/docs/debugging/error-pages.md'
    source = re.search(r'```python title="debug_example.py"\n(.*?)```', page.read_text(), re.DOTALL)[1]
    namespace = {'__name__': 'debug_example'}
    exec(compile(source, 'debug_example.py', 'exec'), namespace)  # noqa: S102 - trusted repository example

    async def check():
        for debug in (False, True):
            for address in ('127.0.0.1', '203.0.113.10'):
                app = namespace['create_debug_example'](debug=debug)
                transport = httpx.ASGITransport(app=app, client=(address, 12345))
                async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
                    response = await client.get('/probe-error', headers={'Accept': 'application/json'})
                    assert response.status_code == 500
                    error = response.json()['error']
                    assert error['message'] == 'Internal Server Error'
                    if debug and address == '127.0.0.1':
                        assert error['debug_detail'] == 'deliberate diagnostic example'
                    else:
                        assert 'debug_detail' not in error
                    response = await client.get('/probe-error', headers={'Accept': 'text/html'})
                    assert response.status_code == 500
                    assert response.headers['content-type'].startswith('text/html')
                    assert ('deliberate diagnostic example' in response.text) is debug

    asyncio.run(check())
