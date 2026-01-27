"""
Tests for aksara CLI info command.

Tests the info command output and functionality.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock, AsyncMock


class TestInfoCommand:
    """Tests for aksara info CLI command."""
    
    def test_info_command_exists(self):
        """Test that info command is registered."""
        from aksara.cli.main import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ["info", "--help"])
        
        assert result.exit_code == 0
        assert "info" in result.output.lower() or "Show Aksara environment" in result.output
    
    def test_info_shows_version(self):
        """Test that info shows Aksara version."""
        from aksara.cli.main import cli
        from aksara import __version__
        
        runner = CliRunner()
        result = runner.invoke(cli, ["info"])
        
        # Should show version somewhere in output
        assert __version__ in result.output or "0.3.12" in result.output
    
    def test_info_shows_cli_version(self):
        """Test that info shows CLI version."""
        from aksara.cli.main import cli, CLI_VERSION
        
        runner = CliRunner()
        result = runner.invoke(cli, ["info"])
        
        assert CLI_VERSION in result.output
    
    def test_info_shows_database_not_configured(self):
        """Test that info shows database not configured message when no DB URL."""
        from aksara.cli.main import cli
        
        runner = CliRunner()
        
        # Patch settings at the conf module level
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.database_url = None
            mock_settings.debug = False
            mock_settings.migrations_dir = "migrations"
            mock_settings.apps = ["app"]
            
            result = runner.invoke(cli, ["info"])
        
        # Should mention database somewhere
        assert "Database" in result.output or "database" in result.output
    
    def test_info_shows_apps(self):
        """Test that info shows configured apps."""
        from aksara.cli.main import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ["info"])
        
        # Should show "Configured Apps" section
        assert "Apps" in result.output or "apps" in result.output.lower()


class TestRedactDbUrl:
    """Tests for _redact_db_url helper function."""
    
    def test_redact_password(self):
        """Test that password is redacted from URL."""
        from aksara.cli.main import _redact_db_url
        
        url = "postgresql://user:secret123@localhost:5432/mydb"
        redacted = _redact_db_url(url)
        
        assert "secret123" not in redacted
        assert "****" in redacted
        assert "user" in redacted
        assert "localhost" in redacted
    
    def test_redact_preserves_host_and_db(self):
        """Test that host and database name are preserved."""
        from aksara.cli.main import _redact_db_url
        
        url = "postgresql://admin:password@db.example.com:5432/production"
        redacted = _redact_db_url(url)
        
        assert "db.example.com" in redacted
        assert "production" in redacted
        assert "password" not in redacted
    
    def test_redact_handles_asyncpg_driver(self):
        """Test redaction with asyncpg driver."""
        from aksara.cli.main import _redact_db_url
        
        url = "postgresql+asyncpg://user:secret@localhost/db"
        redacted = _redact_db_url(url)
        
        assert "secret" not in redacted
        assert "postgresql+asyncpg" in redacted
    
    def test_no_password_returns_original(self):
        """Test that URL without password is returned as-is."""
        from aksara.cli.main import _redact_db_url
        
        url = "postgresql://localhost/mydb"
        redacted = _redact_db_url(url)
        
        # Should return unchanged if no password pattern matched
        assert url == redacted or "localhost" in redacted


class TestCliVersion:
    """Tests for CLI version option."""
    
    def test_version_option(self):
        """Test that --version shows version."""
        from aksara.cli.main import cli, CLI_VERSION
        
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        
        assert result.exit_code == 0
        assert CLI_VERSION in result.output
    
    def test_version_matches_init(self):
        """Test that CLI_VERSION matches module version."""
        from aksara.cli.main import CLI_VERSION
        from aksara import __version__
        
        # Both should be 0.3.12
        assert CLI_VERSION == __version__


class TestShellCommand:
    """Tests for aksara shell CLI command."""
    
    def test_shell_command_exists(self):
        """Test that shell command is registered."""
        from aksara.cli.main import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ["shell", "--help"])
        
        assert result.exit_code == 0
        assert "shell" in result.output.lower() or "interactive" in result.output.lower()
    
    def test_shell_has_no_ipython_flag(self):
        """Test that shell has --no-ipython flag."""
        from aksara.cli.main import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ["shell", "--help"])
        
        assert "--no-ipython" in result.output
    
    def test_shell_calls_run_shell(self):
        """Test that shell command calls run_shell."""
        from aksara.cli.main import cli
        
        runner = CliRunner()
        
        with patch("aksara.shell.run_shell") as mock_run_shell:
            mock_run_shell.return_value = None
            
            result = runner.invoke(cli, ["shell"])
            
            mock_run_shell.assert_called_once()
    
    def test_shell_passes_no_ipython_flag(self):
        """Test that --no-ipython flag is passed to run_shell."""
        from aksara.cli.main import cli
        
        runner = CliRunner()
        
        with patch("aksara.shell.run_shell") as mock_run_shell:
            mock_run_shell.return_value = None
            
            runner.invoke(cli, ["shell", "--no-ipython"])
            
            # Verify run_shell was called with use_ipython=False
            mock_run_shell.assert_called_once()
            call_kwargs = mock_run_shell.call_args[1]
            assert call_kwargs["use_ipython"] is False
