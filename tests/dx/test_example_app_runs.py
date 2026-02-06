"""
Tests for example app running with the new scaffold structure.

Tests that a generated project:
- Can be imported without errors
- Has proper template structure with examples in comments
- Has working health check
- Templates are Django-style (empty with documentation)
"""

import pytest
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from aksara.cli.scaffold import create_project_scaffold, write_scaffold_files


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
        """app.models should be importable (empty template)."""
        import importlib.util
        
        models_path = self.project_path / "app" / "models.py"
        spec = importlib.util.spec_from_file_location("app.models", models_path)
        models = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(models)
        
        # Empty template should import successfully
        assert spec is not None
    
    def test_app_serializers_can_be_imported(self):
        """app.serializers should be importable (empty template)."""
        import importlib.util
        
        # Import serializers (empty template)
        serializers_path = self.project_path / "app" / "serializers.py"
        spec = importlib.util.spec_from_file_location("app.serializers", serializers_path)
        serializers = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(serializers)
        
        # Empty template should import successfully
        assert spec is not None
    
    def test_settings_can_be_imported(self):
        """settings.py should be syntactically valid Python."""
        settings_path = self.project_path / "settings.py"
        content = settings_path.read_text()
        
        # Verify syntax is valid
        compile(content, str(settings_path), "exec")
        
        # Verify structure
        assert "class Settings" in content
        assert "settings = Settings()" in content


class TestGeneratedAppStructure:
    """Test structural aspects of the generated app (Django-style empty templates)."""
    
    def setup_method(self):
        """Create a temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_models_use_aksara_imports(self):
        """Models should import from Aksara with working Post model."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        models_path = self.base_path / "testapp" / "app" / "models.py"
        content = models_path.read_text()
        
        assert "from aksara import Model, fields" in content
        # v0.5.5: Should have working Post model
        assert "class Post(Model):" in content
    
    def test_views_use_aksara_viewset(self):
        """Views should import Aksara ModelViewSet with working PostViewSet."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        views_path = self.base_path / "testapp" / "app" / "views.py"
        content = views_path.read_text()
        
        assert "from aksara import" in content
        assert "ModelViewSet" in content
        # v0.5.5: Should have working PostViewSet
        assert "class PostViewSet(ModelViewSet):" in content
    
    def test_serializers_use_aksara_serializer(self):
        """Serializers should import Aksara ModelSerializer with PostSerializer."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        serializers_path = self.base_path / "testapp" / "app" / "serializers.py"
        content = serializers_path.read_text()
        
        assert "from aksara import ModelSerializer" in content
        # v0.5.5: Should have working PostSerializer
        assert "class PostSerializer(ModelSerializer):" in content
    
    def test_main_uses_aksara_app(self):
        """Main should use Aksara app, not FastAPI."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        main_path = self.base_path / "testapp" / "main.py"
        content = main_path.read_text()
        
        assert "from aksara import Aksara" in content
        assert "app = Aksara(" in content
        assert "from fastapi import" not in content


class TestTemplatesHaveExamples:
    """Test that empty templates have proper examples in comments."""
    
    def setup_method(self):
        """Create a temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_models_template_has_working_model(self):
        """Models template should have working Post model (v0.5.5+)."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        models_path = self.base_path / "testapp" / "app" / "models.py"
        content = models_path.read_text()
        
        # Should have working Post model
        assert "class Post(Model):" in content
        assert "fields." in content  # Shows field usage
        # Should also have commented example for extending
        assert "# class User(Model):" in content  # Example for additional models
    
    def test_views_template_has_working_viewset(self):
        """Views template should have working PostViewSet with actions (v0.5.5+)."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        views_path = self.base_path / "testapp" / "app" / "views.py"
        content = views_path.read_text()
        
        # Should have working PostViewSet
        assert "class PostViewSet(ModelViewSet):" in content
        # Should show action decorator usage
        assert "@action" in content
        assert "detail=" in content
    
    def test_urls_template_has_structure(self):
        """Urls template should have proper structure for route registration."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        urls_path = self.base_path / "testapp" / "app" / "urls.py"
        content = urls_path.read_text()
        
        assert "urlpatterns = [" in content
        assert "def register_routes(app):" in content
        assert "include_viewset" in content


class TestSettingsConfiguration:
    """Test settings configuration."""
    
    def setup_method(self):
        """Create a temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_settings_extends_aksara_settings(self):
        """Settings should extend AksaraSettings."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        settings_path = self.base_path / "testapp" / "settings.py"
        content = settings_path.read_text()
        
        assert "from aksara.conf import Settings as AksaraSettings" in content
        assert "class Settings(AksaraSettings):" in content
    
    def test_env_has_required_vars(self):
        """Env file should have all required variables."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        env_path = self.base_path / "testapp" / ".env"
        content = env_path.read_text()
        
        required_vars = [
            "DATABASE_URL=",
            "AKSARA_DEBUG=",
            "AKSARA_LOG_LEVEL=",
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
        
        assert "aksara makemigrations" in content
        assert "aksara migrate" in content


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
        assert "aksara run main:app" in content
    
    def test_readme_has_api_docs_reference(self):
        """README should reference API documentation."""
        files = create_project_scaffold("testapp", self.base_path)
        write_scaffold_files(files)
        
        readme_path = self.base_path / "testapp" / "README.md"
        content = readme_path.read_text()
        
        # Should mention API docs access
        assert "/docs" in content or "swagger" in content.lower() or "api" in content.lower()
