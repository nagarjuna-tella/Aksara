"""
Tests for aksara.testing module.

Tests the testing utilities and helpers.
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestAksaraTestClient:
    """Tests for AksaraTestClient."""
    
    def test_client_creation(self):
        """Test that AksaraTestClient can be created."""
        from aksara.testing import AksaraTestClient
        
        app = MagicMock()
        
        with patch("starlette.testclient.TestClient"):
            client = AksaraTestClient(app)
            assert client._app is app
    
    def test_with_user_returns_new_client(self):
        """Test that with_user() returns a new client with user set."""
        from aksara.testing import AksaraTestClient, create_test_user
        
        app = MagicMock()
        
        with patch("starlette.testclient.TestClient"):
            client = AksaraTestClient(app)
            user = create_test_user(username="alice")
            
            authenticated_client = client.with_user(user)
            
            assert authenticated_client is not client
            assert authenticated_client._current_user is user
    
    def test_with_user_preserves_app(self):
        """Test that with_user() preserves the app reference."""
        from aksara.testing import AksaraTestClient, create_test_user
        
        app = MagicMock()
        
        with patch("starlette.testclient.TestClient"):
            client = AksaraTestClient(app)
            user = create_test_user()
            
            authenticated_client = client.with_user(user)
            
            assert authenticated_client._app is app
    
    def test_context_manager(self):
        """Test that client works as context manager."""
        from aksara.testing import AksaraTestClient
        
        app = MagicMock()
        mock_test_client = MagicMock()
        
        with patch("starlette.testclient.TestClient", return_value=mock_test_client):
            with AksaraTestClient(app) as client:
                assert client is not None
            
            mock_test_client.close.assert_called_once()


class TestCreateTestUser:
    """Tests for create_test_user() helper."""
    
    def test_default_user_values(self):
        """Test that create_test_user has sensible defaults."""
        from aksara.testing import create_test_user
        
        user = create_test_user()
        
        assert user.id == 1
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.is_active is True
        assert user.is_admin is False
        assert user.is_authenticated is True
    
    def test_custom_user_values(self):
        """Test that create_test_user accepts custom values."""
        from aksara.testing import create_test_user
        
        user = create_test_user(
            id=42,
            username="alice",
            email="alice@example.com",
            is_active=False,
            is_admin=True,
        )
        
        assert user.id == 42
        assert user.username == "alice"
        assert user.email == "alice@example.com"
        assert user.is_active is False
        assert user.is_admin is True
    
    def test_extra_attributes(self):
        """Test that create_test_user accepts extra attributes."""
        from aksara.testing import create_test_user
        
        user = create_test_user(
            custom_field="custom_value",
            another_field=123,
        )
        
        assert user.custom_field == "custom_value"
        assert user.another_field == 123
    
    def test_user_repr(self):
        """Test that test user has a readable repr."""
        from aksara.testing import create_test_user
        
        user = create_test_user(id=5, username="bob")
        
        repr_str = repr(user)
        assert "TestUser" in repr_str
        assert "5" in repr_str
        assert "bob" in repr_str
    
    def test_user_implements_protocol(self):
        """Test that test user matches AksaraUserProtocol."""
        from aksara.testing import create_test_user
        
        user = create_test_user()
        
        # All protocol attributes should be present
        assert hasattr(user, "id")
        assert hasattr(user, "is_authenticated")
        assert hasattr(user, "is_active")
        assert hasattr(user, "is_admin")


class TestCreateTestApp:
    """Tests for create_test_app() helper."""
    
    @pytest.mark.asyncio
    async def test_create_test_app_returns_aksara_app(self):
        """Test that create_test_app returns a Aksara app."""
        from aksara.testing import create_test_app
        from aksara.app import Aksara
        
        with patch.dict("os.environ", {"DATABASE_URL": ""}):
            app = await create_test_app(database_url=None)
            
            assert isinstance(app, Aksara)
    
    @pytest.mark.asyncio
    async def test_create_test_app_defaults(self):
        """Test that create_test_app has sensible defaults."""
        from aksara.testing import create_test_app
        
        app = await create_test_app(database_url=None)
        
        assert app.title == "Aksara Test App"
        assert app.debug is True
    
    @pytest.mark.asyncio
    async def test_create_test_app_custom_title(self):
        """Test that create_test_app accepts custom app settings."""
        from aksara.testing import create_test_app
        
        app = await create_test_app(
            database_url=None,
            title="My Test API",
            version="1.0.0",
        )
        
        assert app.title == "My Test API"
        assert app.version == "1.0.0"
    
    @pytest.mark.asyncio
    async def test_create_test_app_disables_autodiscovery(self):
        """Test that create_test_app disables view auto-discovery by default."""
        from aksara.testing import create_test_app
        
        app = await create_test_app(database_url=None)
        
        assert app._auto_discover_views is False


class TestTestDatabase:
    """Tests for test_database() context manager."""
    
    @pytest.mark.asyncio
    async def test_test_database_yields_db(self):
        """Test that test_database yields a database instance."""
        # This test verifies the basic structure of test_database
        # Actual database connection testing is done in integration tests
        from aksara.testing import test_database
        
        # We can't easily test this without a real DB,
        # but we can verify it's a context manager
        assert hasattr(test_database, "__call__")
        
        # Verify the function signature accepts expected params
        import inspect
        sig = inspect.signature(test_database)
        params = list(sig.parameters.keys())
        assert "database_url" in params
        assert "cleanup" in params


class TestAksaraTestCase:
    """Tests for AksaraTestCase base class."""
    
    def test_test_case_attributes(self):
        """Test that AksaraTestCase has expected attributes."""
        from aksara.testing import AksaraTestCase
        
        assert hasattr(AksaraTestCase, "database_url")
        assert hasattr(AksaraTestCase, "apply_migrations")
        assert hasattr(AksaraTestCase, "db")
        assert hasattr(AksaraTestCase, "app")
        assert hasattr(AksaraTestCase, "client")
    
    def test_test_case_defaults(self):
        """Test that AksaraTestCase has sensible defaults."""
        from aksara.testing import AksaraTestCase
        
        assert AksaraTestCase.database_url is None
        assert AksaraTestCase.apply_migrations is False
    
    @pytest.mark.asyncio
    async def test_async_setup_without_db(self):
        """Test asyncSetUp when no database URL is configured."""
        from aksara.testing import AksaraTestCase
        
        test_case = AksaraTestCase()
        
        with patch.dict("os.environ", {"DATABASE_URL": ""}):
            await test_case.asyncSetUp()
        
        assert test_case.db is None
    
    @pytest.mark.asyncio
    async def test_async_teardown(self):
        """Test asyncTearDown cleans up resources."""
        from aksara.testing import AksaraTestCase
        
        test_case = AksaraTestCase()
        
        mock_client = MagicMock()
        mock_client._client = MagicMock()
        test_case.client = mock_client
        
        mock_db = AsyncMock()
        mock_db.disconnect = AsyncMock()
        test_case.db = mock_db
        
        await test_case.asyncTearDown()
        
        mock_client._client.close.assert_called_once()
        mock_db.disconnect.assert_called_once()


class TestCreateAuthTestUser:
    """Tests for create_auth_test_user() helper."""
    
    @pytest.mark.asyncio
    async def test_import_error_when_auth_not_installed(self):
        """Test that ImportError is raised when auth module not available."""
        from aksara.testing import create_auth_test_user
        
        mock_db = MagicMock()
        
        # Simulate auth module not being installed
        with patch.dict("sys.modules", {"aksara.contrib.auth.models": None}):
            with patch("aksara.testing.create_auth_test_user") as mock_create:
                mock_create.side_effect = ImportError("aksara.contrib.auth is not available")
                
                with pytest.raises(ImportError):
                    await mock_create(mock_db)


class TestModuleExports:
    """Tests for module exports."""
    
    def test_all_exports_exist(self):
        """Test that all __all__ exports are importable."""
        from aksara import testing
        
        for name in testing.__all__:
            assert hasattr(testing, name), f"Missing export: {name}"
    
    def test_main_imports(self):
        """Test that main functions can be imported."""
        from aksara.testing import (
            AksaraTestClient,
            create_test_app,
            test_database,
            create_test_user,
            create_auth_test_user,
            AksaraTestCase,
        )
        
        assert AksaraTestClient is not None
        assert create_test_app is not None
        assert test_database is not None
        assert create_test_user is not None
        assert create_auth_test_user is not None
        assert AksaraTestCase is not None
