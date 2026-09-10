"""Included-router discovery must describe the actual HTTP/OpenAPI surface."""

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from aksara.ai.context import _extract_routes_from_app
from aksara.launch_check import _route_paths
from aksara.routing import iter_routes
from aksara.studio.utils import _get_ai_tools_summary, build_routes_info


def test_nested_includes_match_live_paths_and_openapi():
    leaf = APIRouter()

    @leaf.get("/value", name="value")
    async def value():
        return {"value": 42}

    parent = APIRouter()
    parent.include_router(leaf, prefix="/nested", tags=["nested"])
    app = FastAPI()
    app.include_router(parent, prefix="/ai")
    routes = list(iter_routes(app))
    effective = next(r for r in routes if r.path == "/ai/nested/value")
    assert effective.endpoint is value
    assert effective.methods == {"GET"}
    assert "nested" in effective.tags
    with TestClient(app) as client:
        response = client.get(effective.path)
        assert response.status_code == 200
        assert response.json() == {"value": 42}
        assert effective.path in client.get("/openapi.json").json()["paths"]
    assert effective.path in _route_paths(app)
    assert any(r.path == effective.path for r in build_routes_info(app))
    assert any(r.path == effective.path for r in _extract_routes_from_app(app))
    assert any(t.endpoint == effective.path for t in _get_ai_tools_summary(app))


def test_including_same_router_twice_preserves_distinct_effective_paths():
    router = APIRouter()

    @router.post("/items")
    async def create():
        return {"ok": True}

    app = FastAPI()
    app.include_router(router, prefix="/one")
    app.include_router(router, prefix="/two")
    paths = {r.path for r in iter_routes(app) if "POST" in (r.methods or ())}
    assert paths == {"/one/items", "/two/items"}
    with TestClient(app) as client:
        for path in paths:
            assert client.post(path).status_code == 200


def test_route_inventory_accepts_mounts_without_http_methods(tmp_path):
    from starlette.staticfiles import StaticFiles

    from aksara.studio.utils import compute_routes_checksum

    app = FastAPI()
    app.mount("/media", StaticFiles(directory=tmp_path), name="media")
    assert len(compute_routes_checksum(app)) == 16
    assert any(r.path == "/media" for r in build_routes_info(app))
    assert any(r.path == "/media" for r in _extract_routes_from_app(app))
