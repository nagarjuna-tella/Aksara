"""
Tests for aksara.shell module.

Tests the interactive shell helpers and utilities.
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestArun:
    """Tests for the arun() async helper function."""
    
    def test_arun_runs_coroutine(self):
        """Test that arun() executes a coroutine and returns its result."""
        from aksara.shell import arun
        
        async def async_func():
            return 42
        
        result = arun(async_func())
        assert result == 42
    
    def test_arun_returns_value(self):
        """Test that arun() returns the coroutine's return value."""
        from aksara.shell import arun
        
        async def get_data():
            return {"name": "test", "value": 123}
        
        result = arun(get_data())
        assert result == {"name": "test", "value": 123}
    
    def test_arun_handles_exceptions(self):
        """Test that arun() propagates exceptions from the coroutine."""
        from aksara.shell import arun
        
        async def failing_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            arun(failing_func())
    
    def test_arun_with_async_iteration(self):
        """Test that arun() works with async iterables."""
        from aksara.shell import arun
        
        async def collect_items():
            items = []
            async def gen():
                for i in range(3):
                    yield i
            async for item in gen():
                items.append(item)
            return items
        
        result = arun(collect_items())
        assert result == [0, 1, 2]


class TestLoadModelsFromApps:
    """Tests for load_models_from_apps() function."""
    
    def test_load_models_returns_dict(self):
        """Test that load_models_from_apps returns a dictionary."""
        from aksara.shell import load_models_from_apps
        
        # Should return empty dict if no models found
        result = load_models_from_apps([])
        assert isinstance(result, dict)
    
    def test_load_models_with_nonexistent_app(self):
        """Test graceful handling of non-existent app modules."""
        from aksara.shell import load_models_from_apps
        
        # Should not raise, just return what's already registered
        result = load_models_from_apps(["nonexistent_app"])
        assert isinstance(result, dict)
    
    def test_load_models_includes_registered_models(self):
        """Test that registered models are included."""
        from aksara.shell import load_models_from_apps
        from aksara import Model, fields
        from aksara.registry import ModelRegistry
        
        # Clear and register a test model
        ModelRegistry.clear()
        
        class TestShellModel(Model):
            name = fields.String(max_length=100)
        
        result = load_models_from_apps(["nonexistent"])
        
        assert "TestShellModel" in result
        assert result["TestShellModel"] is TestShellModel
        
        # Cleanup
        ModelRegistry.clear()


class TestBuildShellNamespace:
    """Tests for build_shell_namespace() function."""
    
    def test_namespace_has_core_imports(self):
        """Test that namespace includes core Aksara imports."""
        from aksara.shell import build_shell_namespace
        
        namespace = build_shell_namespace(load_models=False)
        
        # Core imports
        assert "Model" in namespace
        assert "fields" in namespace
        assert "Database" in namespace
        assert "ModelRegistry" in namespace
        
        # Configuration
        assert "settings" in namespace
        assert "configure" in namespace
        
        # Exceptions
        assert "DoesNotExist" in namespace
        assert "MultipleObjectsReturned" in namespace
        
        # Async helper
        assert "arun" in namespace
    
    def test_namespace_arun_is_callable(self):
        """Test that arun in namespace is callable."""
        from aksara.shell import build_shell_namespace
        
        namespace = build_shell_namespace(load_models=False)
        
        async def test_coro():
            return "test"
        
        result = namespace["arun"](test_coro())
        assert result == "test"
    
    def test_namespace_with_database_url(self):
        """Test that namespace includes db when database_url is provided."""
        from aksara.shell import build_shell_namespace
        
        # Note: We provide a URL but don't connect, so db will be created but not connected
        namespace = build_shell_namespace(
            database_url="postgresql://localhost/test",
            load_models=False,
        )
        
        assert "db" in namespace
    
    def test_namespace_without_database_url(self):
        """Test that namespace has no db when database_url is not provided."""
        from aksara.shell import build_shell_namespace
        
        namespace = build_shell_namespace(database_url=None, load_models=False)
        
        assert "db" not in namespace


class TestGetShellBanner:
    """Tests for get_shell_banner() function."""
    
    def test_banner_includes_version(self):
        """Test that banner includes Aksara version."""
        from aksara.shell import get_shell_banner
        from aksara import __version__
        
        namespace = {"_loaded_models": []}
        banner = get_shell_banner(namespace)
        
        assert __version__ in banner
        assert "Aksara Shell" in banner
    
    def test_banner_shows_arun_help(self):
        """Test that banner shows arun() helper documentation."""
        from aksara.shell import get_shell_banner
        
        namespace = {"_loaded_models": []}
        banner = get_shell_banner(namespace)
        
        assert "arun" in banner
    
    def test_banner_shows_loaded_models(self):
        """Test that banner shows loaded model names."""
        from aksara.shell import get_shell_banner
        
        namespace = {"_loaded_models": ["User", "Post", "Comment"]}
        banner = get_shell_banner(namespace)
        
        assert "User" in banner
        assert "Post" in banner
        assert "Comment" in banner
    
    def test_banner_truncates_many_models(self):
        """Test that banner truncates when many models are loaded."""
        from aksara.shell import get_shell_banner
        
        # More than 5 models
        models = [f"Model{i}" for i in range(10)]
        namespace = {"_loaded_models": models}
        banner = get_shell_banner(namespace)
        
        # Should show "... (10 total)"
        assert "10 total" in banner
    
    def test_banner_shows_db_connection(self):
        """Test that banner shows db connection when available."""
        from aksara.shell import get_shell_banner
        
        namespace = {"_loaded_models": [], "db": MagicMock()}
        banner = get_shell_banner(namespace)
        
        assert "db" in banner.lower() or "Database" in banner


class TestStartStandardShell:
    """Tests for start_standard_shell() function."""
    
    def test_standard_shell_uses_namespace(self):
        """Test that standard shell receives the namespace."""
        from aksara.shell import start_standard_shell
        
        namespace = {"test_var": 42}
        
        with patch("code.InteractiveConsole") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console
            
            # Make interact exit immediately
            mock_console.interact.return_value = None
            
            start_standard_shell(namespace, "Test Banner")
            
            # Verify console was created with namespace
            mock_console_cls.assert_called_once()
            call_kwargs = mock_console_cls.call_args
            assert call_kwargs[1]["locals"]["test_var"] == 42


class TestStartIpythonShell:
    """Tests for start_ipython_shell() function."""
    
    def test_ipython_shell_import_error(self):
        """Test that ImportError is raised when IPython not installed."""
        from aksara.shell import start_ipython_shell
        
        namespace = {"test_var": 42}
        
        with patch.dict("sys.modules", {"IPython": None}):
            with pytest.raises(ImportError):
                start_ipython_shell(namespace, "Test Banner")


class TestRunShell:
    """Tests for run_shell() main entry point."""
    
    def test_run_shell_tries_ipython_first(self):
        """Test that run_shell tries IPython first when enabled."""
        from aksara.shell import run_shell
        
        with patch("aksara.shell.start_ipython_shell") as mock_ipython:
            mock_ipython.return_value = None
            
            run_shell(use_ipython=True)
            
            mock_ipython.assert_called_once()
    
    def test_run_shell_falls_back_to_standard(self):
        """Test that run_shell falls back to standard shell when IPython unavailable."""
        from aksara.shell import run_shell
        
        with patch("aksara.shell.start_ipython_shell") as mock_ipython:
            mock_ipython.side_effect = ImportError("IPython not installed")
            
            with patch("aksara.shell.start_standard_shell") as mock_standard:
                mock_standard.return_value = None
                
                run_shell(use_ipython=True)
                
                mock_standard.assert_called_once()
    
    def test_run_shell_skips_ipython_when_disabled(self):
        """Test that run_shell skips IPython when use_ipython=False."""
        from aksara.shell import run_shell
        
        with patch("aksara.shell.start_ipython_shell") as mock_ipython:
            with patch("aksara.shell.start_standard_shell") as mock_standard:
                mock_standard.return_value = None
                
                run_shell(use_ipython=False)
                
                mock_ipython.assert_not_called()
                mock_standard.assert_called_once()
