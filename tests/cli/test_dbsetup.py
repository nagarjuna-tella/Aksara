"""
Tests for the `aksara dbsetup` CLI command.

Covers:
- Happy path (PG reachable, DB created, .env written)
- PostgreSQL not reachable
- Database already exists
- .env already has DATABASE_URL (overwrite yes/no)
- Connection test failure (bad credentials)
- Helper functions (_mask_password, _read_env_database_url, _write_env_database_url)
"""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from aksara.cli.main import (
    cli,
    _mask_password,
    _read_env_database_url,
    _write_env_database_url,
)


# =============================================================================
# Helper function tests
# =============================================================================

class TestMaskPassword:
    """Tests for the _mask_password helper."""

    def test_masks_simple_password(self):
        url = "postgresql://postgres:secret@localhost:5432/mydb"
        assert _mask_password(url) == "postgresql://postgres:***@localhost:5432/mydb"

    def test_masks_special_characters_in_password(self):
        url = "postgresql://admin:p%40ssw0rd@host:5432/db"
        assert _mask_password(url) == "postgresql://admin:***@host:5432/db"

    def test_preserves_url_without_password_pattern(self):
        url = "postgresql://localhost:5432/mydb"
        # No user:pass pattern, should be unchanged
        result = _mask_password(url)
        assert "localhost" in result

    def test_masks_only_password_portion(self):
        url = "postgresql://user:longpassword123!@db.example.com:5433/prod"
        masked = _mask_password(url)
        assert "user:***@" in masked
        assert "longpassword" not in masked


class TestReadEnvDatabaseUrl:
    """Tests for _read_env_database_url."""

    def test_returns_none_if_file_missing(self, tmp_path):
        assert _read_env_database_url(tmp_path / ".env") is None

    def test_returns_none_if_no_database_url(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("SECRET_KEY=abc123\nDEBUG=true\n")
        assert _read_env_database_url(env) is None

    def test_returns_url_when_present(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("DATABASE_URL=postgresql://localhost/mydb\nDEBUG=true\n")
        assert _read_env_database_url(env) == "postgresql://localhost/mydb"

    def test_ignores_commented_lines(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("# DATABASE_URL=old_value\nDATABASE_URL=real_value\n")
        assert _read_env_database_url(env) == "real_value"

    def test_strips_whitespace(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("  DATABASE_URL = postgresql://localhost/db  \n")
        assert _read_env_database_url(env) == "postgresql://localhost/db"


class TestWriteEnvDatabaseUrl:
    """Tests for _write_env_database_url."""

    def test_creates_new_file(self, tmp_path):
        env = tmp_path / ".env"
        _write_env_database_url(env, "postgresql://localhost/new")
        assert env.read_text() == "DATABASE_URL=postgresql://localhost/new\n"

    def test_appends_to_existing_file(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("SECRET_KEY=abc\n")
        _write_env_database_url(env, "postgresql://localhost/db")
        content = env.read_text()
        assert "SECRET_KEY=abc\n" in content
        assert "DATABASE_URL=postgresql://localhost/db\n" in content

    def test_replaces_existing_url(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("SECRET_KEY=abc\nDATABASE_URL=old_value\nDEBUG=true\n")
        _write_env_database_url(env, "postgresql://localhost/new")
        content = env.read_text()
        assert "DATABASE_URL=postgresql://localhost/new\n" in content
        assert "old_value" not in content
        # Other values preserved
        assert "SECRET_KEY=abc\n" in content
        assert "DEBUG=true\n" in content

    def test_preserves_comments(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("# Database config\nDATABASE_URL=old\n# End\n")
        _write_env_database_url(env, "postgresql://localhost/new")
        content = env.read_text()
        assert "# Database config\n" in content
        assert "# End\n" in content

    def test_adds_newline_before_append(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("SECRET_KEY=abc")  # No trailing newline
        _write_env_database_url(env, "postgresql://localhost/db")
        content = env.read_text()
        assert content.endswith("DATABASE_URL=postgresql://localhost/db\n")
        # Ensure the SECRET_KEY line got a newline added
        assert "SECRET_KEY=abc\n" in content


# =============================================================================
# CLI command tests
# =============================================================================

class TestDbsetupCommand:
    """Tests for the `aksara dbsetup` CLI command."""

    def test_help_text(self):
        """Test that dbsetup shows help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["dbsetup", "--help"])
        assert result.exit_code == 0
        assert "Set up a PostgreSQL database" in result.output
        assert "aksara startproject" in result.output

    def test_dbsetup_appears_in_cli_help(self):
        """Test that dbsetup appears in the main CLI help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "dbsetup" in result.output

    @patch("aksara.cli.main._read_env_database_url")
    def test_existing_database_url_keep(self, mock_read_env):
        """Test that existing DATABASE_URL prompts and keeps if user says no."""
        mock_read_env.return_value = "postgresql://postgres:secret@localhost:5432/olddb"

        runner = CliRunner()
        result = runner.invoke(cli, ["dbsetup"], input="N\n")

        assert "already set in .env" in result.output
        assert "postgres:***@" in result.output
        assert "Keeping existing configuration" in result.output

    @patch("aksara.cli.main._read_env_database_url")
    @patch("asyncio.run")
    def test_pg_not_reachable(self, mock_asyncio_run, mock_read_env):
        """Test PostgreSQL not reachable shows helpful message."""
        mock_read_env.return_value = None
        mock_asyncio_run.return_value = False  # PG check returns False

        runner = CliRunner()
        result = runner.invoke(cli, ["dbsetup"])

        assert result.exit_code != 0
        assert "not running or not reachable" in result.output
        assert "brew services start" in result.output
        assert "systemctl start" in result.output
        assert "docker run" in result.output
        assert "aksara dbsetup" in result.output

    @patch("aksara.cli.main._write_env_database_url")
    @patch("aksara.cli.main._read_env_database_url")
    @patch("asyncio.run")
    @patch("getpass.getpass")
    def test_happy_path_db_created(
        self, mock_getpass, mock_asyncio_run, mock_read_env, mock_write_env
    ):
        """Test happy path: PG reachable, connection ok, DB created, .env written."""
        mock_read_env.return_value = None
        mock_getpass.return_value = "mypassword"

        # asyncio.run calls:
        # 1. _check_pg -> True
        # 2. _test_connection -> None (success)
        # 3. _create_database -> "created"
        mock_asyncio_run.side_effect = [True, None, "created"]

        runner = CliRunner()
        result = runner.invoke(
            cli, ["dbsetup"],
            input="testdb\npostgres\n",  # db name, username (password via getpass)
        )

        assert "found" in result.output
        assert "connected" in result.output
        assert "created" in result.output
        assert "done" in result.output
        assert "aksara migrate" in result.output
        mock_write_env.assert_called_once()

    @patch("aksara.cli.main._write_env_database_url")
    @patch("aksara.cli.main._read_env_database_url")
    @patch("asyncio.run")
    @patch("getpass.getpass")
    def test_happy_path_db_already_exists(
        self, mock_getpass, mock_asyncio_run, mock_read_env, mock_write_env
    ):
        """Test DB already exists scenario — should skip creation and write .env."""
        mock_read_env.return_value = None
        mock_getpass.return_value = "secret"

        # 1. _check_pg -> True
        # 2. _test_connection -> None
        # 3. _create_database -> "exists"
        mock_asyncio_run.side_effect = [True, None, "exists"]

        runner = CliRunner()
        result = runner.invoke(
            cli, ["dbsetup"],
            input="existingdb\npostgres\n",
        )

        assert "already exists, skipping" in result.output
        assert "done" in result.output
        assert "aksara migrate" in result.output
        mock_write_env.assert_called_once()

    @patch("aksara.cli.main._read_env_database_url")
    @patch("asyncio.run")
    @patch("getpass.getpass")
    def test_connection_failure_bad_password(
        self, mock_getpass, mock_asyncio_run, mock_read_env
    ):
        """Test connection failure with bad credentials."""
        mock_read_env.return_value = None
        mock_getpass.return_value = "wrongpass"

        # 1. _check_pg -> True
        # 2. _test_connection -> raises Exception
        mock_asyncio_run.side_effect = [
            True,
            Exception("password authentication failed for user \"postgres\""),
        ]

        runner = CliRunner()
        result = runner.invoke(
            cli, ["dbsetup"],
            input="mydb\npostgres\n",
        )

        assert result.exit_code != 0
        assert "failed" in result.output
        assert "password authentication failed" in result.output
        assert "Check your username and password" in result.output

    @patch("aksara.cli.main._read_env_database_url")
    @patch("asyncio.run")
    @patch("getpass.getpass")
    def test_connection_failure_role_not_exists(
        self, mock_getpass, mock_asyncio_run, mock_read_env
    ):
        """Test connection failure when role does not exist."""
        mock_read_env.return_value = None
        mock_getpass.return_value = "pass"

        mock_asyncio_run.side_effect = [
            True,
            Exception('role "baduser" does not exist'),
        ]

        runner = CliRunner()
        result = runner.invoke(
            cli, ["dbsetup"],
            input="mydb\nbaduser\n",
        )

        assert result.exit_code != 0
        assert "does not exist" in result.output

    @patch("aksara.cli.main._write_env_database_url")
    @patch("aksara.cli.main._read_env_database_url")
    @patch("asyncio.run")
    @patch("getpass.getpass")
    def test_env_write_uses_url_encoded_password(
        self, mock_getpass, mock_asyncio_run, mock_read_env, mock_write_env
    ):
        """Test that special characters in password are URL-encoded."""
        mock_read_env.return_value = None
        mock_getpass.return_value = "p@ss:word/test"

        mock_asyncio_run.side_effect = [True, None, "created"]

        runner = CliRunner()
        result = runner.invoke(
            cli, ["dbsetup"],
            input="mydb\npostgres\n",
        )

        # Verify the URL passed to _write_env_database_url has encoded password
        written_url = mock_write_env.call_args[0][1]
        assert "p%40ss%3Aword%2Ftest" in written_url
        assert "p@ss:word/test" not in written_url

    @patch("aksara.cli.main._write_env_database_url")
    @patch("aksara.cli.main._read_env_database_url")
    @patch("asyncio.run")
    @patch("getpass.getpass")
    def test_custom_host_and_port(
        self, mock_getpass, mock_asyncio_run, mock_read_env, mock_write_env
    ):
        """Test custom --host and --port options."""
        mock_read_env.return_value = None
        mock_getpass.return_value = "pass"

        mock_asyncio_run.side_effect = [True, None, "created"]

        runner = CliRunner()
        result = runner.invoke(
            cli, ["dbsetup", "--host", "db.example.com", "--port", "5433"],
            input="mydb\npostgres\n",
        )

        assert "db.example.com:5433" in result.output
        written_url = mock_write_env.call_args[0][1]
        assert "db.example.com:5433" in written_url

    @patch("aksara.cli.main._write_env_database_url")
    @patch("aksara.cli.main._read_env_database_url")
    @patch("asyncio.run")
    @patch("getpass.getpass")
    def test_create_database_failure(
        self, mock_getpass, mock_asyncio_run, mock_read_env, mock_write_env
    ):
        """Test database creation failure is handled gracefully."""
        mock_read_env.return_value = None
        mock_getpass.return_value = "pass"

        mock_asyncio_run.side_effect = [
            True,
            None,
            Exception("permission denied to create database"),
        ]

        runner = CliRunner()
        result = runner.invoke(
            cli, ["dbsetup"],
            input="mydb\npostgres\n",
        )

        assert result.exit_code != 0
        assert "Could not create database" in result.output
        mock_write_env.assert_not_called()

    @patch("aksara.cli.main._read_env_database_url")
    @patch("asyncio.run")
    @patch("getpass.getpass")
    @patch("aksara.cli.main._write_env_database_url")
    def test_env_write_failure(
        self, mock_write_env, mock_getpass, mock_asyncio_run, mock_read_env
    ):
        """Test .env write failure is handled gracefully."""
        mock_read_env.return_value = None
        mock_getpass.return_value = "pass"
        mock_asyncio_run.side_effect = [True, None, "created"]
        mock_write_env.side_effect = PermissionError("Permission denied: '.env'")

        runner = CliRunner()
        result = runner.invoke(
            cli, ["dbsetup"],
            input="mydb\npostgres\n",
        )

        assert result.exit_code != 0
        assert "Could not write .env" in result.output
