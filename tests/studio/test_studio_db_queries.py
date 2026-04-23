"""
Tests for Studio DB query endpoints.

v0.5.10: Query Inspector & ORM Profiler

Tests:
- GET /studio/db/queries
- GET /studio/db/queries/{request_id}
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from aksara.studio.fastapi import router, verify_studio_auth as _verify_studio_auth


# =============================================================================
# Test Setup
# =============================================================================

def create_test_app() -> FastAPI:
    """Create a test FastAPI app with Studio router."""
    app = FastAPI(title="Test App", version="1.0.0")
    app.include_router(router)
    app.dependency_overrides[_verify_studio_auth] = lambda: None
    
    # Mock database state
    app._db = None
    app.state.db = None
    app.state.viewset_registry = []
    app.ai_registry = None
    
    return app


def create_mock_settings():
    """Create mock settings for testing."""
    mock_settings = MagicMock()
    mock_settings.debug = True
    mock_settings.log_level = "DEBUG"
    mock_settings.pool_min_size = 5
    mock_settings.pool_max_size = 20
    mock_settings.migrations_dir = "migrations"
    mock_settings.ai_enabled = True
    mock_settings.mcp_enabled = False
    mock_settings.apps = ["app"]
    mock_settings.app_title = "Test App"
    mock_settings.app_version = "1.0.0"
    mock_settings.enable_studio = True
    mock_settings.studio_secret_token = "test_token"
    mock_settings.studio_expose_in_production = False
    mock_settings.studio_allowed_origins = []  # Allow all
    mock_settings.env = "development"
    mock_settings.installed_apps = ["app"]
    # v0.5.10: Tracing settings
    mock_settings.db_trace_enabled = True
    mock_settings.db_trace_slow_threshold_ms = 100.0
    mock_settings.db_trace_max_queries = 500
    return mock_settings


# =============================================================================
# Test /studio/db/queries Endpoint
# =============================================================================

class TestStudioDbQueriesEndpoint:
    """Tests for GET /studio/db/queries."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_test_app()
        return TestClient(app)
    
    @pytest.fixture
    def mock_env(self):
        """Set up mock environment."""
        mock_settings = create_mock_settings()
        
        with patch("aksara.studio.fastapi.verify_studio_auth", return_value=None):
            with patch("aksara.conf.settings", mock_settings):
                yield mock_settings
    
    def test_db_queries_endpoint_returns_200(self, client, mock_env):
        """Test that endpoint returns 200 OK."""
        with patch("aksara.db.tracing.is_tracing_enabled", return_value=True):
            with patch("aksara.db.tracing.get_trace_stats", return_value={
                "total_batches": 0,
                "total_queries": 0,
                "avg_queries_per_request": 0.0,
                "total_slow_queries": 0,
                "requests_with_slow_queries": 0,
                "requests_with_n_plus_one": 0,
            }):
                with patch("aksara.db.tracing.get_recent_traces", return_value=[]):
                    with patch("aksara.db.tracing.get_top_slow_queries", return_value=[]):
                        response = client.get("/studio/db/queries")
        
        assert response.status_code == 200
    
    def test_db_queries_response_structure(self, client, mock_env):
        """Test response structure matches StudioQueryInspector model."""
        with patch("aksara.db.tracing.is_tracing_enabled", return_value=True):
            with patch("aksara.db.tracing.get_trace_stats", return_value={
                "total_batches": 5,
                "total_queries": 25,
                "avg_queries_per_request": 5.0,
                "total_slow_queries": 2,
                "requests_with_slow_queries": 1,
                "requests_with_n_plus_one": 0,
            }):
                with patch("aksara.db.tracing.get_recent_traces", return_value=[]):
                    with patch("aksara.db.tracing.get_top_slow_queries", return_value=[]):
                        response = client.get("/studio/db/queries")
        
        data = response.json()
        
        assert "enabled" in data
        assert "slow_threshold_ms" in data
        assert "stats" in data
        assert "recent_batches" in data
        assert "top_slow_queries" in data
        
        # Check stats structure
        stats = data["stats"]
        assert "total_batches" in stats
        assert "total_queries" in stats
        assert "avg_queries_per_request" in stats
        assert "total_slow_queries" in stats
    
    def test_db_queries_tracing_disabled(self, client, mock_env):
        """Test response when tracing is disabled."""
        mock_env.db_trace_enabled = False
        
        with patch("aksara.db.tracing.is_tracing_enabled", return_value=False):
            with patch("aksara.db.tracing.get_trace_stats", return_value={
                "total_batches": 0,
                "total_queries": 0,
                "avg_queries_per_request": 0.0,
                "total_slow_queries": 0,
                "requests_with_slow_queries": 0,
                "requests_with_n_plus_one": 0,
            }):
                with patch("aksara.db.tracing.get_recent_traces", return_value=[]):
                    with patch("aksara.db.tracing.get_top_slow_queries", return_value=[]):
                        response = client.get("/studio/db/queries")
        
        data = response.json()
        assert data["enabled"] == False
    
    def test_db_queries_with_data(self, client, mock_env):
        """Test response with actual trace data."""
        from aksara.db.tracing import DbQueryTrace, DbQueryBatch
        from datetime import datetime, timezone
        
        mock_batch = DbQueryBatch(
            request_id="req-123",
            path="/api/users",
            method="GET",
            status_code=200,
            queries=[
                DbQueryTrace(
                    sql="SELECT * FROM users",
                    duration_ms=15.0,
                    operation="SELECT",
                    table="users",
                ),
            ],
        )
        
        mock_slow = DbQueryTrace(
            sql="SELECT * FROM large_table",
            duration_ms=150.0,
            operation="SELECT",
            table="large_table",
        )
        
        with patch("aksara.db.tracing.is_tracing_enabled", return_value=True):
            with patch("aksara.db.tracing.get_trace_stats", return_value={
                "total_batches": 1,
                "total_queries": 1,
                "avg_queries_per_request": 1.0,
                "total_slow_queries": 1,
                "requests_with_slow_queries": 1,
                "requests_with_n_plus_one": 0,
            }):
                with patch("aksara.db.tracing.get_recent_traces", return_value=[mock_batch]):
                    with patch("aksara.db.tracing.get_top_slow_queries", return_value=[mock_slow]):
                        response = client.get("/studio/db/queries")
        
        data = response.json()
        
        assert data["stats"]["total_batches"] == 1
        assert len(data["recent_batches"]) == 1
        assert data["recent_batches"][0]["request_id"] == "req-123"
        assert len(data["top_slow_queries"]) == 1
        assert data["top_slow_queries"][0]["duration_ms"] == 150.0


# =============================================================================
# Test /studio/db/queries/{request_id} Endpoint
# =============================================================================

class TestStudioDbQueryDetailEndpoint:
    """Tests for GET /studio/db/queries/{request_id}."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_test_app()
        return TestClient(app)
    
    @pytest.fixture
    def mock_env(self):
        """Set up mock environment."""
        mock_settings = create_mock_settings()
        
        with patch("aksara.studio.fastapi.verify_studio_auth", return_value=None):
            with patch("aksara.conf.settings", mock_settings):
                yield mock_settings
    
    def test_query_detail_found(self, client, mock_env):
        """Test getting detail for existing request."""
        from aksara.db.tracing import DbQueryTrace, DbQueryBatch
        
        mock_batch = DbQueryBatch(
            request_id="req-123",
            path="/api/users/1",
            method="GET",
            status_code=200,
            queries=[
                DbQueryTrace(
                    sql="SELECT * FROM users WHERE id = $1",
                    params=(1,),
                    duration_ms=12.5,
                ),
                DbQueryTrace(
                    sql="SELECT * FROM posts WHERE user_id = $1",
                    params=(1,),
                    duration_ms=8.3,
                ),
            ],
        )
        
        with patch("aksara.db.tracing.get_trace_by_request_id", return_value=mock_batch):
            response = client.get("/studio/db/queries/req-123")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["request_id"] == "req-123"
        assert data["path"] == "/api/users/1"
        assert len(data["queries"]) == 2
    
    def test_query_detail_not_found(self, client, mock_env):
        """Test 404 when request_id not found."""
        with patch("aksara.db.tracing.get_trace_by_request_id", return_value=None):
            response = client.get("/studio/db/queries/nonexistent")
        
        assert response.status_code == 404
        assert "no trace found" in response.json()["detail"].lower()
