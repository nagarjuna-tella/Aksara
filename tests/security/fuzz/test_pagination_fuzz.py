from __future__ import annotations

import pytest
from fastapi import HTTPException

from aksara.api.pagination import CursorPagination, LimitOffsetPagination
from aksara.api.viewsets import ModelViewSet
from aksara.manager import QuerySet

from .conftest import FakeRequest, FuzzAccount, TrackingQuerySet, encoded_cursor


pytestmark = [pytest.mark.security, pytest.mark.fuzz]


class FuzzPaginationViewSet(ModelViewSet):
    model = FuzzAccount
    prefix = "/security-fuzz-pagination"
    max_limit = 25


@pytest.mark.asyncio
async def test_pagination_fuzz_rejects_negative_limit():
    paginator = LimitOffsetPagination()
    request = FakeRequest(query_params={"limit": "-1", "offset": "-10"})

    await paginator.paginate_queryset(TrackingQuerySet(), request)

    assert paginator.limit == paginator.default_limit
    assert paginator.offset == 0
    with pytest.raises(ValueError):
        QuerySet(FuzzAccount).limit(-1)


@pytest.mark.asyncio
async def test_pagination_fuzz_caps_huge_limit():
    paginator = LimitOffsetPagination()
    request = FakeRequest(query_params={"limit": "999999999", "offset": "0"})

    await paginator.paginate_queryset(TrackingQuerySet(), request)

    assert paginator.limit == paginator.max_limit


@pytest.mark.asyncio
async def test_pagination_fuzz_rejects_malformed_cursor():
    paginator = CursorPagination()
    request = FakeRequest(query_params={"cursor": "not-valid-base64!!!"})

    result = await paginator.paginate_queryset(TrackingQuerySet(), request)

    assert paginator.cursor is None
    assert result.filters == {}


@pytest.mark.asyncio
async def test_pagination_fuzz_does_not_extract_tenant_from_cursor():
    paginator = CursorPagination()
    cursor = encoded_cursor({"id": "123", "tenant_id": "tenant-b"})
    request = FakeRequest(query_params={"cursor": cursor})

    result = await paginator.paginate_queryset(TrackingQuerySet(), request)

    assert result.filters == {"id__gt": "123"}
    assert "tenant_id" not in result.filters


@pytest.mark.asyncio
async def test_pagination_fuzz_large_cursor_fails_safely():
    paginator = CursorPagination()
    request = FakeRequest(query_params={"cursor": "x" * 100_000})

    result = await paginator.paginate_queryset(TrackingQuerySet(), request)

    assert paginator.cursor is None
    assert result.filters == {}


@pytest.mark.asyncio
async def test_pagination_fuzz_viewset_negative_offset_fails_safely():
    view = FuzzPaginationViewSet()

    with pytest.raises(HTTPException) as exc_info:
        await view._paginate(TrackingQuerySet(), limit=1, offset=-1)

    assert exc_info.value.status_code == 400
