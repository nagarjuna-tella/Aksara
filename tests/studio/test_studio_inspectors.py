"""
Tests for Studio Inspector endpoints and builder functions.

v0.5.21: Tests for POST /studio/db/plan, GET /studio/models/inspect/{name},
         GET /studio/models/inspect/all, and the builder functions.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from aksara.studio.fastapi import router
from aksara.studio.models import (
    StudioQueryPlanRequest,
    StudioQueryPlanResult,
    StudioModelInspectorField,
    StudioModelInspectorRelationship,
    StudioModelInspectorConstraint,
    StudioModelInspectorSummary,
    StudioModelInspectorAll,
)
from aksara.studio.utils import (
    build_query_plan,
    build_model_inspector,
    build_all_models_inspector,
    _convert_inspector_to_studio,
)
from aksara.inspectors.models import (
    ModelInspectorField,
    ModelInspectorRelationship,
    ModelInspectorConstraint,
    ModelInspectorSummary,
)


# =============================================================================
# Test Setup
# =============================================================================


def create_test_app() -> FastAPI:
    """Create a test FastAPI app with Studio router."""
    app = FastAPI(title="Test App", version="1.0.0")
    app.include_router(router)
    app._db = None
    app.state.db = None
    app.state.viewset_registry = []
    app.ai_registry = None
    return app


def create_mock_settings():
    """Create mock settings for testing."""
    mock = MagicMock()
    mock.debug = True
    mock.log_level = "DEBUG"
    mock.pool_min_size = 5
    mock.pool_max_size = 20
    mock.migrations_dir = "migrations"
    mock.ai_enabled = True
    mock.mcp_enabled = False
    mock.apps = ["app"]
    mock.app_title = "Test App"
    mock.app_version = "1.0.0"
    mock.enable_studio = True
    mock.studio_expose_in_production = False
    mock.studio_allowed_origins = []
    mock.env = "development"
    mock.installed_apps = ["app"]
    mock.db_trace_enabled = True
    mock.db_trace_slow_threshold_ms = 100.0
    mock.db_trace_max_queries = 500
    return mock


# =============================================================================
# Studio Pydantic model tests
# =============================================================================


class TestStudioQueryPlanRequest:
    """Tests for StudioQueryPlanRequest model."""

    def test_create_minimal(self):
        r = StudioQueryPlanRequest(sql="SELECT 1")
        assert r.sql == "SELECT 1"
        assert r.analyze is False

    def test_create_with_analyze(self):
        r = StudioQueryPlanRequest(sql="SELECT * FROM users", analyze=True)
        assert r.analyze is True

    def test_roundtrip(self):
        r = StudioQueryPlanRequest(sql="SELECT 1")
        data = r.model_dump()
        r2 = StudioQueryPlanRequest(**data)
        assert r2.sql == "SELECT 1"


class TestStudioQueryPlanResult:
    """Tests for StudioQueryPlanResult model."""

    def test_create_minimal(self):
        r = StudioQueryPlanResult(sql="SELECT 1")
        assert r.plan == []
        assert r.estimated_cost is None

    def test_create_full(self):
        r = StudioQueryPlanResult(
            sql="SELECT 1",
            plan=["Seq Scan  (cost=0.00..35.50)"],
            estimated_cost=35.50,
            plan_type="EXPLAIN",
            warnings=["Synthetic plan"],
        )
        assert len(r.plan) == 1
        assert r.estimated_cost == 35.50


class TestStudioModelInspectorField:
    """Tests for StudioModelInspectorField model."""

    def test_create_minimal(self):
        f = StudioModelInspectorField(name="id", column_name="id", field_type="AutoField")
        assert f.name == "id"
        assert f.python_type == "Any"

    def test_create_full(self):
        f = StudioModelInspectorField(
            name="email",
            column_name="email",
            field_type="CharField",
            python_type="str",
            unique=True,
            max_length=255,
        )
        assert f.unique is True
        assert f.max_length == 255

    def test_roundtrip(self):
        f = StudioModelInspectorField(name="x", column_name="x", field_type="IntegerField")
        data = f.model_dump()
        f2 = StudioModelInspectorField(**data)
        assert f2.name == "x"


class TestStudioModelInspectorRelationship:
    """Tests for StudioModelInspectorRelationship model."""

    def test_fk(self):
        r = StudioModelInspectorRelationship(
            field_name="author", kind="fk", target_model="User",
        )
        assert r.kind == "fk"

    def test_m2m(self):
        r = StudioModelInspectorRelationship(
            field_name="tags", kind="m2m", target_model="Tag",
            through_table="post_tags",
        )
        assert r.through_table == "post_tags"


class TestStudioModelInspectorConstraint:
    """Tests for StudioModelInspectorConstraint model."""

    def test_pk(self):
        c = StudioModelInspectorConstraint(kind="primary_key", columns=["id"])
        assert c.kind == "primary_key"

    def test_unique(self):
        c = StudioModelInspectorConstraint(kind="unique", columns=["email"])
        assert c.columns == ["email"]


class TestStudioModelInspectorSummary:
    """Tests for StudioModelInspectorSummary model."""

    def test_create_minimal(self):
        s = StudioModelInspectorSummary(name="User", table_name="users")
        assert s.name == "User"
        assert s.num_fields == 0

    def test_create_full(self):
        s = StudioModelInspectorSummary(
            name="User",
            table_name="users",
            num_fields=3,
            num_relationships=1,
            has_timestamps=True,
            pk_field="id",
            fields=[
                StudioModelInspectorField(name="id", column_name="id", field_type="AutoField"),
            ],
        )
        assert len(s.fields) == 1


class TestStudioModelInspectorAll:
    """Tests for StudioModelInspectorAll model."""

    def test_empty(self):
        a = StudioModelInspectorAll(models=[], total_count=0)
        assert a.total_count == 0
        assert a.total_fields == 0

    def test_with_models(self):
        m = StudioModelInspectorSummary(name="X", table_name="x", num_fields=3)
        a = StudioModelInspectorAll(models=[m], total_count=1, total_fields=3)
        assert a.total_count == 1
        assert a.total_fields == 3


# =============================================================================
# Builder function tests
# =============================================================================


class TestBuildQueryPlan:
    """Tests for build_query_plan utility."""

    def test_select_plan(self):
        result = build_query_plan("SELECT 1")
        assert isinstance(result, StudioQueryPlanResult)
        assert result.sql == "SELECT 1"
        assert len(result.plan) > 0
        assert result.estimated_cost is not None

    def test_insert_plan(self):
        result = build_query_plan("INSERT INTO users (name) VALUES ('x')")
        assert result.estimated_cost is not None
        assert any("Insert" in line for line in result.plan)

    def test_update_plan(self):
        result = build_query_plan("UPDATE users SET name='x' WHERE id=1")
        assert any("Update" in line for line in result.plan)

    def test_delete_plan(self):
        result = build_query_plan("DELETE FROM users WHERE id=1")
        assert any("Delete" in line for line in result.plan)

    def test_utility_statement(self):
        result = build_query_plan("CREATE TABLE foo (id int)")
        assert any("Utility" in line for line in result.plan)

    def test_analyze_flag(self):
        result = build_query_plan("SELECT 1", analyze=True)
        assert result.plan_type == "EXPLAIN ANALYZE"

    def test_synthetic_warning(self):
        result = build_query_plan("SELECT 1")
        assert any("ynthetic" in w for w in result.warnings)


class TestBuildModelInspector:
    """Tests for build_model_inspector utility."""

    @patch("aksara.registry.ModelRegistry")
    def test_not_found(self, mock_registry):
        mock_registry.get.side_effect = KeyError("NotFound")
        result = build_model_inspector("NotFound")
        assert result is None

    @patch("aksara.registry.ModelRegistry")
    @patch("aksara.inspectors.models.inspect_model")
    def test_found(self, mock_inspect, mock_registry):
        mock_model = MagicMock()
        mock_registry.get.return_value = mock_model
        mock_inspect.return_value = ModelInspectorSummary(
            name="User",
            table_name="users",
            num_fields=2,
            fields=[
                ModelInspectorField(name="id", column_name="id", field_type="AutoField", primary_key=True),
                ModelInspectorField(name="name", column_name="name", field_type="CharField"),
            ],
        )
        result = build_model_inspector("User")
        assert result is not None
        assert isinstance(result, StudioModelInspectorSummary)
        assert result.name == "User"
        assert len(result.fields) == 2


class TestBuildAllModelsInspector:
    """Tests for build_all_models_inspector utility."""

    @patch("aksara.inspectors.models.inspect_all_models")
    def test_empty_registry(self, mock_all):
        mock_all.return_value = []
        result = build_all_models_inspector()
        assert isinstance(result, StudioModelInspectorAll)
        assert result.total_count == 0

    @patch("aksara.inspectors.models.inspect_all_models")
    def test_with_models(self, mock_all):
        mock_all.return_value = [
            ModelInspectorSummary(name="User", table_name="users", num_fields=3, num_relationships=1),
            ModelInspectorSummary(name="Post", table_name="posts", num_fields=5, num_relationships=2),
        ]
        result = build_all_models_inspector()
        assert result.total_count == 2
        assert result.total_fields == 8
        assert result.total_relationships == 3


class TestConvertInspectorToStudio:
    """Tests for _convert_inspector_to_studio utility."""

    def test_basic_conversion(self):
        inspector = ModelInspectorSummary(
            name="Item",
            table_name="items",
            pk_field="id",
            pk_type="AutoField",
            fields=[
                ModelInspectorField(
                    name="id", column_name="id", field_type="AutoField",
                    primary_key=True, python_type="int",
                ),
            ],
            relationships=[
                ModelInspectorRelationship(
                    field_name="category", kind="fk", target_model="Category",
                ),
            ],
            constraints=[
                ModelInspectorConstraint(kind="primary_key", columns=["id"]),
            ],
            comments=["✓ Has PK"],
        )
        result = _convert_inspector_to_studio(inspector)
        assert isinstance(result, StudioModelInspectorSummary)
        assert result.name == "Item"
        assert len(result.fields) == 1
        assert result.fields[0].primary_key is True
        assert len(result.relationships) == 1
        assert result.relationships[0].kind == "fk"
        assert len(result.constraints) == 1

    def test_preserves_all_field_attrs(self):
        inspector = ModelInspectorSummary(
            name="X",
            table_name="x",
            fields=[
                ModelInspectorField(
                    name="email",
                    column_name="email",
                    field_type="CharField",
                    python_type="str",
                    nullable=False,
                    unique=True,
                    has_default=True,
                    default_repr="''",
                    max_length=255,
                    ai_sensitive=True,
                    auto_generated="Unique; ⚠️ Sensitive",
                ),
            ],
        )
        result = _convert_inspector_to_studio(inspector)
        f = result.fields[0]
        assert f.unique is True
        assert f.ai_sensitive is True
        assert f.max_length == 255
        assert f.has_default is True
        assert f.auto_generated == "Unique; ⚠️ Sensitive"


# =============================================================================
# Endpoint tests
# =============================================================================


class TestStudioDbPlanEndpoint:
    """Tests for POST /studio/db/plan endpoint."""

    @patch("aksara.studio.fastapi.verify_studio_origin")
    def test_select_plan(self, mock_verify):
        mock_verify.return_value = None
        app = create_test_app()
        client = TestClient(app)
        response = client.post(
            "/studio/db/plan",
            json={"sql": "SELECT * FROM users", "analyze": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sql"] == "SELECT * FROM users"
        assert len(data["plan"]) > 0
        assert data["estimated_cost"] is not None

    @patch("aksara.studio.fastapi.verify_studio_origin")
    def test_insert_plan(self, mock_verify):
        mock_verify.return_value = None
        app = create_test_app()
        client = TestClient(app)
        response = client.post(
            "/studio/db/plan",
            json={"sql": "INSERT INTO users (name) VALUES ('x')"},
        )
        assert response.status_code == 200
        data = response.json()
        assert any("Insert" in line for line in data["plan"])

    @patch("aksara.studio.fastapi.verify_studio_origin")
    def test_plan_with_analyze(self, mock_verify):
        mock_verify.return_value = None
        app = create_test_app()
        client = TestClient(app)
        response = client.post(
            "/studio/db/plan",
            json={"sql": "SELECT 1", "analyze": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["plan_type"] == "EXPLAIN ANALYZE"

    @patch("aksara.studio.fastapi.verify_studio_origin")
    def test_plan_warnings(self, mock_verify):
        mock_verify.return_value = None
        app = create_test_app()
        client = TestClient(app)
        response = client.post(
            "/studio/db/plan",
            json={"sql": "SELECT 1"},
        )
        data = response.json()
        # Synthetic plan should have warning
        assert any("ynthetic" in w for w in data.get("warnings", []))


class TestStudioModelInspectEndpoint:
    """Tests for GET /studio/models/inspect/{model_name} endpoint."""

    @patch("aksara.studio.fastapi.verify_studio_origin")
    @patch("aksara.studio.fastapi.build_model_inspector")
    def test_model_found(self, mock_build, mock_verify):
        mock_verify.return_value = None
        mock_build.return_value = StudioModelInspectorSummary(
            name="User",
            table_name="users",
            num_fields=2,
        )
        app = create_test_app()
        client = TestClient(app)
        response = client.get("/studio/models/inspect/User")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "User"
        assert data["table_name"] == "users"

    @patch("aksara.studio.fastapi.verify_studio_origin")
    @patch("aksara.studio.fastapi.build_model_inspector")
    def test_model_not_found(self, mock_build, mock_verify):
        mock_verify.return_value = None
        mock_build.return_value = None
        app = create_test_app()
        client = TestClient(app)
        response = client.get("/studio/models/inspect/NotExist")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @patch("aksara.studio.fastapi.verify_studio_origin")
    @patch("aksara.studio.fastapi.build_model_inspector")
    def test_response_has_fields(self, mock_build, mock_verify):
        mock_verify.return_value = None
        mock_build.return_value = StudioModelInspectorSummary(
            name="Post",
            table_name="posts",
            num_fields=1,
            fields=[
                StudioModelInspectorField(name="id", column_name="id", field_type="AutoField"),
            ],
        )
        app = create_test_app()
        client = TestClient(app)
        response = client.get("/studio/models/inspect/Post")
        assert response.status_code == 200
        data = response.json()
        assert len(data["fields"]) == 1
        assert data["fields"][0]["name"] == "id"


class TestStudioModelsInspectAllEndpoint:
    """Tests for GET /studio/models/inspect/all endpoint."""

    @patch("aksara.studio.fastapi.verify_studio_origin")
    @patch("aksara.studio.fastapi.build_all_models_inspector")
    def test_empty(self, mock_build, mock_verify):
        mock_verify.return_value = None
        mock_build.return_value = StudioModelInspectorAll(
            models=[], total_count=0, total_fields=0, total_relationships=0,
        )
        app = create_test_app()
        client = TestClient(app)
        response = client.get("/studio/models/inspect/all")
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 0
        assert data["models"] == []

    @patch("aksara.studio.fastapi.verify_studio_origin")
    @patch("aksara.studio.fastapi.build_all_models_inspector")
    def test_with_models(self, mock_build, mock_verify):
        mock_verify.return_value = None
        mock_build.return_value = StudioModelInspectorAll(
            models=[
                StudioModelInspectorSummary(name="User", table_name="users", num_fields=3),
                StudioModelInspectorSummary(name="Post", table_name="posts", num_fields=5),
            ],
            total_count=2,
            total_fields=8,
            total_relationships=0,
        )
        app = create_test_app()
        client = TestClient(app)
        response = client.get("/studio/models/inspect/all")
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 2
        assert len(data["models"]) == 2
        assert data["total_fields"] == 8

    @patch("aksara.studio.fastapi.verify_studio_origin")
    @patch("aksara.studio.fastapi.build_all_models_inspector")
    def test_aggregate_counts(self, mock_build, mock_verify):
        mock_verify.return_value = None
        mock_build.return_value = StudioModelInspectorAll(
            models=[
                StudioModelInspectorSummary(name="A", table_name="a", num_fields=2, num_relationships=1),
                StudioModelInspectorSummary(name="B", table_name="b", num_fields=4, num_relationships=3),
            ],
            total_count=2,
            total_fields=6,
            total_relationships=4,
        )
        app = create_test_app()
        client = TestClient(app)
        response = client.get("/studio/models/inspect/all")
        data = response.json()
        assert data["total_relationships"] == 4
