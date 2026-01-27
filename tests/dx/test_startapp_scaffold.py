"""
Tests for `aksara startapp` CLI command.
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from aksara.cli.main import cli


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    tmp = tempfile.mkdtemp()
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


class TestStartappCommand:
    """Tests for the startapp CLI command."""
    
    def test_startapp_creates_app_directory(self, temp_dir):
        """startapp should create app directory."""
        runner = CliRunner()
        result = runner.invoke(cli, ["startapp", "blog", "-d", temp_dir])
        
        assert result.exit_code == 0
        app_path = Path(temp_dir) / "blog"
        assert app_path.exists()
        assert app_path.is_dir()
    
    def test_startapp_creates_init_file(self, temp_dir):
        """startapp should create __init__.py file."""
        runner = CliRunner()
        result = runner.invoke(cli, ["startapp", "users", "-d", temp_dir])
        
        assert result.exit_code == 0
        init_file = Path(temp_dir) / "users" / "__init__.py"
        assert init_file.exists()
    
    def test_startapp_creates_models_file(self, temp_dir):
        """startapp should create models.py file."""
        runner = CliRunner()
        result = runner.invoke(cli, ["startapp", "orders", "-d", temp_dir])
        
        assert result.exit_code == 0
        models_file = Path(temp_dir) / "orders" / "models.py"
        assert models_file.exists()
        
        content = models_file.read_text()
        assert "from aksara import Model, fields" in content
        assert "'orders'" in content  # App name in template
    
    def test_startapp_creates_views_file(self, temp_dir):
        """startapp should create views.py file."""
        runner = CliRunner()
        result = runner.invoke(cli, ["startapp", "products", "-d", temp_dir])
        
        assert result.exit_code == 0
        views_file = Path(temp_dir) / "products" / "views.py"
        assert views_file.exists()
        
        content = views_file.read_text()
        assert "from aksara import ModelViewSet" in content
        assert "'products'" in content  # App name in template
    
    def test_startapp_creates_serializers_file(self, temp_dir):
        """startapp should create serializers.py file."""
        runner = CliRunner()
        result = runner.invoke(cli, ["startapp", "catalog", "-d", temp_dir])
        
        assert result.exit_code == 0
        serializers_file = Path(temp_dir) / "catalog" / "serializers.py"
        assert serializers_file.exists()
        
        content = serializers_file.read_text()
        assert "from aksara import ModelSerializer" in content
        assert "'catalog'" in content  # App name in template
    
    def test_startapp_invalid_name(self, temp_dir):
        """startapp should reject invalid Python identifiers."""
        runner = CliRunner()
        result = runner.invoke(cli, ["startapp", "my-app", "-d", temp_dir])
        
        assert result.exit_code == 0  # CLI returns 0 but shows error
        assert "Invalid app name" in result.output
        
        # App should not be created
        app_path = Path(temp_dir) / "my-app"
        assert not app_path.exists()
    
    def test_startapp_numeric_start(self, temp_dir):
        """startapp should reject names starting with numbers."""
        runner = CliRunner()
        result = runner.invoke(cli, ["startapp", "123app", "-d", temp_dir])
        
        assert "Invalid app name" in result.output
        app_path = Path(temp_dir) / "123app"
        assert not app_path.exists()
    
    def test_startapp_existing_directory(self, temp_dir):
        """startapp should fail if directory already exists."""
        # Create the directory first
        app_path = Path(temp_dir) / "existing"
        app_path.mkdir()
        
        runner = CliRunner()
        result = runner.invoke(cli, ["startapp", "existing", "-d", temp_dir])
        
        assert "Directory already exists" in result.output
    
    def test_startapp_shows_next_steps(self, temp_dir):
        """startapp should show next steps to user."""
        runner = CliRunner()
        result = runner.invoke(cli, ["startapp", "blog", "-d", temp_dir])
        
        assert result.exit_code == 0
        assert "Next steps" in result.output
        assert "settings.apps" in result.output
        assert '"blog"' in result.output
    
    def test_startapp_underscore_name(self, temp_dir):
        """startapp should accept underscored names."""
        runner = CliRunner()
        result = runner.invoke(cli, ["startapp", "my_awesome_app", "-d", temp_dir])
        
        assert result.exit_code == 0
        app_path = Path(temp_dir) / "my_awesome_app"
        assert app_path.exists()


class TestStartappTemplateContent:
    """Tests for the content of generated app files."""
    
    def test_models_template_has_example(self, temp_dir):
        """models.py should have example code."""
        runner = CliRunner()
        runner.invoke(cli, ["startapp", "myapp", "-d", temp_dir])
        
        models_file = Path(temp_dir) / "myapp" / "models.py"
        content = models_file.read_text()
        
        # Should have example docstring
        assert "Example:" in content
        assert "class Item(Model):" in content or "class Meta:" in content
    
    def test_views_template_has_example(self, temp_dir):
        """views.py should have example code."""
        runner = CliRunner()
        runner.invoke(cli, ["startapp", "myapp", "-d", temp_dir])
        
        views_file = Path(temp_dir) / "myapp" / "views.py"
        content = views_file.read_text()
        
        # Should have example
        assert "Example:" in content
        assert "ModelViewSet" in content
        assert "@action" in content
    
    def test_serializers_template_has_example(self, temp_dir):
        """serializers.py should have example code."""
        runner = CliRunner()
        runner.invoke(cli, ["startapp", "myapp", "-d", temp_dir])
        
        serializers_file = Path(temp_dir) / "myapp" / "serializers.py"
        content = serializers_file.read_text()
        
        # Should have example
        assert "Example:" in content
        assert "ModelSerializer" in content
