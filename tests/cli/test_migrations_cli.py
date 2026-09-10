"""
Tests for the makemigrations and migrate CLI commands.
"""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from aksara.cli.main import cli


runner = CliRunner()


class _FakeDatabase:
    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        return None

    async def execute(self, *args, **kwargs) -> None:
        return None


class TestMakemigrationsCommand:
    @patch("aksara.cli.main.discover_models")
    @patch("aksara.registry.ModelRegistry.all", return_value={})
    def test_no_models_found(self, mock_all, mock_discover) -> None:
        result = runner.invoke(cli, ["makemigrations"])

        assert result.exit_code == 0
        assert "No models found!" in result.output

    @patch("aksara.cli.main.discover_models")
    @patch("aksara.registry.ModelRegistry.all", return_value={"User": MagicMock()})
    @patch(
        "aksara.migrations.autodetector.detect_changes",
        return_value=(SimpleNamespace(has_changes=False), []),
    )
    def test_no_changes_detected(
        self,
        mock_detect_changes,
        mock_all,
        mock_discover,
        monkeypatch,
        tmp_path,
    ) -> None:
        from aksara.conf import settings

        monkeypatch.setattr(settings, "migrations_dir", str(tmp_path / "migrations"), raising=False)

        result = runner.invoke(cli, ["makemigrations"])

        assert result.exit_code == 0
        assert "No changes detected." in result.output

    @patch("aksara.cli.main.discover_models")
    @patch("aksara.registry.ModelRegistry.all", return_value={"User": MagicMock()})
    @patch(
        "aksara.migrations.autodetector.detect_changes",
        return_value=(
            SimpleNamespace(
                has_changes=True,
                new_tables=["users"],
                added_fields={},
                removed_fields={},
                removed_tables=[],
                altered_fields={},
            ),
            [MagicMock()],
        ),
    )
    @patch(
        "aksara.migrations.autodetector.operations_to_code",
        return_value="        op.RunSQL('SELECT 1')",
    )
    @patch(
        "aksara.migrations.executor.generate_migration_filename",
        return_value="0001_auto.py",
    )
    def test_writes_python_migration_file(
        self,
        mock_filename,
        mock_ops_to_code,
        mock_detect_changes,
        mock_all,
        mock_discover,
        monkeypatch,
        tmp_path,
    ) -> None:
        from aksara.conf import settings

        migrations_dir = tmp_path / "migrations"
        monkeypatch.setattr(settings, "migrations_dir", str(migrations_dir), raising=False)

        result = runner.invoke(cli, ["makemigrations"])

        assert result.exit_code == 0
        assert "Python Migration created" in result.output
        assert (migrations_dir / "0001_auto.py").exists()

    def test_sql_stdout_orders_models_by_foreign_key_dependencies(self) -> None:
        from aksara import Model, fields
        from aksara.registry import ModelRegistry

        ModelRegistry._models.clear()

        try:
            class SqlOrderUser(Model):
                id = fields.UUID(primary_key=True)

                class Meta:
                    table_name = "sql_order_users"

            class SqlOrderPost(Model):
                id = fields.UUID(primary_key=True)
                author = fields.ForeignKey(SqlOrderUser)

                class Meta:
                    table_name = "sql_order_posts"

            models = {
                "SqlOrderPost": SqlOrderPost,
                "SqlOrderUser": SqlOrderUser,
            }

            with patch("aksara.cli.main.discover_models"), patch(
                "aksara.registry.ModelRegistry.all",
                return_value=models,
            ):
                result = runner.invoke(
                    cli,
                    ["makemigrations", "--sql", "--stdout"],
                )

            assert result.exit_code == 0
            assert result.output.index("-- Model: SqlOrderUser") < result.output.index(
                "-- Model: SqlOrderPost"
            )
        finally:
            ModelRegistry._models.clear()


class TestMigrateCommand:
    def _invoke_with_apply_exception(self, tmp_path, monkeypatch, exc):
        from aksara.conf import settings

        migrations_dir = tmp_path / "migrations"
        migration_path = migrations_dir / "0001_initial.py"
        migrations_dir.mkdir()
        migration_path.write_text("# migration")

        monkeypatch.setattr(settings, "database_url", "postgresql://localhost/test", raising=False)
        monkeypatch.setattr(settings, "migrations_dir", str(migrations_dir), raising=False)

        with ExitStack() as stack:
            stack.enter_context(patch("aksara.db.Database", return_value=_FakeDatabase()))
            stack.enter_context(
                patch(
                    "aksara.migrations.executor.discover_migrations",
                    return_value=[("0001_initial", migration_path)],
                )
            )
            stack.enter_context(
                patch("aksara.migrations.executor.build_migration_graph", return_value=MagicMock())
            )
            stack.enter_context(
                patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock)
            )
            stack.enter_context(
                patch(
                    "aksara.migrations.executor.get_applied_migrations",
                    new_callable=AsyncMock,
                    return_value=[],
                )
            )
            stack.enter_context(
                patch("aksara.migrations.executor.check_migration_conflicts", return_value=[])
            )
            apply_mock = stack.enter_context(
                patch(
                    "aksara.migrations.executor.apply_migrations",
                    new_callable=AsyncMock,
                    side_effect=exc,
                )
            )

            result = runner.invoke(cli, ["migrate"])

        return result, apply_mock

    def test_requires_database_url(self, monkeypatch) -> None:
        from aksara.conf import settings

        monkeypatch.delenv("AKSARA_DATABASE_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setattr(settings, "database_url", None, raising=False)

        result = runner.invoke(cli, ["migrate"])

        assert result.exit_code != 0
        assert "No database URL provided!" in result.output

    @patch("aksara.db.Database", return_value=_FakeDatabase())
    @patch("aksara.migrations.executor.discover_migrations")
    @patch("aksara.migrations.executor.build_migration_graph", return_value=MagicMock())
    @patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock)
    @patch(
        "aksara.migrations.executor.get_applied_migrations",
        new_callable=AsyncMock,
        return_value=["0001_initial"],
    )
    @patch("aksara.migrations.executor.check_migration_conflicts", return_value=[])
    @patch(
        "aksara.migrations.executor.apply_migrations",
        new_callable=AsyncMock,
        return_value={
            "applied": [],
            "skipped": ["0001_initial"],
            "pending_skipped": [],
            "errors": [],
            "total_discovered": 1,
        },
    )
    def test_all_migrations_already_applied(
        self,
        mock_apply,
        mock_conflicts,
        mock_applied,
        mock_ensure_table,
        mock_graph,
        mock_discover,
        mock_db,
        monkeypatch,
        tmp_path,
    ) -> None:
        from aksara.conf import settings

        migrations_dir = tmp_path / "migrations"
        migration_path = migrations_dir / "0001_initial.py"
        migrations_dir.mkdir()
        migration_path.write_text("# migration")

        monkeypatch.setattr(settings, "database_url", "postgresql://localhost/test", raising=False)
        monkeypatch.setattr(settings, "migrations_dir", str(migrations_dir), raising=False)
        mock_discover.return_value = [("0001_initial", migration_path)]

        result = runner.invoke(cli, ["migrate"])

        assert result.exit_code == 0
        assert "All migrations already applied!" in result.output

    @patch("aksara.migrations.executor.discover_migrations")
    @patch(
        "aksara.migrations.executor.build_migration_graph",
        side_effect=ValueError("Could not load migration app.0001_bad"),
    )
    def test_preflight_graph_error_is_clean_cli_failure(
        self,
        mock_graph,
        mock_discover,
        monkeypatch,
        tmp_path,
    ) -> None:
        from aksara.conf import settings

        migrations_dir = tmp_path / "migrations"
        migration_path = migrations_dir / "0001_bad.py"
        migrations_dir.mkdir()
        migration_path.write_text("def broken(:")

        monkeypatch.setattr(settings, "database_url", "postgresql://localhost/test", raising=False)
        monkeypatch.setattr(settings, "migrations_dir", str(migrations_dir), raising=False)
        mock_discover.return_value = [("0001_bad", migration_path)]

        result = runner.invoke(cli, ["migrate"])

        assert result.exit_code != 0
        assert "Could not build migration graph" in result.output
        assert "Could not load migration" in result.output
        assert "Traceback" not in result.output
        mock_graph.assert_called_once()

    def test_apply_migrations_runtime_error_is_clean_cli_failure(
        self, monkeypatch, tmp_path
    ) -> None:
        result, apply_mock = self._invoke_with_apply_exception(
            tmp_path,
            monkeypatch,
            RuntimeError("Could not acquire migration advisory lock"),
        )

        assert result.exit_code != 0
        assert "Migration failed:" in result.output
        assert "advisory lock" in result.output
        assert "Traceback" not in result.output
        apply_mock.assert_awaited_once()

    def test_apply_migrations_value_error_is_clean_cli_failure(
        self, monkeypatch, tmp_path
    ) -> None:
        result, apply_mock = self._invoke_with_apply_exception(
            tmp_path,
            monkeypatch,
            ValueError("Migration checksum mismatch for '0001_initial'"),
        )

        assert result.exit_code != 0
        assert "Migration failed:" in result.output
        assert "checksum mismatch" in result.output
        assert "Traceback" not in result.output
        apply_mock.assert_awaited_once()
