"""
Tests for example app running with the new scaffold structure.

Tests that a generated project:
- Can be imported without errors
- Has working ViewSet routes
- Has working AI schema endpoints
- Has working health check
"""

import pytest
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from vidyut.cli.scaffold import create_project_scaffold, write_scaffold_files


class TestGeneratedAppImports:
    """Test that generated app can be imported correctly."""
    
    def setup_method(self):
        """Create a temporary directory and scaffold for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
        self.project_name = "testapp"
        
        # Create scaffold
        files = create_project_scaffold(self.project_name, self.base_path)
        write_scaffold_files(files)
        
        # Add project to path
        self.project_path = self.base_path / self.project_name
        if str(self.project_path) not in sys.path:
            sys.path.insert(0, str(self.project_path))
    
    def teardown_method(self):
        """Clean up temporary directory and path."""
        # Remove from path
        if str(self.project_path) in sys.path:
            sys.path.remove(str(self.project_path))
        
        # Clean up temp dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        # Clean up imported modules
        modules_to_remove = [k for k in sys.modules.keys() if k.startswith('app') or k.startswith('settings')]
        for mod in modules_to_remove:
            del sys.modules[mod]
    
    def test_app_models_can_be_imported(self):
        """app.models should be importable."""
        # We need to import from the generated project
        import importlib.util
        
        models_path = self.project_path / "app" / "models.py"
        spec = importlib.util.spec_from_file_location("app.models", models_path)
        models = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(models)
        
        # Check models exist
        assert hasattr(models, 'User')
        assert hasattr(models, 'Post')
    
    def test_app_serializers_can_be_imported(self):
        """app.serializers should be importable after models."""
        import importlib.util
        
        # First import models
        models_path = self.project_path / "app" / "models.py"
        spec = importlib.util.spec_from_file_location("app.models", models_path)
        models = importlib.util.module_from_spec(spec)
        sys.modules['app.models'] = models
        spec.loader.exec_module(models)
        
        # Then import serializers
        serializers_path = self.project_path / "app" / "serializers.py"
        spec = importlib.util.spec_from_file_location("app.serializers", serializers_path)
        serializers = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(serializers)
        
        assert hasattr(serializers, 'UserSerializer')
        assert hasattr(serializers, 'PostSerializer')
    
    def test_settings_can_be_imported(self):
        """settings.py should be importable."""
        import importlib.util
        
        settings_path = self.project_path / "settings.py"
        spec = importlib.util.spec_from_file_location("settings", settings_path)
        settings_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(settings_module)
        
        assert hasattr(settings_module, 'Settings')
        assert hasattr(settings_module, 'settings')


class TestGeneratedAppStructure:
    """Test structural aspects of the generated app."""
    
    def setup_method(self):
        """Create a temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_models_use_vidyut_model_base(self):
        """Models should use Vidyut Model base class."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        models_path = self.base_path / "testapp" / "app" / "models.py"
        content = models_path.read_text()
        
        assert "from vidyut import Model, fields" in content
        assert "class User(Model):" in content
        assert "class Post(Model):" in content
    
    def test_views_use_vidyut_viewset(self):
        """Views should use Vidyut ModelViewSet."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        views_path = self.base_path / "testapp" / "app" / "views.py"
        content = views_path.read_text()
        
        assert "from vidyut import" in content
        assert "ModelViewSet" in content
        assert "class UserViewSet(ModelViewSet):" in content
    
    def test_serializers_use_vidyut_serializer(self):
        """Serializers should use Vidyut ModelSerializer."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        serializers_path = self.base_path / "testapp" / "app" / "serializers.py"
        content = serializers_path.read_text()
        
        assert "from vidyut import ModelSerializer" in content
        assert "class UserSerializer(ModelSerializer):" in content
    
    def test_main_uses_vidyut_app(self):
        """Main should use Vidyut app, not FastAPI."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        main_path = self.base_path / "testapp" / "main.py"
        content = main_path.read_text()
        
        assert "from vidyut import Vidyut" in content
        assert "app = Vidyut(" in content
        assert "from fastapi import" not in content


class TestViewsHaveRequiredEndpoints:
    """Test that views define all required endpoints."""
    
    def setup_method(self):
        """Create a temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_user_viewset_has_custom_actions(self):
        """UserViewSet should have custom actions."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        views_path = self.base_path / "testapp" / "app" / "views.py"
        content = views_path.read_text()
        
        # Check for user actions
        assert "async def deactivate" in content
        assert "async def activate" in content
        assert "async def active" in content
        assert "async def stats" in content
    
    def test_post_viewset_has_custom_actions(self):
        """PostViewSet should have custom actions."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        views_path = self.base_path / "testapp" / "app" / "views.py"
        content = views_path.read_text()
        
        # Check for post actions
        assert "async def publish" in content
        assert "async def unpublish" in content
        assert "async def published" in content
    
    def test_ai_schema_endpoints_registered(self):
        """AI schema endpoints should be registered in views."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        views_path = self.base_path / "testapp" / "app" / "views.py"
        content = views_path.read_text()
        
        assert '@app.get("/ai/schema"' in content
        assert "get_ai_schemas" in content
        assert "get_model_ai_schema" in content


class TestSettingsConfiguration:
    """Test settings configuration."""
    
    def setup_method(self):
        """Create a temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_settings_extends_vidyut_settings(self):
        """Settings should extend VidyutSettings."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        settings_path = self.base_path / "testapp" / "settings.py"
        content = settings_path.read_text()
        
        assert "from vidyut.conf import Settings as VidyutSettings" in content
        assert "class Settings(VidyutSettings):" in content
    
    def test_env_has_required_vars(self):
        """Env file should have all required variables."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        env_path = self.base_path / "testapp" / ".env"
        content = env_path.read_text()
        
        required_vars = [
            "DATABASE_URL=",
            "VIDYUT_DEBUG=",
            "VIDYUT_LOG_LEVEL=",
            "VIDYUT_APP_TITLE=",
            "VIDYUT_APP_VERSION=",
        ]
        
        for var in required_vars:
            assert var in content, f"Missing environment variable: {var}"


class TestMigrationReadiness:
    """Test that generated project is ready for migrations."""
    
    def setup_method(self):
        """Create a temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_migrations_dir_exists(self):
        """Migrations directory should exist."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        migrations_dir = self.base_path / "testapp" / "migrations"
        assert migrations_dir.is_dir()
        assert (migrations_dir / "__init__.py").exists()
    
    def test_no_create_table_sql_in_main(self):
        """Main should not contain CREATE TABLE or get_create_table_sql."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        main_path = self.base_path / "testapp" / "main.py"
        content = main_path.read_text()
        
        assert "CREATE TABLE" not in content
        assert "get_create_table_sql" not in content
    
    def test_readme_has_migration_instructions(self):
        """README should include migration instructions."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        readme_path = self.base_path / "testapp" / "README.md"
        content = readme_path.read_text()
        
        assert "vidyut makemigrations" in content
        assert "vidyut migrate" in content


class TestProjectDocumentation:
    """Test that generated project has proper documentation."""
    
    def setup_method(self):
        """Create a temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_readme_exists(self):
        """README.md should exist."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        readme_path = self.base_path / "testapp" / "README.md"
        assert readme_path.exists()
    
    def test_readme_has_quick_start(self):
        """README should have quick start instructions."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        readme_path = self.base_path / "testapp" / "README.md"
        content = readme_path.read_text()
        
        assert "Quick Start" in content
        assert "pip install" in content
        assert "vidyut run main:app" in content
    
    def test_readme_has_api_endpoints_docs(self):
        """README should document API endpoints."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        readme_path = self.base_path / "testapp" / "README.md"
        content = readme_path.read_text()
        
        assert "/api/users/" in content
        assert "/api/posts/" in content
        assert "/ai/schema" in content
        assert "/health" in content
