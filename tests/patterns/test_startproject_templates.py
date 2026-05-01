"""
Tests for `aksara startproject --template` Feature

Tests the template system and CLI integration.
"""

import pytest
import tempfile
import shutil
from pathlib import Path


class TestTemplateModule:
    """Test the templates module."""
    
    def test_templates_module_importable(self):
        """Templates module should be importable."""
        from aksara.cli import templates
        assert templates is not None
    
    def test_get_available_templates(self):
        """get_available_templates should return dict of templates."""
        from aksara.cli.templates import get_available_templates
        
        templates = get_available_templates()
        assert isinstance(templates, dict)
        assert "basic" in templates
        assert "blog" in templates
        assert "crm" in templates
        assert "multitenant" in templates
    
    def test_get_template_info(self):
        """get_template_info should return template details."""
        from aksara.cli.templates import get_template_info
        
        info = get_template_info("blog")
        assert info is not None
        assert info["name"] == "blog"
        assert "description" in info
    
    def test_get_template_info_unknown(self):
        """get_template_info should return None for unknown template."""
        from aksara.cli.templates import get_template_info
        
        info = get_template_info("nonexistent")
        assert info is None
    
    def test_list_templates(self):
        """list_templates should return formatted string."""
        from aksara.cli.templates import list_templates
        
        output = list_templates()
        assert isinstance(output, str)
        assert "basic" in output
        assert "blog" in output
        assert "crm" in output
        assert "multitenant" in output
    
    def test_get_examples_path(self):
        """get_examples_path should return valid path."""
        from aksara.cli.templates import get_examples_path
        
        path = get_examples_path()
        assert isinstance(path, Path)
        # Note: Path might not exist in all test environments


class TestTemplateMetadata:
    """Test template metadata structure."""
    
    def test_basic_template_metadata(self):
        """Basic template should have correct metadata."""
        from aksara.cli.templates import TEMPLATES
        
        basic = TEMPLATES["basic"]
        assert basic["name"] == "basic"
        assert basic["source"] is None  # Uses scaffold.py
        assert "description" in basic
    
    def test_blog_template_metadata(self):
        """Blog template should have correct metadata."""
        from aksara.cli.templates import TEMPLATES
        
        blog = TEMPLATES["blog"]
        assert blog["name"] == "blog"
        assert blog["source"] == "blog"  # Copies from examples/blog
    
    def test_crm_template_metadata(self):
        """CRM template should have correct metadata."""
        from aksara.cli.templates import TEMPLATES
        
        crm = TEMPLATES["crm"]
        assert crm["name"] == "crm"
        assert crm["source"] == "crm"
    
    def test_multitenant_template_metadata(self):
        """Multitenant template should have correct metadata."""
        from aksara.cli.templates import TEMPLATES
        
        mt = TEMPLATES["multitenant"]
        assert mt["name"] == "multitenant"
        assert mt["source"] == "multitenant"


class TestCopyTemplateProject:
    """Test copy_template_project function."""
    
    def test_copy_basic_template(self):
        """Basic template should use scaffold.py."""
        from aksara.cli.templates import copy_template_project
        
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            files = copy_template_project("basic", "myproject", base_path)
            
            assert isinstance(files, dict)
            assert len(files) > 0
            
            # Check expected files
            paths = [str(p) for p in files.keys()]
            assert any("main.py" in p for p in paths)
            assert any("settings.py" in p for p in paths)
    
    def test_copy_blog_template(self):
        """Blog template should copy from examples."""
        from aksara.cli.templates import copy_template_project, get_examples_path
        
        # Skip if examples path doesn't exist
        examples = get_examples_path()
        if not (examples / "blog").exists():
            pytest.skip("Blog example not found")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            files = copy_template_project("blog", "myblog", base_path)
            
            assert isinstance(files, dict)
            assert len(files) > 0
            
            # Check expected blog files
            paths = [str(p) for p in files.keys()]
            assert any("models.py" in p for p in paths)
    
    def test_copy_unknown_template_raises(self):
        """Unknown template should raise ValueError."""
        from aksara.cli.templates import copy_template_project
        
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            with pytest.raises(ValueError, match="Unknown template"):
                copy_template_project("nonexistent", "myproject", base_path)


class TestProjectNameSubstitutions:
    """Test project name substitution in templates."""
    
    def test_apply_project_name_substitutions(self):
        """Project name should be substituted in content."""
        from aksara.cli.templates import apply_project_name_substitutions
        
        content = "# Blog Example\nDATABASE_URL=postgresql://...aksara_blog"
        result = apply_project_name_substitutions(content, "blog", "myproject")
        
        assert "myproject" in result
        assert "Blog Example" not in result
    
    def test_module_path_substitution(self):
        """Module paths should be substituted."""
        from aksara.cli.templates import apply_project_name_substitutions
        
        content = "from examples.blog.models import Post"
        result = apply_project_name_substitutions(content, "blog", "myproject")
        
        assert "from app.models import Post" in result
        assert "examples.blog" not in result

    def test_relative_imports_converted_to_absolute(self):
        """Relative imports must be rewritten as absolute imports."""
        from aksara.cli.templates import apply_project_name_substitutions

        content = (
            "from . import settings as _  # noqa: F401\n"
            "from . import models  # noqa: F401\n"
            "from .urls import register_routes\n"
            "from .settings import DATABASE_URL, DEBUG\n"
            "from .models import Post, Comment\n"
        )
        result = apply_project_name_substitutions(content, "blog", "myproject")

        assert "import settings as _  # noqa: F401" in result
        assert "import models  # noqa: F401" in result
        assert "from urls import register_routes" in result
        assert "from settings import DATABASE_URL, DEBUG" in result
        assert "from models import Post, Comment" in result
        # Ensure no relative dot imports remain
        assert "from . import" not in result
        assert "from ." not in result


class TestCLIIntegration:
    """Test CLI command integration."""
    
    def test_startproject_has_template_option(self):
        """startproject command should have --template option."""
        from click.testing import CliRunner
        from aksara.cli.main import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ["startproject", "--help"])
        
        assert result.exit_code == 0
        assert "--template" in result.output or "-t" in result.output
    
    def test_templates_list_command(self):
        """aksara templates list should work."""
        from click.testing import CliRunner
        from aksara.cli.main import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ["templates", "list"])
        
        assert result.exit_code == 0
        assert "basic" in result.output
        assert "blog" in result.output
        assert "crm" in result.output
        assert "multitenant" in result.output
    
    def test_startproject_with_unknown_template(self):
        """startproject with unknown template should show error."""
        from click.testing import CliRunner
        from aksara.cli.main import cli
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, [
                "startproject", "myproject", 
                "--template", "nonexistent"
            ])
            
            assert "Unknown template" in result.output or result.exit_code != 0
    
    def test_startproject_with_basic_template(self):
        """startproject with basic template should work."""
        from click.testing import CliRunner
        from aksara.cli.main import cli
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, [
                "startproject", "testproject",
                "--template", "basic"
            ])
            
            # Should succeed
            assert result.exit_code == 0 or "Created project" in result.output
            
            # Check files were created
            project_path = Path("testproject")
            if project_path.exists():
                assert (project_path / "main.py").exists()
                assert (project_path / "settings.py").exists()
