"""Verify the documented Studio router dependencies without DB/session lookup."""

from unittest.mock import patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from aksara.conf import settings
from aksara.studio.fastapi import _check_studio_origin, verify_studio_auth


def test_studio_origin_and_bearer_boundaries():
    app = FastAPI()

    @app.get('/probe', dependencies=[Depends(_check_studio_origin), Depends(verify_studio_auth)])
    async def probe():
        return {'ok': True}

    with patch.object(settings, 'studio_require_auth', True), \
         patch.object(settings, 'studio_auth_token', 'docs-test-token'), \
         patch.object(settings, 'studio_allowed_origins', ['https://allowed.example']), \
         TestClient(app) as client:
        assert client.get('/probe').status_code == 401
        auth = {'Authorization': 'Bearer docs-test-token'}
        assert client.get('/probe', headers=auth).status_code == 200
        assert client.get('/probe', headers={**auth, 'Origin': 'http://testserver'}).status_code == 200
        assert client.get('/probe', headers={**auth, 'Origin': 'https://allowed.example'}).status_code == 200
        assert client.get('/probe', headers={**auth, 'Origin': 'https://denied.example'}).status_code == 403
        assert client.get('/probe', headers={'Authorization': 'bearer docs-test-token'}).status_code == 401
        with patch.object(settings, 'studio_allowed_origins', []):
            assert client.get('/probe', headers={**auth, 'Origin': 'https://denied.example'}).status_code == 200
        with patch.object(settings, 'studio_require_auth', False):
            assert client.get('/probe').status_code == 200
