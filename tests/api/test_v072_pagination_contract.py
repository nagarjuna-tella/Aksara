"""HTTP and OpenAPI contracts for each built-in pagination backend."""

from __future__ import annotations

import os
from typing import ClassVar
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI

from aksara import Model, fields, include_viewset
from aksara.api import (
    CursorPagination,
    LimitOffsetPagination,
    ModelViewSet,
    OrderingFilter,
    PageNumberPagination,
)
from aksara.permissions import AllowAny
from aksara.registry import ModelRegistry

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set",
)


@pytest.fixture
async def pagination_app():
    from aksara.db import Database

    ModelRegistry.clear()

    class PaginatedItem(Model):
        __tablename__ = "v072_paginated_items"

        name = fields.String()

    class BaseItemViewSet(ModelViewSet):
        model = PaginatedItem
        permission_classes: ClassVar[list[type]] = [AllowAny]
        stream_enabled = False
        filter_backends: ClassVar[list[type]] = [OrderingFilter]
        ordering_fields: ClassVar[list[str]] = ["id"]
        ordering: ClassVar[list[str]] = ["id"]

    class DefaultItemViewSet(BaseItemViewSet):
        prefix = "/v072/default-items"
        default_limit = 2
        max_limit = 4

    class OffsetItemViewSet(BaseItemViewSet):
        prefix = "/v072/offset-items"
        pagination_class = LimitOffsetPagination

    class PageItemViewSet(BaseItemViewSet):
        prefix = "/v072/page-items"
        pagination_class = PageNumberPagination

    class CursorItemViewSet(BaseItemViewSet):
        prefix = "/v072/cursor-items"
        pagination_class = CursorPagination

    app = FastAPI()
    for viewset in (
        DefaultItemViewSet,
        OffsetItemViewSet,
        PageItemViewSet,
        CursorItemViewSet,
    ):
        include_viewset(app, viewset)

    database = Database(os.environ["DATABASE_URL"], min_size=1, max_size=2)
    await database.connect()
    await database.execute('DROP TABLE IF EXISTS "v072_paginated_items" CASCADE')
    await database.execute(PaginatedItem.get_create_table_sql())
    for index in range(1, 6):
        await PaginatedItem.objects.create(id=UUID(int=index), name=f"item-{index}")

    try:
        yield app
    finally:
        await database.execute('DROP TABLE IF EXISTS "v072_paginated_items" CASCADE')
        await database.disconnect()
        ModelRegistry.clear()


def _response_properties(openapi: dict, path: str) -> set[str]:
    response_schema = openapi["paths"][path]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    reference = response_schema["$ref"].rsplit("/", 1)[-1]
    return set(openapi["components"]["schemas"][reference]["properties"])


def _query_parameters(openapi: dict, path: str) -> set[str]:
    return {
        parameter["name"]
        for parameter in openapi["paths"][path]["get"].get("parameters", [])
        if parameter["in"] == "query"
    }


@pytest.mark.asyncio
async def test_limit_offset_default_first_middle_final_empty_and_bounds(pagination_app):
    transport = httpx.ASGITransport(app=pagination_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        default = await client.get("/v072/default-items/")
        assert default.status_code == 200
        assert default.json()["limit"] == 2

        pages = []
        for offset in (0, 2, 4, 6):
            response = await client.get(
                "/v072/offset-items/",
                params={"limit": 2, "offset": offset},
            )
            assert response.status_code == 200
            pages.append(response.json())

        assert [len(page["results"]) for page in pages] == [2, 2, 1, 0]
        assert all(page["count"] == 5 for page in pages)
        assert [page["offset"] for page in pages] == [0, 2, 4, 6]
        assert (await client.get("/v072/offset-items/?limit=0")).status_code == 422
        assert (await client.get("/v072/offset-items/?offset=-1")).status_code == 422


@pytest.mark.asyncio
async def test_page_number_first_middle_final_empty_custom_size_and_bounds(pagination_app):
    transport = httpx.ASGITransport(app=pagination_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        default = await client.get("/v072/page-items/")
        assert default.status_code == 200
        assert default.json() == {
            "count": 5,
            "page": 1,
            "size": 20,
            "total_pages": 1,
            "results": default.json()["results"],
        }

        pages = []
        for page_number in (1, 2, 3, 4):
            response = await client.get(
                "/v072/page-items/",
                params={"page": page_number, "size": 2},
            )
            assert response.status_code == 200
            pages.append(response.json())

        assert [len(page["results"]) for page in pages] == [2, 2, 1, 0]
        assert [page["page"] for page in pages] == [1, 2, 3, 4]
        assert all(page["size"] == 2 and page["total_pages"] == 3 for page in pages)
        assert (await client.get("/v072/page-items/?page=0")).status_code == 422
        assert (await client.get("/v072/page-items/?size=0")).status_code == 422
        assert (await client.get("/v072/page-items/?size=101")).status_code == 422


@pytest.mark.asyncio
async def test_cursor_continuation_first_middle_final_empty_and_bounds(pagination_app):
    transport = httpx.ASGITransport(app=pagination_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = (await client.get("/v072/cursor-items/?page_size=2")).json()
        assert [item["name"] for item in first["results"]] == ["item-1", "item-2"]
        assert first["count"] == 5 and first["next_cursor"]

        middle = (
            await client.get(
                "/v072/cursor-items/",
                params={"page_size": 2, "cursor": first["next_cursor"]},
            )
        ).json()
        assert [item["name"] for item in middle["results"]] == ["item-3", "item-4"]
        assert middle["count"] == 3 and middle["next_cursor"]

        final = (
            await client.get(
                "/v072/cursor-items/",
                params={"page_size": 2, "cursor": middle["next_cursor"]},
            )
        ).json()
        assert [item["name"] for item in final["results"]] == ["item-5"]
        assert final["count"] == 1 and final["next_cursor"] is None

        empty = (
            await client.get(
                "/v072/cursor-items/",
                params={"page_size": 2, "cursor": "eyJpZCI6ICI5OTk5OTk5OS0wMDAwLTAwMDAtMDAwMC0wMDAwMDAwMDAwMDAifQ=="},
            )
        ).json()
        assert empty["count"] == 0 and empty["results"] == []
        assert empty["next_cursor"] is None
        assert (await client.get("/v072/cursor-items/?page_size=0")).status_code == 422
        assert (await client.get("/v072/cursor-items/?page_size=101")).status_code == 422
        assert (await client.get("/v072/cursor-items/?cursor=malformed")).status_code == 200


@pytest.mark.asyncio
async def test_openapi_uses_paginator_specific_metadata_and_parameters(pagination_app):
    openapi = pagination_app.openapi()

    assert _response_properties(openapi, "/v072/default-items/") == {
        "count", "limit", "offset", "results",
    }
    assert _response_properties(openapi, "/v072/offset-items/") == {
        "count", "limit", "offset", "results",
    }
    assert _response_properties(openapi, "/v072/page-items/") == {
        "count", "page", "size", "total_pages", "results",
    }
    assert _response_properties(openapi, "/v072/cursor-items/") == {
        "count", "next_cursor", "results",
    }
    assert _query_parameters(openapi, "/v072/default-items/") >= {"limit", "offset"}
    assert _query_parameters(openapi, "/v072/offset-items/") >= {"limit", "offset"}
    assert _query_parameters(openapi, "/v072/page-items/") >= {"page", "size"}
    assert _query_parameters(openapi, "/v072/cursor-items/") >= {"cursor", "page_size"}
