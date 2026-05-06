"""
Tests for the `aksara models` CLI command.
"""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from aksara.cli.main import cli
from aksara.fields import String


runner = CliRunner()


class TestModelsCommand:
    """Tests for `aksara models`."""

    @patch("aksara.cli.main.discover_models")
    @patch("aksara.registry.ModelRegistry.all")
    def test_lists_nullable_field_without_crashing(self, mock_all, mock_discover) -> None:
        """The command should read the field `nullable` attribute used by runtime fields."""
        title = String(nullable=True, unique=True)
        title.name = "title"

        post_model = type(
            "Post",
            (),
            {
                "__tablename__": "posts",
                "_fields": {"title": title},
            },
        )
        mock_all.return_value = {"Post": post_model}

        result = runner.invoke(cli, ["models"])

        assert result.exit_code == 0
        assert "📦 Post" in result.output
        assert "title: VARCHAR(255) unique nullable" in result.output