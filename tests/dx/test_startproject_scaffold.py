"""
Tests for vidyut startproject scaffold generation.

Tests that:
- startproject creates the correct directory structure
- All required files are generated
- Generated files have correct content
- main.py imports Vidyut, not FastAPI
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from vidyut.cli.scaffold import (
    create_project_scaffold,
    write_scaffold_files,
    get_main_py_template,
    get_settings_py_template,
    get_models_template,
    get_views_template,
    get_urls_template,
    get_serializers_template,
    get_env_template,
    get_readme_template,
    get_requirements_template,
)


class TestScaffoldTemplates:
    """Test individual template generation."""
    
    def test_main_py_template_imports_vidyut(self):
        """Main.py should import Vidyut, not FastAPI directly."""
        content = get_main_py_template("testproject")
        
        # Should import from vidyut
        assert "from vidyut import Vidyut" in content
        
        # Should NOT import FastAPI directly
        assert "from fastapi import" not in content
        assert "import fastapi" not in content.lower()
        
        # Should create Vidyut app
        assert "app = Vidyut(" in content
    
    def test_main_py_template_has_health_endpoint(self):
        """Main.py should include a health check endpoint."""
        content = get_main_py_template("testproject")
        assert '@app.get("/health")' in content
        assert "async def health_check" in content
    
    def test_main_py_template_uses_urls_register(self):
        """Main.py should register routes via urls.register_routes."""
        content = get_main_py_template("testproject")
        assert "from app.urls import register_routes" in content
        assert "register_routes(app)" in content
    
    def test_settings_py_template(self):
        """Settings.py should extend VidyutSettings."""
        content = get_settings_py_template("testproject")
        
        assert "from vidyut.conf import Settings as VidyutSettings" in content
        assert "class Settings(VidyutSettings):" in content
        assert "settings = Settings()" in content
    
    def test_models_template_is_empty_with_example(self):
        """Models.py should be empty with example in comments."""
        content = get_models_template("testproject")
        
        assert "from vidyut import Model, fields" in content
        # Should have example in docstring/comments, not actual models
        assert "# Define your models here" in content
        assert "Example:" in content
    
    def test_views_template_is_empty_with_example(self):
        """Views.py should be empty with example in comments."""
        content = get_views_template("testproject")
        
        assert "from vidyut import" in content
        assert "ModelViewSet" in content
        assert "action" in content
        # Should have example in docstring, not actual viewsets
        assert "# Define your ViewSets here" in content
        assert "Example:" in content
    
    def test_urls_template_has_register_routes(self):
        """Urls.py should include register_routes function."""
        content = get_urls_template("testproject")
        
        assert "from vidyut import" in content
        assert "include_viewset" in content
        assert "urlpatterns = [" in content
        assert "def register_routes(app):" in content
    
    def test_urls_template_has_empty_urlpatterns(self):
        """Urls.py should have empty urlpatterns list."""
        content = get_urls_template("testproject")
        
        # Should have commented out example
        assert "# Add your ViewSets here" in content
    
    def test_serializers_template_is_empty_with_example(self):
        """Serializers.py should be empty with example in comments."""
        content = get_serializers_template("testproject")
        
        assert "from vidyut import ModelSerializer" in content
        # Should have example in docstring, not actual serializers
        assert "# Define your serializers here" in content
        assert "Example:" in content
    
    def test_env_template(self):
        """Env template should have all required variables."""
        content = get_env_template("testproject")
        
        assert "DATABASE_URL=" in content
        assert "VIDYUT_DEBUG=" in content
        assert "VIDYUT_LOG_LEVEL=" in content
        assert "VIDYUT_APP_TITLE=" in content
        assert "VIDYUT_APP_VERSION=" in content
    
    def test_readme_template(self):
        """README should include project name and instructions."""
        content = get_readme_template("testproject")
        
        assert "# testproject" in content
        assert "vidyut makemigrations" in content
        assert "vidyut migrate" in content
        assert "vidyut run main:app" in content
    
    def test_requirements_template(self):
        """Requirements should include vidyut and uvicorn."""
        content = get_requirements_template()
        
        assert "vidyut" in content
        assert "uvicorn" in content


class TestScaffoldCreation:
    """Test full scaffold creation."""
    
    def setup_method(self):
        """Create a temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_project_scaffold_returns_files(self):
        """create_project_scaffold should return dict of files."""
        files = create_project_scaffold("myproject", self.base_path)
        
        assert isinstance(files, dict)
        assert len(files) > 0
        
        # Check key files exist
        file_names = [str(p) for p in files.keys()]
        assert any("main.py" in f for f in file_names)
        assert any("settings.py" in f for f in file_names)
        assert any("models.py" in f for f in file_names)
        assert any("views.py" in f for f in file_names)
        assert any("urls.py" in f for f in file_names)
        assert any("serializers.py" in f for f in file_names)
    
    def test_write_scaffold_files_creates_structure(self):
        """write_scaffold_files should create all files and directories."""
        files = create_project_scaffold("myproject", self.base_path)
        write_scaffold_files(files)
        
        project_path = self.base_path / "myproject"
        
        # Check project directory exists
        assert project_path.exists()
        assert project_path.is_dir()
        
        # Check main files
        assert (project_path / "main.py").exists()
        assert (project_path / "settings.py").exists()
        assert (project_path / ".env").exists()
        assert (project_path / "README.md").exists()
        assert (project_path / "requirements.txt").exists()
        
        # Check app directory
        assert (project_path / "app").is_dir()
        assert (project_path / "app" / "__init__.py").exists()
        assert (project_path / "app" / "models.py").exists()
        assert (project_path / "app" / "views.py").exists()
        assert (project_path / "app" / "urls.py").exists()
        assert (project_path / "app" / "serializers.py").exists()
        
        # Check migrations directory
        assert (project_path / "migrations").is_dir()
        assert (project_path / "migrations" / "__init__.py").exists()
    
    def test_generated_main_imports_vidyut_not_fastapi(self):
        """Generated main.py should import Vidyut, not FastAPI."""
        files = create_project_scaffold("myproject", self.base_path)
        write_scaffold_files(files)
        
        main_path = self.base_path / "myproject" / "main.py"
        content = main_path.read_text()
        
        # Should import Vidyut
        assert "from vidyut import Vidyut" in content
        
        # Should NOT import FastAPI
        assert "from fastapi import" not in content
        assert "import fastapi" not in content.lower()
    
    def test_generated_files_have_project_name(self):
        """Generated files should include project name."""
        project_name = "blogapi"
        files = create_project_scaffold(project_name, self.base_path)
        write_scaffold_files(files)
        
        # Check main.py
        main_path = self.base_path / project_name / "main.py"
        main_content = main_path.read_text()
        assert project_name in main_content
        
        # Check README
        readme_path = self.base_path / project_name / "README.md"
        readme_content = readme_path.read_text()
        assert f"# {project_name}" in readme_content
        
        # Check .env
        env_path = self.base_path / project_name / ".env"
        env_content = env_path.read_text()
        assert project_name in env_content


class TestScaffoldValidation:
    """Test scaffold validation and edge cases."""
    
    def setup_method(self):
        """Create a temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_scaffold_creates_valid_python_files(self):
        """All generated .py files should be syntactically valid."""
        files = create_project_scaffold("testproject", self.base_path)
        write_scaffold_files(files)
        
        project_path = self.base_path / "testproject"
        
        python_files = list(project_path.rglob("*.py"))
        assert len(python_files) > 0
        
        for py_file in python_files:
            content = py_file.read_text()
            # This will raise SyntaxError if invalid
            compile(content, str(py_file), "exec")
    
    def test_scaffold_with_underscore_name(self):
        """Scaffold should work with underscore project names."""
        files = create_project_scaffold("my_blog_api", self.base_path)
        write_scaffold_files(files)
        
        project_path = self.base_path / "my_blog_api"
        assert project_path.exists()
        assert (project_path / "main.py").exists()
    
    def test_scaffold_env_example_exists(self):
        """Scaffold should create both .env and .env.example."""
        files = create_project_scaffold("testproject", self.base_path)
        write_scaffold_files(files)
        
        project_path = self.base_path / "testproject"
        assert (project_path / ".env").exists()
        assert (project_path / ".env.example").exists()
    
    def test_scaffold_gitignore_exists(self):
        """Scaffold should create .gitignore."""
        files = create_project_scaffold("testproject", self.base_path)
        write_scaffold_files(files)
        
        project_path = self.base_path / "testproject"
        gitignore = project_path / ".gitignore"
        assert gitignore.exists()
        
        content = gitignore.read_text()
        assert "__pycache__" in content
        assert ".env" in content
        assert ".venv" in content


class TestScaffoldViewSetIntegration:
    """Test that generated ViewSets templates are properly structured."""
    
    def test_views_has_example_with_custom_actions(self):
        """Generated views should have example with @action decorated methods."""
        content = get_views_template("testproject")
        
        # Check for action examples in docstring/comments
        assert "@action" in content
        assert "Example:" in content
        assert "detail=True" in content or "detail=False" in content
    
    def test_urls_has_register_routes(self):
        """register_routes in urls.py should use include_viewset."""
        content = get_urls_template("testproject")
        
        assert "include_viewset(app, viewset)" in content
        # Example viewsets should be in comments
        assert "# UserViewSet" in content or "UserViewSet" in content
    
    def test_urls_has_urlpatterns(self):
        """urls.py should have Django-style urlpatterns."""
        content = get_urls_template("testproject")
        
        assert "urlpatterns = [" in content
        # Example should be commented out
        assert "# Add your ViewSets here" in content


class TestScaffoldMigrationsReady:
    """Test that scaffold is ready for migrations."""
    
    def setup_method(self):
        """Create a temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_migrations_directory_exists(self):
        """Migrations directory should be created."""
        files = create_project_scaffold("testproject", self.base_path)
        write_scaffold_files(files)
        
        migrations_dir = self.base_path / "testproject" / "migrations"
        assert migrations_dir.is_dir()
        assert (migrations_dir / "__init__.py").exists()
    
    def test_no_get_create_table_sql_in_main(self):
        """Main.py should not use get_create_table_sql."""
        content = get_main_py_template("testproject")
        assert "get_create_table_sql" not in content
        assert "CREATE TABLE" not in content
