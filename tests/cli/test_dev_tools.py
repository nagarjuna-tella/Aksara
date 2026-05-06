"""
Tests for v0.3.18 Developer Workflow CLI Commands.

Tests the dev tool commands: format, lint, typecheck, test, precommit.
"""
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from aksara.cli.main import (
    cli,
    format as format_cmd,
    lint,
    typecheck,
    precommit,
    precommit_init,
    precommit_run,
    _run_tool,
    PRECOMMIT_CONFIG,
)


# =============================================================================
# Test _run_tool helper
# =============================================================================

class TestRunToolHelper:
    """Tests for the _run_tool helper function."""
    
    @patch("subprocess.run")
    def test_run_tool_success(self, mock_run):
        """Test successful tool execution."""
        mock_run.return_value = MagicMock(returncode=0)
        
        exit_code = _run_tool("Black", "black", ["."], "black")
        
        assert exit_code == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert sys.executable == args[0]
        assert "-m" == args[1]
        assert "black" == args[2]
        assert "." == args[3]
    
    @patch("subprocess.run")
    def test_run_tool_failure(self, mock_run):
        """Test tool execution with non-zero exit code."""
        mock_run.return_value = MagicMock(returncode=1)
        
        exit_code = _run_tool("Black", "black", ["--check", "."], "black")
        
        assert exit_code == 1
    
    @patch("subprocess.run")
    def test_run_tool_not_installed(self, mock_run, capsys):
        """Test graceful handling when tool is not installed."""
        mock_run.side_effect = FileNotFoundError("No such file or directory")
        
        exit_code = _run_tool("Black", "black", ["."], "black")
        
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Black is not installed" in captured.out
        assert "pip install aksara[dev]" in captured.out
        assert "pip install black" in captured.out


# =============================================================================
# Test format command
# =============================================================================

class TestFormatCommand:
    """Tests for the format command."""
    
    @patch("aksara.cli.main._run_tool")
    def test_format_default_path(self, mock_run_tool):
        """Test format command with default path."""
        mock_run_tool.return_value = 0
        
        runner = CliRunner()
        result = runner.invoke(cli, ["format"])
        
        # Check _run_tool was called with correct arguments
        mock_run_tool.assert_called_once()
        args = mock_run_tool.call_args
        assert args[0][0] == "Black"  # tool_name
        assert args[0][1] == "black"  # module
        assert "." in args[0][2]  # args
    
    @patch("aksara.cli.main._run_tool")
    def test_format_custom_path(self, mock_run_tool):
        """Test format command with custom path."""
        mock_run_tool.return_value = 0
        
        runner = CliRunner()
        result = runner.invoke(cli, ["format", "src/"])
        
        args = mock_run_tool.call_args[0][2]
        assert "src/" in args
    
    @patch("aksara.cli.main._run_tool")
    def test_format_check_mode(self, mock_run_tool):
        """Test format command with --check flag."""
        mock_run_tool.return_value = 0
        
        runner = CliRunner()
        result = runner.invoke(cli, ["format", "--check"])
        
        args = mock_run_tool.call_args[0][2]
        assert "--check" in args


# =============================================================================
# Test lint command
# =============================================================================

class TestLintCommand:
    """Tests for the lint command."""
    
    @patch("aksara.cli.main._run_tool")
    def test_lint_default(self, mock_run_tool):
        """Test lint command with defaults."""
        mock_run_tool.return_value = 0
        
        runner = CliRunner()
        result = runner.invoke(cli, ["lint"])
        
        args = mock_run_tool.call_args
        assert args[0][0] == "Ruff"
        assert args[0][1] == "ruff"
        assert "check" in args[0][2]
        assert "." in args[0][2]
    
    @patch("aksara.cli.main._run_tool")
    def test_lint_with_fix(self, mock_run_tool):
        """Test lint command with --fix flag."""
        mock_run_tool.return_value = 0
        
        runner = CliRunner()
        result = runner.invoke(cli, ["lint", "--fix"])
        
        args = mock_run_tool.call_args[0][2]
        assert "--fix" in args


# =============================================================================
# Test typecheck command
# =============================================================================

class TestTypecheckCommand:
    """Tests for the typecheck command."""
    
    @patch("aksara.cli.main._run_tool")
    def test_typecheck_default(self, mock_run_tool):
        """Test typecheck command with defaults."""
        mock_run_tool.return_value = 0
        
        runner = CliRunner()
        result = runner.invoke(cli, ["typecheck"])
        
        args = mock_run_tool.call_args
        assert args[0][0] == "mypy"
        assert args[0][1] == "mypy"
        assert "." in args[0][2]
    
    @patch("aksara.cli.main._run_tool")
    def test_typecheck_strict(self, mock_run_tool):
        """Test typecheck command with --strict flag."""
        mock_run_tool.return_value = 0
        
        runner = CliRunner()
        result = runner.invoke(cli, ["typecheck", "--strict"])
        
        args = mock_run_tool.call_args[0][2]
        assert "--strict" in args


# =============================================================================
# Test test command
# =============================================================================

class TestTestCommand:
    """Tests for the test command."""
    
    @patch("aksara.cli.main._run_tool")
    def test_test_default(self, mock_run_tool):
        """Test test command with no args."""
        mock_run_tool.return_value = 0
        
        runner = CliRunner()
        result = runner.invoke(cli, ["test"])
        
        args = mock_run_tool.call_args
        assert args[0][0] == "pytest"
        assert args[0][1] == "pytest"
    
    @patch("aksara.cli.main._run_tool")
    def test_test_with_args(self, mock_run_tool):
        """Test test command passes through arguments."""
        mock_run_tool.return_value = 0
        
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "-v", "--tb=short", "tests/"])
        
        args = mock_run_tool.call_args[0][2]
        assert "-v" in args
        assert "--tb=short" in args
        assert "tests/" in args


# =============================================================================
# Test precommit init command
# =============================================================================

class TestPrecommitInitCommand:
    """Tests for the precommit init command."""
    
    def test_precommit_init_creates_file(self, tmp_path):
        """Test that precommit init creates .pre-commit-config.yaml."""
        runner = CliRunner()
        
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["precommit", "init"])
            
            assert result.exit_code == 0
            assert "Created .pre-commit-config.yaml" in result.output
            
            # Check file was created
            config_path = Path(".pre-commit-config.yaml")
            assert config_path.exists()
            
            # Check content
            content = config_path.read_text()
            assert "ruff" in content
            assert "black" in content
            assert "mypy" in content
            assert "pre-commit-hooks" in content
    
    def test_precommit_init_does_not_overwrite(self, tmp_path):
        """Test that precommit init does not overwrite existing file."""
        runner = CliRunner()
        
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create existing file
            existing_content = "# My custom config\n"
            Path(".pre-commit-config.yaml").write_text(existing_content)
            
            result = runner.invoke(cli, ["precommit", "init"])
            
            assert result.exit_code == 0
            assert "already exists" in result.output
            
            # Check content was NOT overwritten
            content = Path(".pre-commit-config.yaml").read_text()
            assert content == existing_content
    
    def test_precommit_init_shows_next_steps(self, tmp_path):
        """Test that precommit init shows next steps."""
        runner = CliRunner()
        
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["precommit", "init"])
            
            assert "pre-commit install" in result.output
            assert "aksara precommit run" in result.output


# =============================================================================
# Test precommit run command
# =============================================================================

class TestPrecommitRunCommand:
    """Tests for the precommit run command."""
    
    @patch("aksara.cli.main._run_tool")
    def test_precommit_run_default(self, mock_run_tool):
        """Test precommit run command."""
        mock_run_tool.return_value = 0
        
        runner = CliRunner()
        result = runner.invoke(cli, ["precommit", "run"])
        
        args = mock_run_tool.call_args
        assert args[0][0] == "pre-commit"
        assert args[0][1] == "pre_commit"
        assert "run" in args[0][2]
        assert "--all-files" in args[0][2]
    
    @patch("aksara.cli.main._run_tool")
    def test_precommit_run_propagates_exit_code(self, mock_run_tool):
        """Test precommit run propagates exit code from tool."""
        mock_run_tool.return_value = 1
        
        runner = CliRunner()
        result = runner.invoke(cli, ["precommit", "run"])
        
        # sys.exit(1) is called, which translates to exit_code=1
        assert result.exit_code == 1


# =============================================================================
# Test precommit group
# =============================================================================

class TestPrecommitGroup:
    """Tests for the precommit command group."""
    
    def test_precommit_help(self):
        """Test precommit group has help text."""
        runner = CliRunner()
        result = runner.invoke(cli, ["precommit", "--help"])
        
        assert result.exit_code == 0
        assert "init" in result.output
        assert "run" in result.output


# =============================================================================
# Test CLI help text
# =============================================================================

class TestCLIHelp:
    """Tests for CLI help output."""
    
    def test_cli_help_shows_dev_commands(self):
        """Test that main CLI help shows new dev commands."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        
        assert result.exit_code == 0
        assert "format" in result.output
        assert "lint" in result.output
        assert "typecheck" in result.output
        assert "test" in result.output
        assert "precommit" in result.output
    
    def test_format_help(self):
        """Test format command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["format", "--help"])
        
        assert result.exit_code == 0
        assert "Black" in result.output
        assert "--check" in result.output
    
    def test_lint_help(self):
        """Test lint command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["lint", "--help"])
        
        assert result.exit_code == 0
        assert "Ruff" in result.output
        assert "--fix" in result.output
    
    def test_typecheck_help(self):
        """Test typecheck command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["typecheck", "--help"])
        
        assert result.exit_code == 0
        assert "mypy" in result.output
        assert "--strict" in result.output
    
    def test_test_help(self):
        """Test test command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--help"])
        
        assert result.exit_code == 0
        assert "pytest" in result.output


# =============================================================================
# Test PRECOMMIT_CONFIG constant
# =============================================================================

class TestPrecommitConfigTemplate:
    """Tests for the pre-commit config template."""
    
    def test_config_has_required_hooks(self):
        """Test that config has all required hooks."""
        assert "ruff" in PRECOMMIT_CONFIG
        assert "black" in PRECOMMIT_CONFIG
        assert "mypy" in PRECOMMIT_CONFIG
        assert "check-added-large-files" in PRECOMMIT_CONFIG
        assert "check-merge-conflict" in PRECOMMIT_CONFIG
        assert "check-yaml" in PRECOMMIT_CONFIG
    
    def test_config_has_repos_structure(self):
        """Test that config has repos structure."""
        assert "repos:" in PRECOMMIT_CONFIG
        assert "- repo:" in PRECOMMIT_CONFIG
        assert "hooks:" in PRECOMMIT_CONFIG


# =============================================================================
# Test startproject scaffolding includes dev files
# =============================================================================

class TestStartprojectDevFiles:
    """Tests for startproject scaffolding with dev files."""
    
    def test_startproject_creates_precommit_config(self, tmp_path):
        """Test that startproject creates .pre-commit-config.yaml."""
        runner = CliRunner()
        
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["startproject", "myproject"])
            
            assert result.exit_code == 0
            
            config_path = Path("myproject/.pre-commit-config.yaml")
            assert config_path.exists()
            
            content = config_path.read_text()
            assert "ruff" in content
            assert "black" in content
            assert "mypy" in content
    
    def test_startproject_creates_editorconfig(self, tmp_path):
        """Test that startproject creates .editorconfig."""
        runner = CliRunner()
        
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["startproject", "myproject"])
            
            assert result.exit_code == 0
            
            config_path = Path("myproject/.editorconfig")
            assert config_path.exists()
            
            content = config_path.read_text()
            assert "indent_style = space" in content
            assert "indent_size = 4" in content
    
    def test_startproject_pyproject_has_dev_tools(self, tmp_path):
        """Test that startproject pyproject.toml has dev tool configs."""
        runner = CliRunner()
        
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["startproject", "myproject"])
            
            assert result.exit_code == 0
            
            pyproject_path = Path("myproject/pyproject.toml")
            assert pyproject_path.exists()
            
            content = pyproject_path.read_text()
            
            # Check dev dependencies
            assert "black>=24.0.0" in content
            assert "ruff>=0.5.0" in content
            assert "mypy>=1.8.0" in content
            assert "pre-commit>=3.6.0" in content
            
            # Check tool configs
            assert "[tool.black]" in content
            assert "[tool.ruff]" in content
            assert "[tool.mypy]" in content
    
    def test_startproject_shows_dev_instructions(self, tmp_path):
        """Test that startproject shows dev tool instructions."""
        runner = CliRunner()
        
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["startproject", "myproject"])
            
            assert result.exit_code == 0
            assert "pip install -e" in result.output
            # v0.5.5: Shows what's included instead of pre-commit instructions
            assert "What's included" in result.output
    
    def test_startproject_creates_pyproject_toml(self, tmp_path):
        """Test that startproject creates pyproject.toml."""
        runner = CliRunner()
        
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["startproject", "myproject"])
            
            assert result.exit_code == 0
            assert Path("myproject/pyproject.toml").exists()

    def test_startproject_app_templates_are_neutral(self, tmp_path):
        """Test that startproject does not force a live Post app scaffold."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["startproject", "myproject"])

            assert result.exit_code == 0

            models_content = Path("myproject/app/models.py").read_text()
            admin_content = Path("myproject/app/admin.py").read_text()
            serializers_content = Path("myproject/app/serializers.py").read_text()
            views_content = Path("myproject/app/views.py").read_text()
            urls_content = Path("myproject/app/urls.py").read_text()

            assert "\nclass Post(Model):" not in models_content
            assert "# class Post(Model):" in models_content
            assert "class User(Model):" not in models_content
            assert "class Comment(Model):" not in models_content
            assert "aksara.contrib.auth.User" in models_content

            assert "\nfrom .models import Post\n" not in admin_content
            assert "\nsite.register(Post, PostAdmin)\n" not in admin_content
            assert "# class PostAdmin(ModelAdmin):" in admin_content

            assert "\nfrom .models import Post\n" not in serializers_content
            assert "\nclass PostSerializer(ModelSerializer):" not in serializers_content
            assert "# class PostSerializer(ModelSerializer):" in serializers_content

            assert "\nfrom .models import Post\n" not in views_content
            assert "\nclass PostViewSet(ModelViewSet):" not in views_content
            assert "# class PostViewSet(ModelViewSet):" in views_content

            assert "\nfrom .views import PostViewSet\n" not in urls_content
            assert "# from .views import PostViewSet" in urls_content
            assert "# PostViewSet," in urls_content
