from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aksara import Aksara
from aksara.conf import settings


def test_mcp_only_application_owns_sdk_session_lifecycle(monkeypatch) -> None:
    monkeypatch.setattr(settings, "mcp_enabled", True)
    monkeypatch.setattr(settings, "installed_apps", [])
    app = Aksara(
        auto_discover_views=False,
        enable_admin=False,
        docs_url=None,
        redoc_url=None,
    )
    assert app.db is None
    assert app.mcp_runtime is not None
    assert app.mcp_runtime._started is False
    with TestClient(app):
        assert app.mcp_runtime._started is True
        assert app.db is None
    assert app.mcp_runtime._started is False


@pytest.mark.asyncio
async def test_mcp_session_start_failure_resets_partial_state(monkeypatch) -> None:
    monkeypatch.setattr(settings, "mcp_enabled", True)
    monkeypatch.setattr(settings, "installed_apps", [])
    app = Aksara(auto_discover_views=False, enable_admin=False)
    runtime = app.mcp_runtime
    assert runtime is not None

    class FailingContext:
        async def __aenter__(self):
            raise RuntimeError("session manager failed")

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(runtime.server.session_manager, "run", FailingContext)
    with pytest.raises(RuntimeError, match="session manager failed"):
        await runtime.start()
    assert runtime._started is False
    assert runtime._session_context is None
