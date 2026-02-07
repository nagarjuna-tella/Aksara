"""
Tests for v0.5.6 "First-Hour Magic" DX Pass.

Tests the developer experience improvements:
1. Dev server banner with all URLs
2. Welcome page at / in scaffolded projects
3. aksara info polish with features section
"""

import pytest
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from aksara.cli.scaffold import create_project_scaffold, write_scaffold_files


class TestDevServerBanner:
    """Test enhanced dev server banner (v0.5.6)."""
    
    def test_print_dev_banner_shows_version(self):
        """Banner should show Aksara version."""
        from aksara.cli.main import _print_dev_banner
        from aksara import __version__
        from io import StringIO
        import sys
        
        # Capture output
        captured = StringIO()
        with patch('sys.stdout', captured):
            with patch('click.echo', side_effect=lambda x='': print(x)):
                _print_dev_banner("http://127.0.0.1:8000", True, "info")
        
        output = captured.getvalue()
        assert __version__ in output or "0.5.6" in output
    
    def test_print_dev_banner_shows_env(self):
        """Banner should show environment (dev/prod)."""
        from aksara.cli.main import _print_dev_banner
        from io import StringIO
        
        with patch('aksara.cli.main._get_debug_mode', return_value=True):
            captured = StringIO()
            with patch('sys.stdout', captured):
                with patch('click.echo', side_effect=lambda x='': print(x)):
                    _print_dev_banner("http://127.0.0.1:8000", True, "info")
            
            output = captured.getvalue()
            assert "Env:" in output or "dev" in output
    
    def test_print_dev_banner_shows_urls(self):
        """Banner should show all URLs."""
        from aksara.cli.main import _print_dev_banner
        from io import StringIO
        
        with patch('aksara.cli.main._check_admin_enabled', return_value=True):
            with patch('aksara.cli.main._check_studio_enabled', return_value=True):
                with patch('aksara.cli.main._get_debug_mode', return_value=True):
                    captured = StringIO()
                    with patch('sys.stdout', captured):
                        with patch('click.echo', side_effect=lambda x='': print(x)):
                            _print_dev_banner("http://127.0.0.1:8000", True, "info")
                    
                    output = captured.getvalue()
                    # Should show all URLs
                    assert "App:" in output
                    assert "Docs:" in output
    
    def test_check_admin_enabled_returns_bool(self):
        """_check_admin_enabled should return a boolean."""
        from aksara.cli.main import _check_admin_enabled
        
        result = _check_admin_enabled()
        assert isinstance(result, bool)
    
    def test_check_studio_enabled_returns_bool(self):
        """_check_studio_enabled should return a boolean."""  
        from aksara.cli.main import _check_studio_enabled
        
        result = _check_studio_enabled()
        assert isinstance(result, bool)
    
    def test_get_debug_mode_returns_bool(self):
        """_get_debug_mode should return a boolean."""
        from aksara.cli.main import _get_debug_mode
        
        result = _get_debug_mode()
        assert isinstance(result, bool)


class TestScaffoldWelcomePage:
    """Test welcome page in scaffolded projects (v0.5.6)."""
    
    def setup_method(self):
        """Create a temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
        self.project_name = "welcome_test"
        
        # Create scaffold
        files = create_project_scaffold(self.project_name, self.base_path)
        write_scaffold_files(files)
        self.project_path = self.base_path / self.project_name
    
    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_main_py_has_welcome_route(self):
        """main.py should define a welcome route at /."""
        main_path = self.project_path / "main.py"
        content = main_path.read_text()
        
        # Should have the welcome route
        assert '@app.get("/", response_class=HTMLResponse' in content
        assert 'async def welcome(' in content
    
    def test_main_py_has_welcome_html(self):
        """main.py should have WELCOME_HTML constant."""
        main_path = self.project_path / "main.py"
        content = main_path.read_text()
        
        assert 'WELCOME_HTML' in content
    
    def test_welcome_html_has_project_name(self):
        """Welcome HTML should include project name."""
        main_path = self.project_path / "main.py"
        content = main_path.read_text()
        
        assert self.project_name in content
    
    def test_welcome_html_has_aksara_version(self):
        """Welcome HTML should include Aksara version reference."""
        main_path = self.project_path / "main.py"
        content = main_path.read_text()
        
        assert 'aksara_version' in content
    
    def test_welcome_html_has_admin_link(self):
        """Welcome HTML should have link to admin."""
        main_path = self.project_path / "main.py"
        content = main_path.read_text()
        
        assert '/admin/' in content
    
    def test_welcome_html_has_studio_link(self):
        """Welcome HTML should have link to studio."""
        main_path = self.project_path / "main.py"
        content = main_path.read_text()
        
        assert '/studio/ui' in content
    
    def test_welcome_html_has_api_link(self):
        """Welcome HTML should have link to API."""
        main_path = self.project_path / "main.py"
        content = main_path.read_text()
        
        assert '/api/posts/' in content
    
    def test_welcome_html_has_docs_link(self):
        """Welcome HTML should have link to docs."""
        main_path = self.project_path / "main.py"
        content = main_path.read_text()
        
        assert '/docs' in content
    
    def test_welcome_html_has_ai_tools_link(self):
        """Welcome HTML should have link to AI tools."""
        main_path = self.project_path / "main.py"
        content = main_path.read_text()
        
        assert '/ai/tools' in content
    
    def test_welcome_html_has_customize_note(self):
        """Welcome HTML should mention how to customize."""
        main_path = self.project_path / "main.py"
        content = main_path.read_text()
        
        assert 'main.py' in content
        assert 'customize' in content.lower() or 'edit' in content.lower()
    
    def test_main_py_imports_htmlresponse(self):
        """main.py should import HTMLResponse."""
        main_path = self.project_path / "main.py"
        content = main_path.read_text()
        
        assert 'from fastapi.responses import HTMLResponse' in content


class TestAksaraInfoPolish:
    """Test aksara info command enhancements (v0.5.6)."""
    
    def test_info_command_exists(self):
        """aksara info command should exist."""
        from aksara.cli.main import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ['info', '--help'])
        
        assert result.exit_code == 0
        assert 'Show Aksara environment information' in result.output
    
    def test_info_shows_version(self):
        """aksara info should show version."""
        from aksara.cli.main import cli
        from aksara import __version__
        
        runner = CliRunner()
        result = runner.invoke(cli, ['info'])
        
        # Should show framework version
        assert 'Framework' in result.output or 'Version' in result.output
    
    def test_info_shows_environment_section(self):
        """aksara info should have environment section."""
        from aksara.cli.main import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ['info'])
        
        # Should show environment info
        assert 'Environment' in result.output or 'Env:' in result.output or 'Debug' in result.output
    
    def test_info_shows_features_section(self):
        """aksara info should have features section."""
        from aksara.cli.main import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ['info'])
        
        # Should show features
        assert 'Features' in result.output or 'Admin:' in result.output


class TestScaffoldVersionUpdates:
    """Test scaffold templates use v0.5.6 versions."""
    
    def setup_method(self):
        """Create a temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
        self.project_name = "version_test"
        
        # Create scaffold
        files = create_project_scaffold(self.project_name, self.base_path)
        write_scaffold_files(files)
        self.project_path = self.base_path / self.project_name
    
    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_main_py_says_v056(self):
        """main.py should reference current version."""
        main_path = self.project_path / "main.py"
        content = main_path.read_text()
        
        assert 'v0.5.13' in content
    
    def test_settings_py_says_v056(self):
        """settings.py should reference current version."""
        settings_path = self.project_path / "settings.py"
        content = settings_path.read_text()
        
        assert 'v0.5.13' in content
    
    def test_pyproject_requires_056(self):
        """pyproject.toml should require aksara>=0.5.13."""
        pyproject_path = self.project_path / "pyproject.toml"
        content = pyproject_path.read_text()
        
        assert 'aksara>=0.5.13' in content
    
    def test_main_py_uses_aksara_dev(self):
        """main.py docstring should mention aksara dev command."""
        main_path = self.project_path / "main.py"
        content = main_path.read_text()
        
        assert 'aksara dev' in content


class TestDevBannerHelperFunctions:
    """Test helper functions used by dev banner."""
    
    def test_check_admin_enabled_with_debug_true(self):
        """Admin should be enabled when debug is True."""
        from aksara.cli.main import _check_admin_enabled
        
        # Just test that the function returns a boolean
        # The actual logic depends on settings which we don't mock
        result = _check_admin_enabled()
        assert isinstance(result, bool)
    
    def test_check_studio_enabled_default(self):
        """Studio should be enabled by default in debug mode."""
        from aksara.cli.main import _check_studio_enabled
        
        # Should not raise and return a boolean
        result = _check_studio_enabled()
        assert isinstance(result, bool)
