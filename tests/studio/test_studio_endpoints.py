"""
Tests for Aksara Studio endpoints.

v0.5.0: Studio Core & Handshake

Tests:
- GET /studio/handshake
- GET /studio/context/summary
- GET /studio/health
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from aksara.studio.models import (
    StudioCapability,
    StudioChecksums,
    StudioContextSummary,
    StudioDatabaseStatus,
    StudioHandshake,
    StudioHealthResponse,
    StudioModelSummary,
    StudioProjectInfo,
)
from aksara.studio.fastapi import router


# =============================================================================
# Test Setup
# =============================================================================

def create_test_app() -> FastAPI:
    """Create a test FastAPI app with Studio router."""
    app = FastAPI(title="Test App", version="1.0.0")
    app.include_router(router)
    
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
    mock_settings.studio_expose_in_production = False
    return mock_settings


# =============================================================================
# StudioHandshake Tests
# =============================================================================

class TestStudioHandshake:
    """Tests for GET /studio/handshake endpoint."""
    
    def test_handshake_returns_project_info(self):
        """Handshake includes project metadata."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {}
                
                response = client.get("/studio/handshake")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "project" in data
        assert "protocol_version" in data
        assert data["protocol_version"] == "1.0"
        
        project = data["project"]
        assert "name" in project
        assert "aksara_version" in project
        assert "python_version" in project
        assert "debug_mode" in project
        assert "environment" in project
    
    def test_handshake_returns_database_status(self):
        """Handshake includes database status."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {}
                
                response = client.get("/studio/handshake")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "database" in data
        db = data["database"]
        
        assert "connected" in db
        assert "dialect" in db
        assert db["dialect"] == "postgresql"
        assert "pool_size" in db
        assert "pool_available" in db
    
    def test_handshake_returns_capabilities(self):
        """Handshake includes available capabilities."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {}
                
                response = client.get("/studio/handshake")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "capabilities" in data
        capabilities = data["capabilities"]
        
        # Should always have read_schema
        assert StudioCapability.READ_SCHEMA.value in capabilities
    
    def test_handshake_returns_checksums(self):
        """Handshake includes checksums for caching."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {}
                
                response = client.get("/studio/handshake")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "checksums" in data
        checksums = data["checksums"]
        
        assert "schema_checksum" in checksums
        assert "migrations_checksum" in checksums
        assert "settings_checksum" in checksums
        assert "routes_checksum" in checksums
        
        # Checksums should be 16-char hex strings
        assert len(checksums["schema_checksum"]) == 16
        assert len(checksums["migrations_checksum"]) == 16
    
    def test_handshake_returns_endpoints(self):
        """Handshake includes endpoint URLs."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {}
                
                response = client.get("/studio/handshake")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "endpoints" in data
        endpoints = data["endpoints"]
        
        assert "context_full" in endpoints
        assert "health" in endpoints
        assert "tools" in endpoints
    
    def test_handshake_returns_timestamp(self):
        """Handshake includes ISO timestamp."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {}
                
                response = client.get("/studio/handshake")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "timestamp" in data
        # Should be ISO format
        assert "T" in data["timestamp"]


# =============================================================================
# StudioContextSummary Tests
# =============================================================================

class TestStudioContextSummary:
    """Tests for GET /studio/context/summary endpoint."""
    
    def test_context_summary_returns_counts(self):
        """Context summary includes counts."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {}
                
                response = client.get("/studio/context/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "model_count" in data
        assert "viewset_count" in data
        assert "route_count" in data
        assert "ai_tool_count" in data
        assert "migration_count" in data
        assert "pending_migrations" in data
    
    def test_context_summary_returns_models(self):
        """Context summary includes model list."""
        app = create_test_app()
        client = TestClient(app)
        
        # Create a mock model class
        mock_model = MagicMock()
        mock_model.__name__ = "TestModel"
        mock_model._table_name = "test_models"
        mock_model._fields = {"id": MagicMock(), "name": MagicMock()}
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {"TestModel": mock_model}
                
                response = client.get("/studio/context/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "models" in data
        assert len(data["models"]) == 1
        
        model = data["models"][0]
        assert model["name"] == "TestModel"
        assert model["table_name"] == "test_models"
        assert "field_count" in model
        assert "has_relations" in model
    
    def test_context_summary_returns_checksums(self):
        """Context summary includes checksums."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {}
                
                response = client.get("/studio/context/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "checksums" in data
        checksums = data["checksums"]
        
        assert "schema_checksum" in checksums
        assert "migrations_checksum" in checksums


# =============================================================================
# StudioHealth Tests
# =============================================================================

class TestStudioHealth:
    """Tests for GET /studio/health endpoint."""
    
    def test_health_returns_status(self):
        """Health returns status field."""
        app = create_test_app()
        client = TestClient(app)
        
        response = client.get("/studio/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert data["status"] in ["healthy", "degraded"]
    
    def test_health_returns_aksara_version(self):
        """Health returns Aksara version."""
        app = create_test_app()
        client = TestClient(app)
        
        response = client.get("/studio/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "aksara_version" in data
        # Should be semver format
        assert "." in data["aksara_version"]
    
    def test_health_returns_database_status(self):
        """Health returns database status."""
        app = create_test_app()
        client = TestClient(app)
        
        response = client.get("/studio/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "database" in data
        db = data["database"]
        
        assert "connected" in db
        assert "dialect" in db
    
    def test_health_returns_timestamp(self):
        """Health returns timestamp."""
        app = create_test_app()
        client = TestClient(app)
        
        response = client.get("/studio/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "timestamp" in data
        assert "T" in data["timestamp"]
    
    def test_health_degraded_without_db(self):
        """Health returns degraded status without DB."""
        app = create_test_app()
        app._db = None
        app.state.db = None
        
        client = TestClient(app)
        response = client.get("/studio/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Without DB, should be degraded
        assert data["status"] == "degraded"
        assert data["database"]["connected"] == False


# =============================================================================
# Model Tests
# =============================================================================

class TestStudioModels:
    """Tests for Studio Pydantic models."""
    
    def test_studio_capability_enum(self):
        """StudioCapability has expected values."""
        assert StudioCapability.READ_SCHEMA.value == "read_schema"
        assert StudioCapability.READ_DATA.value == "read_data"
        assert StudioCapability.WRITE_DATA.value == "write_data"
        assert StudioCapability.AI_TOOLS.value == "ai_tools"
    
    def test_studio_database_status(self):
        """StudioDatabaseStatus creates correctly."""
        status = StudioDatabaseStatus(
            connected=True,
            dialect="postgresql",
            pool_size=10,
            pool_available=8,
        )
        
        assert status.connected == True
        assert status.dialect == "postgresql"
        assert status.pool_size == 10
        assert status.pool_available == 8
    
    def test_studio_project_info(self):
        """StudioProjectInfo creates correctly."""
        project = StudioProjectInfo(
            name="Test App",
            version="1.0.0",
            aksara_version="0.5.0",
            python_version="3.11.5",
            debug_mode=True,
            environment="development",
        )
        
        assert project.name == "Test App"
        assert project.aksara_version == "0.5.0"
        assert project.debug_mode == True
    
    def test_studio_checksums(self):
        """StudioChecksums creates correctly."""
        checksums = StudioChecksums(
            schema_checksum="abc123def4567890",
            migrations_checksum="def456abc1237890",
            settings_checksum="789abc123def4560",
            routes_checksum="123def456abc7890",
        )
        
        assert len(checksums.schema_checksum) == 16
        assert len(checksums.migrations_checksum) == 16


# =============================================================================
# Checksum Tests
# =============================================================================

class TestStudioChecksumUtils:
    """Tests for checksum computation."""
    
    def test_schema_checksum_deterministic(self):
        """Schema checksum is deterministic."""
        from aksara.studio.utils import compute_schema_checksum
        
        models = [{"name": "User", "fields": ["id", "name"]}]
        
        checksum1 = compute_schema_checksum(models)
        checksum2 = compute_schema_checksum(models)
        
        assert checksum1 == checksum2
        assert len(checksum1) == 16
    
    def test_schema_checksum_changes_with_models(self):
        """Schema checksum changes when models change."""
        from aksara.studio.utils import compute_schema_checksum
        
        models1 = [{"name": "User"}]
        models2 = [{"name": "Post"}]
        
        checksum1 = compute_schema_checksum(models1)
        checksum2 = compute_schema_checksum(models2)
        
        assert checksum1 != checksum2
    
    def test_settings_checksum(self):
        """Settings checksum works."""
        from aksara.studio.utils import compute_settings_checksum
        
        with patch("aksara.conf.settings", create_mock_settings()):
            checksum = compute_settings_checksum()
        
        assert len(checksum) == 16
