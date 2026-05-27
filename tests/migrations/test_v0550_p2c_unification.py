"""
v0.5.50 P2-C-lite: Migration Execution Path Unification — Regression Tests

Covers:
  1. CLI migrate delegates to executor.apply_migrations() — not a manual loop
  2. CLI migrate output reflects the apply_migrations() result dict
  3. CLI migrate exits non-zero on executor errors
  4. CLI migrate shows pending_skipped after a failure
  5. CLI migrate fake mode uses apply_migrations(fake=True)
  6. testing._apply_test_migrations delegates to apply_migrations()
  7. testing helper no longer records NULL checksums (uses canonical path)
"""

from __future__ import annotations

import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

from click.testing import CliRunner

from aksara.cli.main import _display_pending_skipped, cli


runner = CliRunner()


# =============================================================================
# Helpers
# =============================================================================

class _FakeDatabase:
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def execute(self, *a, **kw) -> None: ...


def _apply_result(**overrides):
    """Build a minimal apply_migrations() result dict."""
    base = {
        "applied": [],
        "skipped": [],
        "pending_skipped": [],
        "errors": [],
        "total_discovered": 0,
    }
    base.update(overrides)
    return base


def _cli_patches(tmp_path, migration_path, *, apply_result):
    """Return a list of patch contexts for a typical migrate invocation."""
    return [
        patch("aksara.db.Database", return_value=_FakeDatabase()),
        patch("aksara.migrations.executor.discover_migrations",
              return_value=[("0001_init", migration_path)]),
        patch("aksara.migrations.executor.build_migration_graph",
              return_value=MagicMock()),
        patch("aksara.migrations.executor.ensure_migrations_table",
              new_callable=AsyncMock),
        patch("aksara.migrations.executor.get_applied_migrations",
              new_callable=AsyncMock, return_value=[]),
        patch("aksara.migrations.executor.check_migration_conflicts",
              return_value=[]),
        patch("aksara.migrations.executor.apply_migrations",
              new_callable=AsyncMock, return_value=apply_result),
    ]


# =============================================================================
# Task 1: CLI migrate delegates to apply_migrations()
# =============================================================================

class TestCLIMigrateDelegation:
    def _run(self, tmp_path, *, apply_result, monkeypatch, extra_args=()):
        from aksara.conf import settings
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        migration_path = migrations_dir / "0001_init.py"
        migration_path.write_text("# migration")

        monkeypatch.setattr(settings, "database_url", "postgresql://localhost/test",
                            raising=False)
        monkeypatch.setattr(settings, "migrations_dir", str(migrations_dir),
                            raising=False)

        patches = _cli_patches(tmp_path, migration_path, apply_result=apply_result)
        # Stack all patches
        from contextlib import ExitStack
        with ExitStack() as stack:
            mocks = [stack.enter_context(p) for p in patches]
            apply_mock = mocks[-1]  # last patch is apply_migrations
            result = runner.invoke(cli, ["migrate"] + list(extra_args))
            return result, apply_mock

    def test_apply_migrations_is_called(self, tmp_path, monkeypatch):
        result, apply_mock = self._run(
            tmp_path, apply_result=_apply_result(applied=["0001_init"]),
            monkeypatch=monkeypatch,
        )
        assert result.exit_code == 0
        apply_mock.assert_awaited_once()

    def test_canonical_path_does_not_pre_ensure_migrations_table(
        self, tmp_path, monkeypatch
    ):
        from aksara.conf import settings
        from contextlib import ExitStack

        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        migration_path = migrations_dir / "0001_init.py"
        migration_path.write_text("# migration")

        monkeypatch.setattr(
            settings, "database_url", "postgresql://localhost/test", raising=False
        )
        monkeypatch.setattr(settings, "migrations_dir", str(migrations_dir), raising=False)

        patches = _cli_patches(
            tmp_path, migration_path, apply_result=_apply_result(applied=["0001_init"])
        )
        with ExitStack() as stack:
            mocks = [stack.enter_context(p) for p in patches]
            ensure_mock = mocks[3]
            apply_mock = mocks[-1]

            result = runner.invoke(cli, ["migrate"])

        assert result.exit_code == 0
        apply_mock.assert_awaited_once()
        ensure_mock.assert_not_awaited()

    def test_apply_migrations_receives_db_and_path(self, tmp_path, monkeypatch):
        result, apply_mock = self._run(
            tmp_path, apply_result=_apply_result(applied=["0001_init"]),
            monkeypatch=monkeypatch,
        )
        assert apply_mock.await_count == 1
        # Second positional arg is the migrations path
        call_args = apply_mock.call_args
        # apply_migrations(db, mig_dir, fake=..., verbose=..., include_internal=...)
        assert call_args.kwargs.get("fake") is False
        assert call_args.kwargs.get("include_internal") is True

    def test_fake_flag_passed_through(self, tmp_path, monkeypatch):
        result, apply_mock = self._run(
            tmp_path,
            apply_result=_apply_result(applied=["0001_init"]),
            monkeypatch=monkeypatch,
            extra_args=["--fake"],
        )
        assert apply_mock.await_count == 1
        assert apply_mock.call_args.kwargs.get("fake") is True

    def test_no_manual_op_apply_called(self, tmp_path, monkeypatch):
        """The CLI must not call op.apply() directly — that lives inside apply_migrations."""
        from contextlib import ExitStack
        from aksara.conf import settings
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        migration_path = migrations_dir / "0001_init.py"
        migration_path.write_text("# migration")

        monkeypatch.setattr(settings, "database_url", "postgresql://localhost/test",
                            raising=False)
        monkeypatch.setattr(settings, "migrations_dir", str(migrations_dir),
                            raising=False)

        patches = _cli_patches(tmp_path, migration_path,
                               apply_result=_apply_result(applied=["0001_init"]))
        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            with patch("aksara.migrations.executor.load_migration_module") as mock_load:
                runner.invoke(cli, ["migrate"])
                # load_migration_module should NOT be called in the non-dry-run path
                mock_load.assert_not_called()


# =============================================================================
# Task 2: CLI output reflects apply_migrations() result dict
# =============================================================================

class TestCLIMigrateOutput:
    def _invoke(self, tmp_path, monkeypatch, apply_result, extra_args=()):
        from aksara.conf import settings
        from contextlib import ExitStack
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        migration_path = migrations_dir / "0001_init.py"
        migration_path.write_text("# migration")

        monkeypatch.setattr(settings, "database_url", "postgresql://localhost/test",
                            raising=False)
        monkeypatch.setattr(settings, "migrations_dir", str(migrations_dir),
                            raising=False)
        patches = _cli_patches(tmp_path, migration_path, apply_result=apply_result)
        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            return runner.invoke(cli, ["migrate"] + list(extra_args))

    def test_applied_names_shown(self, tmp_path, monkeypatch):
        result = self._invoke(
            tmp_path, monkeypatch,
            apply_result=_apply_result(applied=["0001_init", "0002_add_field"]),
        )
        assert result.exit_code == 0
        assert "0001_init" in result.output
        assert "0002_add_field" in result.output

    def test_all_applied_shows_success_message(self, tmp_path, monkeypatch):
        result = self._invoke(
            tmp_path, monkeypatch,
            apply_result=_apply_result(applied=[], skipped=["0001_init"]),
        )
        assert result.exit_code == 0
        assert "All migrations already applied!" in result.output

    def test_fake_mode_output(self, tmp_path, monkeypatch):
        result = self._invoke(
            tmp_path, monkeypatch,
            apply_result=_apply_result(applied=["0001_init"]),
            extra_args=["--fake"],
        )
        assert result.exit_code == 0
        assert "marked as applied" in result.output

    def test_error_shown_in_output(self, tmp_path, monkeypatch):
        result = self._invoke(
            tmp_path, monkeypatch,
            apply_result=_apply_result(
                errors=[("0001_init", "syntax error near DROP")],
            ),
        )
        assert result.exit_code != 0
        assert "0001_init" in result.output
        assert "syntax error" in result.output

    def test_pending_skipped_shown_after_error(self, tmp_path, monkeypatch):
        result = self._invoke(
            tmp_path, monkeypatch,
            apply_result=_apply_result(
                errors=[("0001_init", "boom")],
                pending_skipped=["0002_add_field", "0003_add_index"],
            ),
        )
        assert result.exit_code != 0
        assert "0002_add_field" in result.output
        assert "0003_add_index" in result.output

    def test_pending_skipped_display_uses_helper(self, tmp_path, monkeypatch):
        from aksara.conf import settings
        from contextlib import ExitStack

        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        migration_path = migrations_dir / "0001_init.py"
        migration_path.write_text("# migration")

        monkeypatch.setattr(
            settings, "database_url", "postgresql://localhost/test", raising=False
        )
        monkeypatch.setattr(settings, "migrations_dir", str(migrations_dir), raising=False)

        patches = _cli_patches(
            tmp_path,
            migration_path,
            apply_result=_apply_result(
                errors=[("0001_init", "boom")],
                pending_skipped=["0002_add_field", "0003_add_index"],
            ),
        )
        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            with patch(
                "aksara.cli.main._display_pending_skipped",
                wraps=_display_pending_skipped,
            ) as mock_display:
                result = runner.invoke(cli, ["migrate"])

        assert result.exit_code != 0
        mock_display.assert_called_once()
        assert mock_display.call_args.args[1] == ["0002_add_field", "0003_add_index"]

    def test_exit_nonzero_on_errors(self, tmp_path, monkeypatch):
        result = self._invoke(
            tmp_path, monkeypatch,
            apply_result=_apply_result(
                errors=[("0001_init", "table does not exist")],
            ),
        )
        assert result.exit_code != 0

    def test_exit_zero_on_success(self, tmp_path, monkeypatch):
        result = self._invoke(
            tmp_path, monkeypatch,
            apply_result=_apply_result(applied=["0001_init"]),
        )
        assert result.exit_code == 0


# =============================================================================
# Task 3: Dry-run path uses load_migration_module, not apply_migrations
# =============================================================================

class TestCLIMigrateDryRun:
    def test_dry_run_does_not_call_apply_migrations(self, tmp_path, monkeypatch):
        from aksara.conf import settings
        from contextlib import ExitStack
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        migration_path = migrations_dir / "0001_init.py"
        migration_path.write_text("# migration")

        monkeypatch.setattr(settings, "database_url", "postgresql://localhost/test",
                            raising=False)
        monkeypatch.setattr(settings, "migrations_dir", str(migrations_dir),
                            raising=False)
        patches = _cli_patches(tmp_path, migration_path,
                               apply_result=_apply_result())
        # Patch get_applied_migrations to return empty so dry-run shows pending
        patches[4] = patch("aksara.migrations.executor.get_applied_migrations",
                           new_callable=AsyncMock, return_value=[])
        # Patch get_pending_migrations for the dry-run path
        patches.append(
            patch("aksara.migrations.executor.get_pending_migrations",
                  return_value=[("0001_init", migration_path)])
        )

        with ExitStack() as stack:
            mocks = [stack.enter_context(p) for p in patches]
            apply_mock = mocks[6]  # apply_migrations
            result = runner.invoke(cli, ["migrate", "--dry-run"])
            apply_mock.assert_not_awaited()

    def test_dry_run_shows_would_apply(self, tmp_path, monkeypatch):
        from aksara.conf import settings
        from contextlib import ExitStack
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        migration_path = migrations_dir / "0001_init.py"
        migration_path.write_text("# migration")

        monkeypatch.setattr(settings, "database_url", "postgresql://localhost/test",
                            raising=False)
        monkeypatch.setattr(settings, "migrations_dir", str(migrations_dir),
                            raising=False)
        patches = _cli_patches(tmp_path, migration_path, apply_result=_apply_result())
        patches[4] = patch("aksara.migrations.executor.get_applied_migrations",
                           new_callable=AsyncMock, return_value=[])
        patches.append(
            patch("aksara.migrations.executor.get_pending_migrations",
                  return_value=[("0001_init", migration_path)])
        )
        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            with patch("aksara.migrations.executor.load_migration_module") as mock_load:
                mock_mig = MagicMock()
                mock_mig.operations = []
                mock_load.return_value = type("M", (), {"operations": [], "__call__": lambda s: mock_mig})
                result = runner.invoke(cli, ["migrate", "--dry-run"])
        assert "DRY RUN" in result.output


# =============================================================================
# Task 4: testing._apply_test_migrations delegates to apply_migrations()
# =============================================================================

class TestApplyTestMigrationsDelegation:
    @pytest.mark.asyncio
    async def test_delegates_to_apply_migrations(self, tmp_path, monkeypatch):
        from aksara.conf import settings
        from aksara.testing import _apply_test_migrations

        monkeypatch.setattr(settings, "migrations_dir", str(tmp_path / "migrations"),
                            raising=False)

        with patch("aksara.migrations.executor.apply_migrations",
                   new_callable=AsyncMock) as mock_apply, \
             patch("aksara.db.Database") as mock_db_cls:
            mock_db = AsyncMock()
            mock_db_cls.return_value = mock_db
            mock_apply.return_value = {
                "applied": [], "skipped": [], "pending_skipped": [],
                "errors": [], "total_discovered": 0,
            }

            await _apply_test_migrations("postgresql://localhost/test")

            mock_apply.assert_awaited_once()
            call_kwargs = mock_apply.call_args.kwargs
            assert call_kwargs.get("fake") is False
            assert call_kwargs.get("include_internal") is True

    @pytest.mark.asyncio
    async def test_no_errors_result_does_not_raise(self, tmp_path, monkeypatch):
        from aksara.conf import settings
        from aksara.testing import _apply_test_migrations

        monkeypatch.setattr(settings, "migrations_dir", str(tmp_path / "migrations"),
                            raising=False)

        with patch(
            "aksara.migrations.executor.apply_migrations",
            new_callable=AsyncMock,
            return_value={
                "applied": ["0001_init"],
                "skipped": [],
                "pending_skipped": [],
                "errors": [],
                "total_discovered": 1,
            },
        ) as mock_apply, patch("aksara.db.Database") as mock_db_cls:
            mock_db = AsyncMock()
            mock_db_cls.return_value = mock_db

            await _apply_test_migrations("postgresql://localhost/test")

            mock_apply.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_error_result_raises_runtime_error_with_pending_skipped(
        self, tmp_path, monkeypatch
    ):
        from aksara.conf import settings
        from aksara.testing import _apply_test_migrations

        monkeypatch.setattr(settings, "migrations_dir", str(tmp_path / "migrations"),
                            raising=False)

        with patch(
            "aksara.migrations.executor.apply_migrations",
            new_callable=AsyncMock,
            return_value={
                "applied": [],
                "skipped": [],
                "pending_skipped": ["0002_add_field", "0003_add_index"],
                "errors": [("0001_init", "syntax error near DROP")],
                "total_discovered": 3,
            },
        ), patch("aksara.db.Database") as mock_db_cls:
            mock_db = AsyncMock()
            mock_db_cls.return_value = mock_db

            with pytest.raises(RuntimeError) as exc_info:
                await _apply_test_migrations("postgresql://localhost/test")

        message = str(exc_info.value)
        assert "0001_init" in message
        assert "syntax error near DROP" in message
        assert "0002_add_field" in message
        assert "0003_add_index" in message

    @pytest.mark.asyncio
    async def test_no_longer_calls_record_migration_directly(self, tmp_path, monkeypatch):
        """The testing helper must not bypass apply_migrations with its own record calls."""
        from aksara.conf import settings
        from aksara.testing import _apply_test_migrations

        monkeypatch.setattr(settings, "migrations_dir", str(tmp_path / "migrations"),
                            raising=False)

        with patch("aksara.migrations.executor.apply_migrations",
                   new_callable=AsyncMock,
                   return_value={"applied": [], "skipped": [], "pending_skipped": [],
                                 "errors": [], "total_discovered": 0}), \
             patch("aksara.db.Database") as mock_db_cls, \
             patch("aksara.migrations.executor.record_migration",
                   new_callable=AsyncMock) as mock_record:
            mock_db = AsyncMock()
            mock_db_cls.return_value = mock_db

            await _apply_test_migrations("postgresql://localhost/test")

            mock_record.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_db_connect_and_disconnect_called(self, tmp_path, monkeypatch):
        from aksara.conf import settings
        from aksara.testing import _apply_test_migrations

        monkeypatch.setattr(settings, "migrations_dir", str(tmp_path / "migrations"),
                            raising=False)

        with patch("aksara.migrations.executor.apply_migrations",
                   new_callable=AsyncMock,
                   return_value={"applied": [], "skipped": [], "pending_skipped": [],
                                 "errors": [], "total_discovered": 0}), \
             patch("aksara.db.Database") as mock_db_cls:
            mock_db = AsyncMock()
            mock_db_cls.return_value = mock_db

            await _apply_test_migrations("postgresql://localhost/test")

            mock_db.connect.assert_awaited_once()
            mock_db.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_called_even_if_apply_raises(self, tmp_path, monkeypatch):
        from aksara.conf import settings
        from aksara.testing import _apply_test_migrations

        monkeypatch.setattr(settings, "migrations_dir", str(tmp_path / "migrations"),
                            raising=False)

        with patch("aksara.migrations.executor.apply_migrations",
                   new_callable=AsyncMock,
                   side_effect=RuntimeError("lock held")), \
             patch("aksara.db.Database") as mock_db_cls:
            mock_db = AsyncMock()
            mock_db_cls.return_value = mock_db

            with pytest.raises(RuntimeError):
                await _apply_test_migrations("postgresql://localhost/test")

            mock_db.disconnect.assert_awaited_once()
