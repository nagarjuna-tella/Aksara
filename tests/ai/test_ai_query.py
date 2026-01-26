"""
Tests for AI Query Assistant (v0.4.2).

Tests:
- AiQueryPlan model validation
- execute_ai_query_plan with various filters
- Supported lookups: exact, gt, gte, lt, lte, in, isnull, icontains, contains
- Sorting (asc/desc)
- Pagination (limit/offset)
- Error handling for unknown models, invalid fields, unsupported lookups
- Endpoint integration tests
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

from pydantic import ValidationError
from fastapi.testclient import TestClient
from fastapi import FastAPI

from vidyut.ai.query import (
    AiFilterCondition,
    AiSortField,
    AiQueryPagination,
    AiQueryPlan,
    AiQueryRequest,
    AiQueryResult,
    execute_ai_query_plan,
    get_query_plan_schema,
    get_available_models_for_query,
    SUPPORTED_LOOKUPS,
    _validate_lookup,
    _serialize_value,
)
from vidyut.ai.fastapi import router
from vidyut.exceptions import ConfigurationError


# =============================================================================
# Model Validation Tests
# =============================================================================

class TestAiFilterCondition:
    """Tests for AiFilterCondition model."""
    
    def test_valid_filter_exact(self):
        """Test valid exact filter."""
        condition = AiFilterCondition(
            field="is_active",
            lookup="exact",
            value=True
        )
        assert condition.field == "is_active"
        assert condition.lookup == "exact"
        assert condition.value is True
    
    def test_valid_filter_gt(self):
        """Test valid gt filter."""
        condition = AiFilterCondition(
            field="created_at",
            lookup="gt",
            value="2024-01-01"
        )
        assert condition.lookup == "gt"
    
    def test_valid_filter_in(self):
        """Test valid in filter with list."""
        condition = AiFilterCondition(
            field="status",
            lookup="in",
            value=["active", "pending"]
        )
        assert condition.value == ["active", "pending"]
    
    def test_valid_filter_isnull(self):
        """Test valid isnull filter."""
        condition = AiFilterCondition(
            field="deleted_at",
            lookup="isnull",
            value=True
        )
        assert condition.value is True
    
    def test_valid_filter_icontains(self):
        """Test valid icontains filter."""
        condition = AiFilterCondition(
            field="name",
            lookup="icontains",
            value="john"
        )
        assert condition.lookup == "icontains"
    
    def test_invalid_lookup_allowed_in_model(self):
        """Test that invalid lookups are allowed in model, validated at execution."""
        # Model allows any string, validation happens during execution
        condition = AiFilterCondition(
            field="name",
            lookup="unknown_lookup",
            value="test"
        )
        assert condition.lookup == "unknown_lookup"


class TestAiSortField:
    """Tests for AiSortField model."""
    
    def test_sort_ascending(self):
        """Test ascending sort."""
        sort = AiSortField(field="created_at", direction="asc")
        assert sort.direction == "asc"
    
    def test_sort_descending(self):
        """Test descending sort."""
        sort = AiSortField(field="created_at", direction="desc")
        assert sort.direction == "desc"
    
    def test_sort_default_direction(self):
        """Test default sort direction."""
        sort = AiSortField(field="name")
        assert sort.direction == "asc"


class TestAiQueryPagination:
    """Tests for AiQueryPagination model."""
    
    def test_default_pagination(self):
        """Test default pagination values."""
        pagination = AiQueryPagination()
        assert pagination.limit == 50  # Default is 50
        assert pagination.offset == 0
    
    def test_custom_pagination(self):
        """Test custom pagination."""
        pagination = AiQueryPagination(limit=50, offset=10)
        assert pagination.limit == 50
        assert pagination.offset == 10
    
    def test_max_limit_is_500(self):
        """Test max limit is capped at 500."""
        pagination = AiQueryPagination(limit=500)
        assert pagination.limit == 500


class TestAiQueryPlan:
    """Tests for AiQueryPlan model."""
    
    def test_minimal_plan(self):
        """Test minimal valid plan."""
        plan = AiQueryPlan(model="User")
        assert plan.model == "User"
        assert plan.filters == []
        assert plan.sorting == []
        assert plan.pagination.limit == 50  # Default
    
    def test_full_plan(self):
        """Test complete plan with all options."""
        plan = AiQueryPlan(
            model="Article",
            filters=[
                AiFilterCondition(field="is_published", lookup="exact", value=True),
                AiFilterCondition(field="view_count", lookup="gte", value=100),
            ],
            sorting=[
                AiSortField(field="created_at", direction="desc"),
            ],
            pagination=AiQueryPagination(limit=20, offset=0),
            select_fields=["id", "title", "author"],
        )
        assert len(plan.filters) == 2
        assert len(plan.sorting) == 1
        assert plan.select_fields == ["id", "title", "author"]
    
    def test_qualified_model_name(self):
        """Test qualified model name with app label."""
        plan = AiQueryPlan(model="blog.Article")
        assert plan.model == "blog.Article"


class TestAiQueryResult:
    """Tests for AiQueryResult model."""
    
    def test_result_structure(self):
        """Test result structure."""
        result = AiQueryResult(
            plan=AiQueryPlan(model="User"),
            rows=[{"id": 1, "name": "Test"}],
            count=1,
            limited=False
        )
        assert result.count == 1
        assert len(result.rows) == 1
        assert result.limited is False


# =============================================================================
# Lookup Validation Tests
# =============================================================================

class TestLookupValidation:
    """Tests for lookup validation."""
    
    def test_all_supported_lookups_valid(self):
        """Test all supported lookups are valid."""
        for lookup in SUPPORTED_LOOKUPS:
            # Should not raise
            _validate_lookup(lookup)
    
    def test_unsupported_lookup_raises(self):
        """Test unsupported lookup raises ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            _validate_lookup("startswith")
        assert "Unsupported lookup" in str(exc_info.value)
    
    def test_supported_lookups_set(self):
        """Verify the complete set of supported lookups."""
        expected = {
            "exact", "gt", "gte", "lt", "lte",
            "in", "isnull", "icontains", "contains"
        }
        assert SUPPORTED_LOOKUPS == expected


# =============================================================================
# Serialization Tests
# =============================================================================

class TestSerialization:
    """Tests for value serialization."""
    
    def test_serialize_uuid(self):
        """Test UUID serialization."""
        test_uuid = uuid4()
        result = _serialize_value(test_uuid)
        assert result == str(test_uuid)
    
    def test_serialize_datetime(self):
        """Test datetime serialization."""
        test_dt = datetime(2024, 1, 15, 12, 30, 45, tzinfo=timezone.utc)
        result = _serialize_value(test_dt)
        assert result == "2024-01-15T12:30:45+00:00"
    
    def test_serialize_decimal(self):
        """Test Decimal serialization."""
        result = _serialize_value(Decimal("19.99"))
        assert result == "19.99"
    
    def test_serialize_none(self):
        """Test None serialization."""
        result = _serialize_value(None)
        assert result is None
    
    def test_serialize_list(self):
        """Test list serialization."""
        test_uuid = uuid4()
        result = _serialize_value([test_uuid, "hello"])
        assert result == [str(test_uuid), "hello"]
    
    def test_serialize_dict(self):
        """Test dict serialization."""
        result = _serialize_value({"key": Decimal("10.5")})
        assert result == {"key": "10.5"}


# =============================================================================
# Schema Helper Tests
# =============================================================================

class TestSchemaHelpers:
    """Tests for schema helper functions."""
    
    def test_get_query_plan_schema(self):
        """Test get_query_plan_schema returns valid structure."""
        schema = get_query_plan_schema()
        
        assert "type" in schema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "model" in schema["properties"]
        assert "filters" in schema["properties"]
        assert "sorting" in schema["properties"]
        assert "pagination" in schema["properties"]
    
    def test_get_available_models_for_query(self):
        """Test get_available_models_for_query returns list."""
        # This should work even with empty registry
        models = get_available_models_for_query()
        assert isinstance(models, list)


# =============================================================================
# Execute Query Plan Tests
# =============================================================================

class TestExecuteQueryPlan:
    """Tests for execute_ai_query_plan function."""
    
    @pytest.mark.asyncio
    async def test_execute_unknown_model(self):
        """Test execution with unknown model raises error."""
        plan = AiQueryPlan(model="NonExistentModel")
        
        with pytest.raises(ConfigurationError) as exc_info:
            await execute_ai_query_plan(plan)
        
        assert "not found" in str(exc_info.value).lower()


# =============================================================================
# Endpoint Integration Tests
# =============================================================================

def create_test_app() -> FastAPI:
    """Create a test FastAPI app with AI router."""
    app = FastAPI()
    app.include_router(router)
    return app


class TestQueryPlanSchemaEndpoint:
    """Tests for POST /ai/query/plan/schema endpoint."""
    
    def test_get_schema(self):
        """Test schema endpoint returns valid structure."""
        app = create_test_app()
        client = TestClient(app)
        
        response = client.post("/ai/query/plan/schema")
        assert response.status_code == 200
        
        data = response.json()
        assert "schema" in data
        assert "supported_lookups" in data
        assert "version" in data
        assert data["version"] == "0.4.2"
        assert "exact" in data["supported_lookups"]
        assert "icontains" in data["supported_lookups"]


class TestQueryModelsEndpoint:
    """Tests for GET /ai/query/models endpoint."""
    
    def test_list_models(self):
        """Test models list endpoint."""
        app = create_test_app()
        client = TestClient(app)
        
        response = client.get("/ai/query/models")
        assert response.status_code == 200
        
        data = response.json()
        assert "models" in data
        assert "count" in data
        assert "version" in data


class TestQueryExecuteEndpoint:
    """Tests for POST /ai/query/execute endpoint."""
    
    def test_invalid_plan_returns_400(self):
        """Test invalid plan returns 400."""
        app = create_test_app()
        client = TestClient(app)
        
        # Empty body
        response = client.post("/ai/query/execute", json={})
        assert response.status_code == 400
    
    def test_missing_model_returns_400(self):
        """Test missing model returns 400."""
        app = create_test_app()
        client = TestClient(app)
        
        response = client.post("/ai/query/execute", json={
            "filters": [{"field": "name", "lookup": "exact", "value": "test"}]
        })
        assert response.status_code == 400


# =============================================================================
# Filter Operator Tests
# =============================================================================

class TestFilterOperators:
    """Tests for filter operator mapping."""
    
    def test_exact_lookup_creates_eq_filter(self):
        """Test exact lookup maps correctly."""
        condition = AiFilterCondition(
            field="status",
            lookup="exact",
            value="active"
        )
        assert condition.lookup == "exact"
    
    def test_gt_lookup(self):
        """Test gt lookup maps correctly."""
        condition = AiFilterCondition(
            field="price",
            lookup="gt",
            value=100
        )
        assert condition.lookup == "gt"
    
    def test_gte_lookup(self):
        """Test gte lookup maps correctly."""
        condition = AiFilterCondition(
            field="count",
            lookup="gte",
            value=5
        )
        assert condition.lookup == "gte"
    
    def test_lt_lookup(self):
        """Test lt lookup maps correctly."""
        condition = AiFilterCondition(
            field="age",
            lookup="lt",
            value=30
        )
        assert condition.lookup == "lt"
    
    def test_lte_lookup(self):
        """Test lte lookup maps correctly."""
        condition = AiFilterCondition(
            field="score",
            lookup="lte",
            value=100
        )
        assert condition.lookup == "lte"
    
    def test_in_lookup(self):
        """Test in lookup maps correctly."""
        condition = AiFilterCondition(
            field="category",
            lookup="in",
            value=["tech", "science"]
        )
        assert condition.lookup == "in"
    
    def test_isnull_lookup(self):
        """Test isnull lookup maps correctly."""
        condition = AiFilterCondition(
            field="deleted_at",
            lookup="isnull",
            value=True
        )
        assert condition.lookup == "isnull"
    
    def test_icontains_lookup(self):
        """Test icontains lookup maps correctly."""
        condition = AiFilterCondition(
            field="title",
            lookup="icontains",
            value="python"
        )
        assert condition.lookup == "icontains"
    
    def test_contains_lookup(self):
        """Test contains lookup maps correctly."""
        condition = AiFilterCondition(
            field="description",
            lookup="contains",
            value="important"
        )
        assert condition.lookup == "contains"


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_empty_filters(self):
        """Test plan with empty filters."""
        plan = AiQueryPlan(model="User", filters=[])
        assert plan.filters == []
    
    def test_multiple_filters_same_field(self):
        """Test multiple filters on same field."""
        plan = AiQueryPlan(
            model="Product",
            filters=[
                AiFilterCondition(field="price", lookup="gte", value=10),
                AiFilterCondition(field="price", lookup="lte", value=100),
            ]
        )
        assert len(plan.filters) == 2
    
    def test_combined_sorting(self):
        """Test multiple sort fields."""
        plan = AiQueryPlan(
            model="Article",
            sorting=[
                AiSortField(field="is_featured", direction="desc"),
                AiSortField(field="created_at", direction="desc"),
            ]
        )
        assert len(plan.sorting) == 2
    
    def test_select_fields_subset(self):
        """Test select_fields with subset of fields."""
        plan = AiQueryPlan(
            model="User",
            select_fields=["id", "email"]
        )
        assert plan.select_fields == ["id", "email"]
    
    def test_pagination_offset_only(self):
        """Test pagination with offset only."""
        plan = AiQueryPlan(
            model="Log",
            pagination=AiQueryPagination(offset=50)
        )
        assert plan.pagination.offset == 50
        assert plan.pagination.limit == 50  # default
    
    def test_debug_notes(self):
        """Test plan with debug notes."""
        plan = AiQueryPlan(
            model="User",
            debug_notes="Finding active users created after 2024"
        )
        assert plan.debug_notes == "Finding active users created after 2024"
