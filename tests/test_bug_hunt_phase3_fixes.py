"""
Regression tests for Phase 3 bug-hunt findings on the API layer.

Each test exercises one of the four confirmed bugs from
`bug-hunt/phase-3-findings.md`. We avoid live HTTP/DB to keep the suite
fast; instead, we inspect the generated FastAPI app's OpenAPI document,
the model_to_dict serializer, the CursorPagination contract, and the
serializer's type map.
"""

from __future__ import annotations

import base64
import json
import uuid
from typing import List, get_origin, get_args
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import APIRouter, FastAPI
from typing import Any

from aksara import Model, fields
from aksara.api.pagination import CursorPagination
from aksara.api.router import include_viewset
from aksara.api.schemas import generate_read_schema, model_to_dict
from aksara.api.serializers import ModelSerializer, _get_python_type
from aksara.api.viewsets import ModelViewSet
from aksara.registry import ModelRegistry


@pytest.fixture(autouse=True)
def _clear_registry():
    ModelRegistry._models.clear()
    yield
    ModelRegistry._models.clear()


# ─── Fix #1 — ViewSet routes publish concrete response models ──────────────


class TestViewSetResponseModels:
    def test_openapi_describes_concrete_read_schema(self):
        class Widget(Model):
            name = fields.String(max_length=50)

        class WidgetViewSet(ModelViewSet):
            model = Widget
            prefix = "/widgets"

        router = APIRouter()
        include_viewset(router, WidgetViewSet)

        app = FastAPI()
        app.include_router(router)
        spec = app.openapi()

        retrieve_op = spec["paths"]["/widgets/{pk}"]["get"]
        retrieve_schema = retrieve_op["responses"]["200"]["content"]["application/json"]["schema"]
        # The pre-fix schema was {'type': 'object', 'additionalProperties': True}
        # The fix must reference the concrete WidgetRead model.
        ref = retrieve_schema.get("$ref", "")
        assert "WidgetRead" in ref

        list_op = spec["paths"]["/widgets/"]["get"]
        list_schema = list_op["responses"]["200"]["content"]["application/json"]["schema"]
        list_ref = list_schema.get("$ref", "")
        # The list endpoint returns a paginated wrapper, but it must still
        # reference a concrete model (not a generic object).
        assert "Paginated" in list_ref and "WidgetRead" in list_ref


# ─── Fix #2 — model_to_dict serializes M2M fields ──────────────────────────


class TestModelToDictManyToMany:
    def test_m2m_fields_are_included_in_serialized_output(self):
        class Tag(Model):
            label = fields.String(max_length=30)

        class Post(Model):
            title = fields.String(max_length=50)
            tags = fields.ManyToMany(Tag)

        read_schema = generate_read_schema(Post)
        read_schema_fields = set(read_schema.model_fields.keys())

        dumped = model_to_dict(Post(title="x"))
        # Before the fix `tags` was declared in the schema but missing
        # from the dict. After the fix the key must be present so the
        # documented contract and the serialized payload agree.
        assert "tags" in read_schema_fields
        assert "tags" in dumped

    def test_m2m_cached_ids_are_emitted(self):
        class Tag(Model):
            label = fields.String(max_length=30)

        class Post(Model):
            title = fields.String(max_length=50)
            tags = fields.ManyToMany(Tag)

        post = Post(title="x")
        tag_id = uuid.uuid4()
        # The serializer stashes cached M2M IDs as `_<field>_ids`; the
        # canonical serializer path must surface them too.
        setattr(post, "_tags_ids", [tag_id])

        dumped = model_to_dict(post)
        assert dumped["tags"] == [tag_id]


# ─── Fix #3 — CursorPagination honours page_size and cursor ────────────────


class TestCursorPaginationRespectsParams:
    @pytest.mark.asyncio
    async def test_page_size_sets_limit_for_fetch(self):
        paginator = CursorPagination()
        request = Mock()
        request.query_params = {"page_size": "5"}

        mock_qs = Mock()
        mock_qs.count = AsyncMock(return_value=42)
        mock_qs.filter = Mock(return_value=mock_qs)

        await paginator.paginate_queryset(mock_qs, request)

        # ModelViewSet._paginate reads `paginator.limit` and forwards it
        # to _fetch_with_pagination. Pre-fix, this attribute did not
        # exist and the fetch fell back to the viewset's default limit.
        assert paginator.limit == 5
        assert paginator.offset == 0

    @pytest.mark.asyncio
    async def test_cursor_is_applied_as_filter_on_queryset(self):
        paginator = CursorPagination()
        request = Mock()
        cursor_id = str(uuid.uuid4())
        cursor_b64 = base64.b64encode(
            json.dumps({"id": cursor_id}).encode("utf-8")
        ).decode("utf-8")
        request.query_params = {"page_size": "5", "cursor": cursor_b64}

        filtered_qs = Mock()
        filtered_qs.count = AsyncMock(return_value=10)
        filtered_qs.filter = Mock(return_value=filtered_qs)

        mock_qs = Mock()
        mock_qs.count = AsyncMock(return_value=42)
        mock_qs.filter = Mock(return_value=filtered_qs)

        result_qs = await paginator.paginate_queryset(mock_qs, request)

        # The cursor must be decoded and translated into a real queryset
        # filter so the next page advances past the previous page.
        mock_qs.filter.assert_called_once()
        kwargs = mock_qs.filter.call_args.kwargs
        assert "id__gt" in kwargs
        assert kwargs["id__gt"] == cursor_id
        # The returned queryset must be the filtered one (so the fetch
        # later runs against the narrowed set, not the original).
        assert result_qs is filtered_qs

    def test_next_cursor_round_trips_through_json(self):
        paginator = CursorPagination()
        paginator.count = 100
        paginator.page_size = 2
        new_id = uuid.uuid4()
        data = [{"id": uuid.uuid4()}, {"id": new_id}]

        response = paginator.get_paginated_response(data)

        assert "next_cursor" in response
        decoded = json.loads(
            base64.b64decode(response["next_cursor"]).decode("utf-8")
        )
        # Encoding must be JSON-decodable so paginate_queryset can read
        # it back; the previous str(dict) encoding was not parseable.
        assert decoded == {"id": str(new_id)}


# ─── Fix #4 — serializer types Slug/Float/etc. concretely ─────────────────


class TestSerializerPythonTypeMapping:
    def test_slug_maps_to_str(self):
        assert _get_python_type(fields.Slug(max_length=50)) is str

    def test_float_maps_to_float(self):
        assert _get_python_type(fields.Float()) is float

    def test_filepath_maps_to_str(self):
        assert _get_python_type(fields.FilePath(max_length=200)) is str

    def test_ipaddress_maps_to_str(self):
        assert _get_python_type(fields.IPAddress()) is str

    def test_serializer_input_model_uses_concrete_types(self):
        class Item(Model):
            slug = fields.Slug(max_length=50)
            rating = fields.Float()

        class ItemSerializer(ModelSerializer):
            class Meta:
                model = Item
                fields = "__all__"

        serializer = ItemSerializer(data={})
        input_model = serializer.get_input_model()
        output_model = serializer.get_output_model()

        def _annotation_includes(model, name, target):
            ann = model.model_fields[name].annotation
            # The field is Optional[type]; unwrap the Union to verify
            # the underlying concrete type isn't Any.
            args = get_args(ann) or (ann,)
            return target in args or any(
                target is a for a in args
            )

        assert _annotation_includes(input_model, "slug", str)
        assert _annotation_includes(input_model, "rating", float)
        assert _annotation_includes(output_model, "slug", str)
        assert _annotation_includes(output_model, "rating", float)
        # Make sure none of them silently fall through to Any anymore.
        for model in (input_model, output_model):
            for fname in ("slug", "rating"):
                ann = model.model_fields[fname].annotation
                args = get_args(ann) or (ann,)
                assert Any not in args, f"{fname} should not be typed as Any"
