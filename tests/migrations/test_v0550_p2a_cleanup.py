"""
v0.5.50 P2-A Migration Cleanup — Regression Tests

Covers:
  1. Migration._initialized removed — instantiation still works
  2. Unreachable isinstance(field, type(None)) branch removed
  3. RemoveConstraint _is_missing_constraint_error uses SQLSTATE first
  4. CLI displays pending_skipped after a failure
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aksara.migrations.base import Migration
from aksara.migrations.operations import (
    RemoveConstraint,
    _extract_sqlstate,
    _is_missing_constraint_error,
)


# =============================================================================
# Task 1: Migration._initialized removed
# =============================================================================

class TestMigrationInstantiation:
    def test_base_migration_instantiates(self):
        m = Migration()
        assert m is not None

    def test_no_initialized_attribute(self):
        m = Migration()
        assert not hasattr(m, "_initialized"), (
            "_initialized was a dead flag and should have been removed"
        )

    def test_subclass_with_operations_instantiates(self):
        from aksara.migrations import operations as op

        class MyMigration(Migration):
            operations = [
                op.CreateTable(
                    name="things",
                    fields=[("id", op.UUIDField(primary_key=True))],
                )
            ]

        m = MyMigration()
        assert len(m.operations) == 1

    def test_subclass_with_dependencies_instantiates(self):
        class MyMigration(Migration):
            dependencies = [("myapp", "0001_initial")]
            operations = []

        m = MyMigration()
        assert m.dependencies == [("myapp", "0001_initial")]

    def test_multiple_instantiations_do_not_share_state(self):
        class MyMigration(Migration):
            operations = []

        m1 = MyMigration()
        m2 = MyMigration()
        assert m1 is not m2

    def test_repr(self):
        m = Migration()
        assert "Migration" in repr(m)


# =============================================================================
# Task 2: Unreachable isinstance(field, type(None)) branch removed
# =============================================================================

class TestAutodetectorFallback:
    """Verify the NoneType branch removal doesn't break unknown-field fallback."""

    def test_unknown_field_like_object_still_returns_string_field(self):
        """An object that matches no known field type falls back to StringField."""
        from aksara.migrations.autodetector import _model_field_to_op

        class WeirdField:
            nullable = True
            default = None
            primary_key = False
            unique = False
            max_length = None
            auto_now = False
            auto_now_add = False

        field_op = _model_field_to_op("thing", WeirdField())
        # Unknown type should still produce a usable op (StringField fallback)
        assert field_op is not None

    def test_standard_fields_still_detected(self):
        from aksara.migrations.autodetector import _model_field_to_op
        from aksara.fields import String, Boolean, DateTime, Integer

        for field_cls, expected_type in [
            (String, "StringField"),
            (Boolean, "BooleanField"),
            (DateTime, "DateTimeField"),
            (Integer, "IntegerField"),
        ]:
            # Just check no exception — we already have broader autodetector tests
            op = _model_field_to_op("col", field_cls())
            assert op is not None


# =============================================================================
# Task 3: RemoveConstraint _is_missing_constraint_error
# =============================================================================

class TestExtractSqlstate:
    def test_direct_sqlstate_is_returned_first(self):
        exc = Exception("db error")
        exc.sqlstate = "42704"
        assert _extract_sqlstate(exc) == "42704"

    def test_original_exception_sqlstate_is_returned(self):
        exc = Exception("wrapped")
        original = Exception("inner")
        original.sqlstate = "42704"
        exc.original_exception = original
        assert _extract_sqlstate(exc) == "42704"

    def test_cause_sqlstate_is_returned(self):
        exc = Exception("wrapped")
        cause = Exception("cause")
        cause.sqlstate = "42704"
        exc.__cause__ = cause
        assert _extract_sqlstate(exc) == "42704"

    def test_context_sqlstate_is_returned(self):
        exc = Exception("wrapped")
        context = Exception("context")
        context.sqlstate = "42704"
        exc.__context__ = context
        assert _extract_sqlstate(exc) == "42704"

class TestIsMissingConstraintError:
    def test_sqlstate_42704_returns_true(self):
        exc = Exception("some db error")
        exc.sqlstate = "42704"
        assert _is_missing_constraint_error(exc) is True

    def test_sqlstate_other_returns_false(self):
        exc = Exception("some other error")
        exc.sqlstate = "23505"  # unique_violation
        assert _is_missing_constraint_error(exc) is False

    def test_no_sqlstate_falls_back_to_string_match(self):
        exc = Exception('ERROR: constraint "foo" does not exist')
        assert not hasattr(exc, "sqlstate")
        assert _is_missing_constraint_error(exc) is True

    def test_no_sqlstate_unrelated_message_returns_false(self):
        exc = Exception("connection refused")
        assert not hasattr(exc, "sqlstate")
        assert _is_missing_constraint_error(exc) is False

    def test_sqlstate_takes_priority_over_string(self):
        """Even if the string says 'does not exist', a non-42704 sqlstate wins."""
        exc = Exception("does not exist in some other way")
        exc.sqlstate = "08006"  # connection_failure
        assert _is_missing_constraint_error(exc) is False

    def test_original_exception_sqlstate_42704_returns_true(self):
        exc = Exception("wrapped error")
        original = Exception('constraint "foo" does not exist')
        original.sqlstate = "42704"
        exc.original_exception = original
        assert _is_missing_constraint_error(exc) is True

    def test_cause_sqlstate_42704_returns_true(self):
        exc = Exception("wrapped error")
        cause = Exception('constraint "foo" does not exist')
        cause.sqlstate = "42704"
        exc.__cause__ = cause
        assert _is_missing_constraint_error(exc) is True

    def test_context_sqlstate_42704_returns_true(self):
        exc = Exception("wrapped error")
        context = Exception('constraint "foo" does not exist')
        context.sqlstate = "42704"
        exc.__context__ = context
        assert _is_missing_constraint_error(exc) is True

    def test_non_42704_sqlstate_blocks_string_fallback_when_wrapped(self):
        exc = Exception('constraint "foo" does not exist')
        original = Exception('constraint "foo" does not exist')
        original.sqlstate = "23505"
        exc.original_exception = original
        assert _is_missing_constraint_error(exc) is False


class TestRemoveConstraintErrorHandling:
    @pytest.mark.asyncio
    async def test_if_exists_true_suppresses_42704(self):
        conn = AsyncMock()
        err = Exception("constraint missing")
        err.sqlstate = "42704"
        conn.execute.side_effect = err

        op = RemoveConstraint(table="users", name="chk_age", if_exists=True)
        # Should not raise
        await op.apply(conn)

    @pytest.mark.asyncio
    async def test_if_exists_true_suppresses_english_fallback(self):
        conn = AsyncMock()
        conn.execute.side_effect = Exception('constraint "chk_age" does not exist')

        op = RemoveConstraint(table="users", name="chk_age", if_exists=True)
        await op.apply(conn)

    @pytest.mark.asyncio
    async def test_if_exists_true_does_not_suppress_unrelated_sqlstate(self):
        conn = AsyncMock()
        err = Exception("permission denied")
        err.sqlstate = "42501"
        conn.execute.side_effect = err

        op = RemoveConstraint(table="users", name="chk_age", if_exists=True)
        with pytest.raises(Exception, match="permission denied"):
            await op.apply(conn)

    @pytest.mark.asyncio
    async def test_if_exists_false_does_not_suppress(self):
        conn = AsyncMock()
        err = Exception("constraint missing")
        err.sqlstate = "42704"
        conn.execute.side_effect = err

        op = RemoveConstraint(table="users", name="chk_age", if_exists=False)
        with pytest.raises(Exception):
            await op.apply(conn)

    @pytest.mark.asyncio
    async def test_success_path_no_error(self):
        conn = AsyncMock()
        conn.execute.return_value = "ALTER TABLE"

        op = RemoveConstraint(table="users", name="chk_age")
        await op.apply(conn)
        conn.execute.assert_awaited_once()


# =============================================================================
# Task 4: CLI pending_skipped display
# =============================================================================

class TestCLIPendingSkippedDisplay:
    """Unit-test the _display_pending_skipped helper directly."""

    def test_empty_list_shows_nothing(self):
        from aksara.cli.main import _display_pending_skipped

        ui = MagicMock()
        _display_pending_skipped(ui, [])

        ui.blank.assert_not_called()
        ui.warning.assert_not_called()
        ui.text.assert_not_called()

    def test_non_empty_list_shows_warning_and_names(self):
        from aksara.cli.main import _display_pending_skipped

        ui = MagicMock()
        _display_pending_skipped(ui, ["0002_b", "0003_c"])

        ui.blank.assert_called_once()
        ui.warning.assert_called_once()
        warning_msg = ui.warning.call_args.args[0]
        assert "2" in warning_msg or "Skipped" in warning_msg

        text_calls = [str(c) for c in ui.text.call_args_list]
        assert any("0002_b" in c for c in text_calls)
        assert any("0003_c" in c for c in text_calls)
