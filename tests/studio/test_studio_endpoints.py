"""
Tests for Aksara Studio endpoints.

v0.5.0: Studio Core & Handshake
v0.5.1: Studio Core Polish - richer summaries, security, migrations endpoint
v0.5.2: Runtime Diagnostics - /studio/runtime/info and /studio/runtime/routes

Tests:
- GET /studio/handshake
- GET /studio/context/summary
- GET /studio/health
- GET /studio/migrations/summary (v0.5.1)
- GET /studio/schema/handshake (v0.5.1)
- Origin security (v0.5.1)
- GET /studio/runtime/info (v0.5.2)
- GET /studio/runtime/routes (v0.5.2)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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
    # v0.5.1: New models
    StudioMigrationStatus,
    StudioAppMigrationSummary,
    StudioMigrationConflict,
    StudioMigrationSummary,
    # v0.5.2: Runtime models
    StudioRuntimeInfo,
    StudioRouteInfo,
)
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


def create_test_app_with_auth() -> FastAPI:
    """Create a test FastAPI app with Studio router (no auth override)."""
    app = FastAPI(title="Test App", version="1.0.0")
    app.include_router(router)
    
    # Do NOT override verify_studio_auth — tests that verify auth behavior need real auth
    
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
    mock_settings.studio_require_auth = False
    mock_settings.studio_auth_token = None
    mock_settings.studio_allowed_origins = []
    mock_settings.env = "development"  # v0.5.3: Required for runtime info
    mock_settings.installed_apps = ["app"]  # v0.5.3: Required for runtime info
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


# =============================================================================
# v0.5.1: Context Summary Enhanced Fields Tests
# =============================================================================

class TestStudioContextSummaryV051:
    """Tests for v0.5.1 enhanced StudioContextSummary fields."""
    
    def test_context_summary_returns_app_count(self):
        """Context summary includes app_count (v0.5.1)."""
        app = create_test_app()
        client = TestClient(app)
        
        mock_settings = create_mock_settings()
        mock_settings.installed_apps = ["app", "aksara.contrib.auth"]
        
        with patch("aksara.conf.settings", mock_settings):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {}
                with patch("aksara.migrations.discover_all_migrations", return_value=[]):
                    response = client.get("/studio/context/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "app_count" in data
        assert data["app_count"] == 2
    
    def test_context_summary_returns_database_status(self):
        """Context summary includes database_status (v0.5.1)."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {}
                with patch("aksara.migrations.discover_all_migrations", return_value=[]):
                    response = client.get("/studio/context/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "database_status" in data
        db_status = data["database_status"]
        
        assert "connected" in db_status
        assert "dialect" in db_status
    
    def test_context_summary_returns_migration_status(self):
        """Context summary includes migration_status (v0.5.1)."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {}
                with patch("aksara.migrations.discover_all_migrations", return_value=[]):
                    response = client.get("/studio/context/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "migration_status" in data
        mig_status = data["migration_status"]
        
        assert "total" in mig_status
        assert "applied" in mig_status
        assert "pending" in mig_status
        assert "has_conflicts" in mig_status


# =============================================================================
# v0.5.1: Migrations Summary Endpoint Tests
# =============================================================================

class TestStudioMigrationsSummary:
    """Tests for GET /studio/migrations/summary endpoint (v0.5.1)."""
    
    def test_migrations_summary_returns_counts(self):
        """Migrations summary includes counts."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.migrations.discover_all_migrations", return_value=[]):
                with patch("aksara.migrations.build_migration_graph") as mock_graph:
                    mock_graph.return_value.heads_for_app.return_value = []
                    with patch("aksara.migrations.check_migration_conflicts", return_value={}):
                        response = client.get("/studio/migrations/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_migrations" in data
        assert "applied_migrations" in data
        assert "pending_migrations" in data
    
    def test_migrations_summary_returns_apps(self):
        """Migrations summary includes per-app stats."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.migrations.discover_all_migrations", return_value=[]):
                with patch("aksara.migrations.build_migration_graph") as mock_graph:
                    mock_graph.return_value.heads_for_app.return_value = []
                    with patch("aksara.migrations.check_migration_conflicts", return_value={}):
                        response = client.get("/studio/migrations/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "apps" in data
        assert isinstance(data["apps"], list)
    
    def test_migrations_summary_returns_conflicts(self):
        """Migrations summary includes conflicts array."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.migrations.discover_all_migrations", return_value=[]):
                with patch("aksara.migrations.build_migration_graph") as mock_graph:
                    mock_graph.return_value.heads_for_app.return_value = []
                    with patch("aksara.migrations.check_migration_conflicts", return_value={}):
                        response = client.get("/studio/migrations/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "conflicts" in data
        assert isinstance(data["conflicts"], list)
    
    def test_migrations_summary_returns_checksum(self):
        """Migrations summary includes checksum."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.migrations.discover_all_migrations", return_value=[]):
                with patch("aksara.migrations.build_migration_graph") as mock_graph:
                    mock_graph.return_value.heads_for_app.return_value = []
                    with patch("aksara.migrations.check_migration_conflicts", return_value={}):
                        response = client.get("/studio/migrations/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "migrations_checksum" in data
        assert len(data["migrations_checksum"]) == 16


# =============================================================================
# v0.5.1: Schema Handshake Endpoint Tests
# =============================================================================

class TestStudioSchemaHandshake:
    """Tests for GET /studio/schema/handshake endpoint (v0.5.1)."""
    
    def test_schema_handshake_returns_json_schema(self):
        """Schema handshake returns JSON Schema."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/schema/handshake")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be a valid JSON Schema
        assert "type" in data
        assert data["type"] == "object"
    
    def test_schema_handshake_has_properties(self):
        """Schema handshake JSON Schema has properties."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/schema/handshake")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "properties" in data
        props = data["properties"]
        
        # Should have expected properties from StudioHandshake
        assert "protocol_version" in props
        assert "project" in props
        assert "database" in props
        assert "capabilities" in props
        assert "checksums" in props
    
    def test_schema_handshake_has_title(self):
        """Schema handshake JSON Schema has title."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/schema/handshake")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "title" in data
        assert data["title"] == "StudioHandshake"


# =============================================================================
# v0.5.1: Origin Security Tests
# =============================================================================

class TestStudioOriginSecurity:
    """Tests for Studio origin-based security (v0.5.1)."""
    
    def test_allowed_origin_passes(self):
        """Request with allowed origin passes."""
        app = create_test_app()
        client = TestClient(app)
        
        mock_settings = create_mock_settings()
        mock_settings.studio_allowed_origins = ["https://studio.aksara.dev"]
        
        with patch("aksara.conf.settings", mock_settings):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {}
                response = client.get(
                    "/studio/health",
                    headers={"Origin": "https://studio.aksara.dev"}
                )
        
        assert response.status_code == 200
    
    def test_no_origin_header_passes(self):
        """Request without Origin header passes (same-origin, CLI)."""
        app = create_test_app()
        client = TestClient(app)
        
        mock_settings = create_mock_settings()
        mock_settings.studio_allowed_origins = ["https://studio.aksara.dev"]
        
        with patch("aksara.conf.settings", mock_settings):
            response = client.get("/studio/health")
        
        assert response.status_code == 200
    
    def test_disallowed_origin_blocked(self):
        """Request with disallowed origin is blocked."""
        app = create_test_app_with_auth()
        client = TestClient(app)
        
        mock_settings = create_mock_settings()
        mock_settings.studio_allowed_origins = ["https://studio.aksara.dev"]
        
        with patch("aksara.conf.settings", mock_settings):
            response = client.get(
                "/studio/health",
                headers={"Origin": "https://evil.example.com"}
            )
        
        assert response.status_code == 403
        assert "not allowed" in response.json()["detail"]
    
    def test_wildcard_allows_all(self):
        """Wildcard in allowed origins allows all origins."""
        app = create_test_app()
        client = TestClient(app)
        
        mock_settings = create_mock_settings()
        mock_settings.studio_allowed_origins = ["*"]
        
        with patch("aksara.conf.settings", mock_settings):
            response = client.get(
                "/studio/health",
                headers={"Origin": "https://any-origin.example.com"}
            )
        
        assert response.status_code == 200
    
    def test_empty_origins_allows_all(self):
        """Empty allowed origins list allows all origins."""
        app = create_test_app()
        client = TestClient(app)
        
        mock_settings = create_mock_settings()
        mock_settings.studio_allowed_origins = []
        
        with patch("aksara.conf.settings", mock_settings):
            response = client.get(
                "/studio/health",
                headers={"Origin": "https://any-origin.example.com"}
            )
        
        assert response.status_code == 200


class TestStudioAuthentication:
    """Tests for Studio authentication requirements."""

    def test_studio_requires_auth_when_enabled(self):
        """Studio endpoints should reject unauthenticated access by default."""
        app = create_test_app_with_auth()
        client = TestClient(app)

        mock_settings = create_mock_settings()
        mock_settings.studio_require_auth = True
        mock_settings.debug = False

        with patch("aksara.conf.settings", mock_settings):
            response = client.get("/studio/handshake")

        assert response.status_code == 401
        assert response.json()["detail"] == "Studio requires authentication"

    def test_studio_accepts_bearer_token(self):
        """Studio endpoints should accept the configured bearer token."""
        app = create_test_app()
        client = TestClient(app)

        mock_settings = create_mock_settings()
        mock_settings.studio_require_auth = True
        mock_settings.debug = False
        mock_settings.studio_auth_token = "studio-secret"

        with patch("aksara.conf.settings", mock_settings):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {}
                response = client.get(
                    "/studio/handshake",
                    headers={"Authorization": "Bearer studio-secret"},
                )

        assert response.status_code == 200

    def test_studio_accepts_staff_session_cookie(self):
        """Studio endpoints should accept valid staff sessions."""
        app = create_test_app()
        app.state.db = MagicMock()
        client = TestClient(app)

        mock_settings = create_mock_settings()
        mock_settings.studio_require_auth = True
        mock_settings.debug = False

        mock_user = MagicMock()
        mock_user.is_staff = True

        with patch("aksara.conf.settings", mock_settings):
            with patch("aksara.registry.ModelRegistry") as mock_registry:
                mock_registry.all.return_value = {}
                with patch("aksara.contrib.auth.get_user_from_session_token", new_callable=AsyncMock) as mock_get_user:
                    mock_get_user.return_value = mock_user
                    response = client.get(
                        "/studio/handshake",
                        cookies={"session_token": "session-token"},
                    )

        assert response.status_code == 200


# =============================================================================
# v0.5.1: New Model Tests
# =============================================================================

class TestStudioModelsV051:
    """Tests for v0.5.1 new Studio Pydantic models."""
    
    def test_studio_migration_status(self):
        """StudioMigrationStatus creates correctly."""
        status = StudioMigrationStatus(
            total=10,
            applied=8,
            pending=2,
            has_conflicts=False,
            last_applied="0008_add_index",
        )
        
        assert status.total == 10
        assert status.applied == 8
        assert status.pending == 2
        assert status.has_conflicts == False
        assert status.last_applied == "0008_add_index"
    
    def test_studio_app_migration_summary(self):
        """StudioAppMigrationSummary creates correctly."""
        summary = StudioAppMigrationSummary(
            app_label="blog",
            total=5,
            applied=4,
            pending=1,
            has_conflicts=False,
            head_migrations=["0005_add_tags"],
        )
        
        assert summary.app_label == "blog"
        assert summary.total == 5
        assert summary.head_migrations == ["0005_add_tags"]
    
    def test_studio_migration_conflict(self):
        """StudioMigrationConflict creates correctly."""
        conflict = StudioMigrationConflict(
            app_label="blog",
            heads=["0005_branch_a", "0005_branch_b"],
            message="Conflicting migrations detected.",
        )
        
        assert conflict.app_label == "blog"
        assert len(conflict.heads) == 2
    
    def test_studio_migration_summary(self):
        """StudioMigrationSummary creates correctly."""
        summary = StudioMigrationSummary(
            total_migrations=15,
            applied_migrations=12,
            pending_migrations=3,
            apps=[],
            conflicts=[],
            migrations_checksum="abc1234567890123",
            last_applied="0012_latest",
        )
        
        assert summary.total_migrations == 15
        assert summary.pending_migrations == 3
        assert summary.last_applied == "0012_latest"
    
    def test_studio_context_summary_with_new_fields(self):
        """StudioContextSummary includes v0.5.1 fields."""
        summary = StudioContextSummary(
            app_count=3,
            model_count=5,
            viewset_count=2,
            route_count=15,
            ai_tool_count=10,
            migration_count=8,
            pending_migrations=1,
            database_status=StudioDatabaseStatus(connected=True),
            migration_status=StudioMigrationStatus(total=8, applied=7, pending=1),
            models=[],
            checksums=StudioChecksums(
                schema_checksum="a" * 16,
                migrations_checksum="b" * 16,
                settings_checksum="c" * 16,
                routes_checksum="d" * 16,
            ),
        )
        
        assert summary.app_count == 3
        assert summary.database_status.connected == True
        assert summary.migration_status.total == 8
        # Test schema_checksum property
        assert summary.schema_checksum == "a" * 16


# =============================================================================
# v0.5.2: Runtime Info Endpoint Tests
# =============================================================================

class TestStudioRuntimeInfoEndpoint:
    """Tests for GET /studio/runtime/info endpoint."""
    
    def test_runtime_info_returns_process_info(self):
        """Runtime info includes process and version details."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.studio.utils._get_database_status") as mock_db:
                mock_db.return_value = StudioDatabaseStatus(connected=True)
                
                response = client.get("/studio/runtime/info")
        
        assert response.status_code == 200
        data = response.json()
        
        # Core fields
        assert "app_version" in data
        assert "python_version" in data
        assert "debug" in data
        assert "env" in data
        assert "pid" in data
        assert "start_time" in data
        assert "uptime_seconds" in data
        
        # Types
        assert isinstance(data["pid"], int)
        assert isinstance(data["uptime_seconds"], float)
        assert isinstance(data["debug"], bool)
    
    def test_runtime_info_includes_database_status(self):
        """Runtime info includes database connection status."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.studio.utils._get_database_status") as mock_db:
                mock_db.return_value = StudioDatabaseStatus(connected=True)
                
                response = client.get("/studio/runtime/info")
        
        data = response.json()
        
        assert "database_status" in data
        # database_status is a string: 'ok', 'degraded', or 'disconnected'
        assert data["database_status"] in ["ok", "degraded", "disconnected"]
    
    def test_runtime_info_includes_studio_info(self):
        """Runtime info includes Studio configuration."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            with patch("aksara.studio.utils._get_database_status") as mock_db:
                mock_db.return_value = StudioDatabaseStatus(connected=True)
                
                response = client.get("/studio/runtime/info")
        
        data = response.json()
        
        assert "studio_enabled" in data
        assert "studio_base_path" in data
        assert data["studio_enabled"] == True
        assert data["studio_base_path"] == "/studio"


class TestStudioRoutesEndpoint:
    """Tests for GET /studio/runtime/routes endpoint."""
    
    def test_routes_returns_list(self):
        """Routes endpoint returns list of routes."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/runtime/routes")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) > 0  # Should have at least the studio routes
    
    def test_routes_include_studio_routes(self):
        """Routes include Studio endpoints marked correctly."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/runtime/routes")
        
        data = response.json()
        
        # Find a studio route
        studio_routes = [r for r in data if r.get("is_studio")]
        assert len(studio_routes) > 0
        
        # Check route structure
        route = studio_routes[0]
        assert "path" in route
        assert "methods" in route
        assert "name" in route
        assert "is_studio" in route
        assert "is_admin" in route
        assert "is_ai" in route
    
    def test_routes_handshake_is_marked_as_studio(self):
        """The /studio/handshake route is marked as Studio route."""
        app = create_test_app()
        client = TestClient(app)
        
        with patch("aksara.conf.settings", create_mock_settings()):
            response = client.get("/studio/runtime/routes")
        
        data = response.json()
        
        # Find the handshake route
        handshake_routes = [r for r in data if "/studio/handshake" in r.get("path", "")]
        assert len(handshake_routes) > 0
        
        handshake = handshake_routes[0]
        assert handshake["is_studio"] == True
        assert handshake["is_admin"] == False


# =============================================================================
# v0.5.2: Runtime Models Tests
# =============================================================================

class TestStudioRuntimeModels:
    """Tests for v0.5.2 Pydantic models."""
    
    def test_studio_runtime_info_creates_correctly(self):
        """StudioRuntimeInfo creates with all fields."""
        info = StudioRuntimeInfo(
            app_version="1.0.0",
            python_version="3.12.0",
            debug=True,
            env="development",
            pid=12345,
            start_time="2026-02-15T10:00:00Z",
            uptime_seconds=3600.5,
            database_status="ok",
            pending_migrations=2,
            installed_apps=["blog", "users"],
            studio_enabled=True,
            studio_base_path="/studio",
        )
        
        assert info.app_version == "1.0.0"
        assert info.python_version == "3.12.0"
        assert info.debug == True
        assert info.env == "development"
        assert info.pid == 12345
        assert info.uptime_seconds == 3600.5
        assert info.database_status == "ok"
        assert info.pending_migrations == 2
        assert len(info.installed_apps) == 2
        assert info.studio_enabled == True
    
    def test_studio_runtime_info_defaults(self):
        """StudioRuntimeInfo has sensible defaults."""
        info = StudioRuntimeInfo(
            app_version="1.0.0",
            python_version="3.12.0",
            debug=False,
            env="production",
            pid=1000,
            start_time="2026-02-15T10:00:00Z",
            uptime_seconds=0.0,
            database_status="disconnected",
        )
        
        # Optional fields have defaults
        assert info.pending_migrations == 0
        assert info.installed_apps == []
        assert info.studio_enabled == True
        assert info.studio_base_path == "/studio"
    
    def test_studio_route_info_creates_correctly(self):
        """StudioRouteInfo creates with all fields."""
        route = StudioRouteInfo(
            path="/api/v1/users",
            methods=["GET", "POST"],
            name="users_list",
            app_label="users",
            is_studio=False,
            is_admin=False,
            is_ai=False,
        )
        
        assert route.path == "/api/v1/users"
        assert route.methods == ["GET", "POST"]
        assert route.name == "users_list"
        assert route.app_label == "users"
        assert route.is_studio == False
    
    def test_studio_route_info_detects_studio_route(self):
        """StudioRouteInfo correctly marks Studio routes."""
        route = StudioRouteInfo(
            path="/studio/handshake",
            methods=["GET"],
            name="studio_handshake",
            app_label=None,
            is_studio=True,
            is_admin=False,
            is_ai=False,
        )
        
        assert route.is_studio == True
        assert route.is_admin == False
        assert route.is_ai == False
    
    def test_studio_route_info_detects_admin_route(self):
        """StudioRouteInfo correctly marks Admin routes."""
        route = StudioRouteInfo(
            path="/admin/users/",
            methods=["GET"],
            name="admin_users_list",
            app_label="users",
            is_studio=False,
            is_admin=True,
            is_ai=False,
        )
        
        assert route.is_studio == False
        assert route.is_admin == True
    
    def test_studio_route_info_detects_ai_route(self):
        """StudioRouteInfo correctly marks AI routes."""
        route = StudioRouteInfo(
            path="/ai/query",
            methods=["POST"],
            name="ai_query",
            app_label=None,
            is_studio=False,
            is_admin=False,
            is_ai=True,
        )
        
        assert route.is_ai == True


class TestAgentContextSummaryEndpoint:
    """Tests for GET /studio/agent/context/summary."""

    def test_summary_returns_list(self):
        app = create_test_app()
        client = TestClient(app)
        response = client.get("/studio/agent/context/summary")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_summary_sections_have_required_fields(self):
        app = create_test_app()
        client = TestClient(app)
        response = client.get("/studio/agent/context/summary")
        assert response.status_code == 200
        for section in response.json():
            assert "name" in section
            assert "title" in section
            assert "description" in section
            assert "size_kb" in section

    def test_summary_heavy_and_async_sections_are_placeholders(self):
        """Async sections (migrations, diagnostics) and expensive-to-compute sections
        (db_queries, query_stats, schema_analysis, semantic_index) must have
        size_kb=None so the Context tab load stays cheap."""
        app = create_test_app()
        client = TestClient(app)
        response = client.get("/studio/agent/context/summary")
        sections = {s["name"]: s for s in response.json()}
        placeholder_names = (
            "migrations", "diagnostics",
            "db_queries", "query_stats", "schema_analysis", "semantic_index",
        )
        for name in placeholder_names:
            assert name in sections, f"{name} missing from summary"
            assert sections[name]["size_kb"] is None, (
                f"{name} should be size_kb=None (placeholder) but has size_kb={sections[name]['size_kb']}"
            )

    def test_summary_schema_checksum_has_real_size(self):
        """schema_checksum is cheap (SHA-256 of field names only) so it must
        report a numeric size_kb rather than appearing as a placeholder."""
        from aksara.studio.utils import build_agent_context_summary
        sections = {s["name"]: s for s in build_agent_context_summary()}
        assert "schema_checksum" in sections
        assert sections["schema_checksum"]["size_kb"] is not None

    def test_summary_includes_project_info(self):
        app = create_test_app()
        client = TestClient(app)
        response = client.get("/studio/agent/context/summary")
        names = [s["name"] for s in response.json()]
        assert "project_info" in names

    def test_summary_all_12_sections_present(self):
        """Summary must account for every section the full agent context exposes."""
        expected = {
            "project_info", "models", "routes", "migrations", "diagnostics",
            "ai_profiles", "ai_hints", "db_queries", "schema_checksum",
            "query_stats", "schema_analysis", "semantic_index",
        }
        app = create_test_app()
        client = TestClient(app)
        response = client.get("/studio/agent/context/summary")
        names = {s["name"] for s in response.json()}
        assert expected == names

    def test_summary_cheap_section_descriptions_match_full_context(self):
        """Section descriptions must match the full context builder — regression guard
        for payload reduction (reduced payloads were paired with shorter descriptions)."""
        from aksara.studio.utils import build_agent_context_summary
        sections = {s["name"]: s for s in build_agent_context_summary()}
        assert sections["project_info"]["description"] == "Application name, version, environment, and runtime details"
        assert sections["models"]["description"] == "Registered database models with fields and relations"
        assert sections["routes"]["description"] == "All registered API endpoints with methods and labels"

    def test_summary_project_info_size_reflects_full_payload(self):
        """project_info size_kb must account for environment and python_version fields."""
        import json
        from aksara.studio.utils import build_agent_context_summary
        sections = {s["name"]: s for s in build_agent_context_summary()}
        pi = sections["project_info"]
        assert pi["size_kb"] is not None
        # Full payload has 6 keys; minimum JSON encoding for 6 string/bool keys is > 0.08 KB
        min_size = len(json.dumps({"app_title": "", "app_version": "", "debug": False,
                                   "environment": "", "python_version": "", "aksara_version": ""})) / 1024
        assert pi["size_kb"] >= min_size

    def test_summary_routes_size_is_list_not_count_dict(self):
        """Routes section must serialise the full route list, not just a count dict."""
        import json
        from aksara.studio.utils import build_agent_context_summary
        from unittest.mock import patch, MagicMock
        fake_route = MagicMock()
        fake_route.model_dump.return_value = {"path": "/test", "method": "GET", "label": "Test"}
        with patch("aksara.studio.utils.build_routes_info", return_value=[fake_route, fake_route]):
            sections = {s["name"]: s for s in build_agent_context_summary()}
        routes = sections["routes"]
        assert routes["size_kb"] is not None
        # Two routes serialised as a list is larger than {"count": 2}
        count_only_size = len(json.dumps({"count": 2})) / 1024
        assert routes["size_kb"] > count_only_size
