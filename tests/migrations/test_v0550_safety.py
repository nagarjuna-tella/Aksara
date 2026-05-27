"""
v0.5.50 Migration-Safety Patch — Regression Tests

Covers all 7 P0 fixes:
  1+2. Per-migration transaction wrapping with record_migration inside
  3.   Advisory lock in apply_migrations()
  4.   Multi-statement SQL via _split_sql_statements()
  5.   Cycle detection in execution_order()
  6.   ArrayField present in operations.__all__
  7.   model_to_create_table() Array codegen uses op.ArrayField, not op.TextField
"""

import os
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

from aksara.migrations import operations as op
from aksara.migrations.graph import MigrationGraph, MigrationNode
from aksara.migrations.executor import (
    _compute_file_checksum,
    _split_sql_statements,
    apply_migration,
    apply_migrations,
    model_to_create_table,
)


# =============================================================================
# Fix 6: ArrayField in __all__
# =============================================================================

class TestArrayFieldInAll:
    def test_array_field_in_all(self):
        assert "ArrayField" in op.__all__, (
            "ArrayField must be exported from operations.__all__ so that "
            "'from aksara.migrations.operations import *' includes it"
        )

    def test_array_field_importable(self):
        assert hasattr(op, "ArrayField")
        assert issubclass(op.ArrayField, op.FieldOp)


# =============================================================================
# Fix 7: model_to_create_table() Array codegen
# =============================================================================

class TestArrayCodegen:
    def _clear_registry(self):
        from aksara.registry import ModelRegistry
        ModelRegistry._models.clear()

    def test_array_str_generates_array_field(self):
        from aksara.model.base import Model
        from aksara import fields
        self._clear_registry()

        class TaggedModel(Model):
            id = fields.UUID(primary_key=True)
            tags = fields.Array(item_type=str)

        code = model_to_create_table(TaggedModel)
        self._clear_registry()

        assert "op.ArrayField" in code, (
            "Array field must generate op.ArrayField, not op.TextField"
        )
        assert "op.TextField" not in code or "op.ArrayField" in code
        assert "TEXT[]" in code

    def test_array_int_maps_to_integer_array(self):
        from aksara.model.base import Model
        from aksara import fields
        self._clear_registry()

        class ScoreModel(Model):
            id = fields.UUID(primary_key=True)
            scores = fields.Array(item_type=int)

        code = model_to_create_table(ScoreModel)
        self._clear_registry()

        assert "op.ArrayField" in code
        assert "INTEGER[]" in code

    def test_array_float_maps_to_double_precision_array(self):
        from aksara.model.base import Model
        from aksara import fields
        self._clear_registry()

        class MetricModel(Model):
            id = fields.UUID(primary_key=True)
            values = fields.Array(item_type=float)

        code = model_to_create_table(MetricModel)
        self._clear_registry()

        assert "op.ArrayField" in code
        assert "DOUBLE PRECISION[]" in code

    def test_array_bool_maps_to_boolean_array(self):
        from aksara.model.base import Model
        from aksara import fields
        self._clear_registry()

        class FlagModel(Model):
            id = fields.UUID(primary_key=True)
            flags = fields.Array(item_type=bool)

        code = model_to_create_table(FlagModel)
        self._clear_registry()

        assert "op.ArrayField" in code
        assert "BOOLEAN[]" in code

    def test_array_no_item_type_kwarg_in_generated_code(self):
        """Generated code must not pass item_type= to ArrayField (invalid param)."""
        from aksara.model.base import Model
        from aksara import fields
        self._clear_registry()

        class M(Model):
            id = fields.UUID(primary_key=True)
            items = fields.Array(item_type=str)

        code = model_to_create_table(M)
        self._clear_registry()

        assert "item_type=" not in code, (
            "op.ArrayField has no item_type parameter; codegen must not emit it"
        )

    def test_array_nullable_false_is_emitted(self):
        from aksara.model.base import Model
        from aksara import fields
        self._clear_registry()

        class RequiredTagsModel(Model):
            id = fields.UUID(primary_key=True)
            tags = fields.Array(item_type=str, nullable=False)

        code = model_to_create_table(RequiredTagsModel)
        self._clear_registry()

        assert "op.ArrayField(sql_type='TEXT[]', nullable=False)" in code

    def test_array_nullable_true_uses_default_codegen(self):
        from aksara.model.base import Model
        from aksara import fields
        self._clear_registry()

        class OptionalTagsModel(Model):
            id = fields.UUID(primary_key=True)
            tags = fields.Array(item_type=str, nullable=True)

        code = model_to_create_table(OptionalTagsModel)
        self._clear_registry()

        assert "op.ArrayField(sql_type='TEXT[]')" in code
        assert "nullable=True" not in code

    def test_array_non_callable_default_is_preserved(self):
        from aksara.model.base import Model
        from aksara import fields
        self._clear_registry()

        class DefaultTagsModel(Model):
            id = fields.UUID(primary_key=True)
            tags = fields.Array(item_type=str, default=["alpha", "beta"])

        code = model_to_create_table(DefaultTagsModel)
        self._clear_registry()

        assert "default=['alpha', 'beta']" in code


# =============================================================================
# Fix 4: _split_sql_statements()
# =============================================================================

class TestSplitSqlStatements:
    def test_single_statement(self):
        sql = "CREATE TABLE foo (id SERIAL);"
        parts = _split_sql_statements(sql)
        assert len(parts) == 1
        assert "CREATE TABLE foo" in parts[0]

    def test_two_statements(self):
        sql = "CREATE TABLE a (id SERIAL);\nCREATE TABLE b (id SERIAL);"
        parts = _split_sql_statements(sql)
        assert len(parts) == 2

    def test_three_statements(self):
        sql = (
            "CREATE TABLE x (id SERIAL);\n"
            "CREATE TABLE y (id SERIAL);\n"
            "CREATE TABLE z (id SERIAL);\n"
        )
        parts = _split_sql_statements(sql)
        assert len(parts) == 3

    def test_comments_stripped(self):
        sql = (
            "-- create table\n"
            "CREATE TABLE foo (id SERIAL);\n"
            "-- done\n"
        )
        parts = _split_sql_statements(sql)
        assert len(parts) == 1
        assert "--" not in parts[0]

    def test_blank_lines_ignored(self):
        sql = "\n\nCREATE TABLE foo (id SERIAL);\n\n"
        parts = _split_sql_statements(sql)
        assert len(parts) == 1

    def test_no_trailing_semicolon(self):
        sql = "CREATE TABLE foo (id SERIAL)"
        parts = _split_sql_statements(sql)
        assert len(parts) == 1

    def test_empty_string(self):
        parts = _split_sql_statements("")
        assert parts == []

    def test_only_comments(self):
        sql = "-- nothing here\n-- still nothing\n"
        parts = _split_sql_statements(sql)
        assert parts == []

    def test_inline_two_statements_same_line(self):
        # Regression: old line-based splitter missed semicolons mid-line.
        sql = "CREATE TABLE a (id int); CREATE TABLE b (id int);"
        parts = _split_sql_statements(sql)
        assert len(parts) == 2

    def test_unterminated_block_comment_raises(self):
        sql = "CREATE TABLE a(id int); /* unterminated"
        with pytest.raises(ValueError, match="Unterminated block comment in SQL migration"):
            _split_sql_statements(sql)

    def test_unterminated_single_quoted_string_raises(self):
        sql = "INSERT INTO t (v) VALUES ('unterminated);"
        with pytest.raises(ValueError, match="Unterminated single-quoted string in SQL migration"):
            _split_sql_statements(sql)

    def test_unterminated_double_quoted_identifier_raises(self):
        sql = 'CREATE TABLE "unterminated (id int);'
        with pytest.raises(ValueError, match="Unterminated double-quoted identifier in SQL migration"):
            _split_sql_statements(sql)

    def test_unterminated_dollar_quoted_block_raises(self):
        sql = "CREATE FUNCTION f() RETURNS void AS $$ BEGIN NULL; END;"
        with pytest.raises(ValueError, match="Unterminated dollar-quoted block in SQL migration"):
            _split_sql_statements(sql)

    def test_semicolon_inside_single_quoted_string(self):
        sql = "INSERT INTO t (v) VALUES ('hello; world');"
        parts = _split_sql_statements(sql)
        assert len(parts) == 1

    def test_semicolon_inside_double_quoted_identifier(self):
        sql = 'CREATE TABLE "my;table" (id int);'
        parts = _split_sql_statements(sql)
        assert len(parts) == 1

    def test_semicolon_inside_dollar_quoted_block(self):
        sql = (
            "CREATE FUNCTION f() RETURNS void AS $$ "
            "BEGIN NULL; END; $$ LANGUAGE plpgsql;"
        )
        parts = _split_sql_statements(sql)
        assert len(parts) == 1

    def test_tagged_dollar_quoted_function_body_with_semicolons_is_one_statement(self):
        sql = (
            "CREATE FUNCTION f() RETURNS void AS $body$ "
            "BEGIN PERFORM 1; PERFORM 2; END; $body$ LANGUAGE plpgsql;"
        )
        parts = _split_sql_statements(sql)
        assert parts == [sql.rstrip(";")]

    def test_block_comment_with_semicolon_ignored(self):
        sql = "/* ignore this; */ CREATE TABLE x (id int);"
        parts = _split_sql_statements(sql)
        assert len(parts) == 1
        assert "ignore" not in parts[0]

    def test_valid_block_comment_still_works(self):
        sql = "CREATE TABLE x (id int) /* valid comment */;"
        parts = _split_sql_statements(sql)
        assert len(parts) == 1
        assert parts[0].startswith("CREATE TABLE x (id int)")

    def test_block_comment_preserves_token_separator(self):
        sql = "SELECT/*x*/1;"
        parts = _split_sql_statements(sql)
        assert parts == ["SELECT 1"]

    def test_block_comment_between_tokens_preserves_spacing(self):
        sql = "SELECT/* comment */FROM dual;"
        parts = _split_sql_statements(sql)
        assert parts == ["SELECT FROM dual"]

    def test_block_comment_between_statements_splits_cleanly(self):
        sql = "CREATE TABLE a(id int); /* comment */ CREATE TABLE b(id int);"
        parts = _split_sql_statements(sql)
        assert parts == [
            "CREATE TABLE a(id int)",
            "CREATE TABLE b(id int)",
        ]

    def test_block_comment_inside_quoted_string_is_preserved(self):
        sql = "INSERT INTO t (v) VALUES ('keep /* not a comment */ text');"
        parts = _split_sql_statements(sql)
        assert len(parts) == 1
        assert "/* not a comment */" in parts[0]

    def test_escaped_single_quote_in_string(self):
        sql = "INSERT INTO t (v) VALUES ('it''s fine; ok');"
        parts = _split_sql_statements(sql)
        assert len(parts) == 1


# =============================================================================
# Fix 5: Cycle detection in execution_order()
# =============================================================================

class TestCycleDetection:
    def _graph_with_nodes(self, *node_specs):
        """node_specs: list of (app, name, deps) tuples."""
        g = MigrationGraph()
        for app, name, deps in node_specs:
            node = MigrationNode(app_label=app, name=name, dependencies=deps)
            g.add_node(node)
        return g

    def test_linear_chain_no_cycle(self):
        g = self._graph_with_nodes(
            ("app", "0001", []),
            ("app", "0002", [("app", "0001")]),
            ("app", "0003", [("app", "0002")]),
        )
        order = g.execution_order()
        names = [n.name for n in order]
        assert names.index("0001") < names.index("0002")
        assert names.index("0002") < names.index("0003")

    def test_no_dependencies_no_cycle(self):
        g = self._graph_with_nodes(
            ("app", "0001", []),
            ("app", "0002", []),
        )
        order = g.execution_order()
        assert len(order) == 2

    def test_direct_self_cycle_raises(self):
        g = self._graph_with_nodes(
            ("app", "0001", [("app", "0001")]),
        )
        with pytest.raises(ValueError, match="cycle"):
            g.execution_order()

    def test_two_node_cycle_raises(self):
        g = self._graph_with_nodes(
            ("app", "0001", [("app", "0002")]),
            ("app", "0002", [("app", "0001")]),
        )
        with pytest.raises(ValueError, match="cycle"):
            g.execution_order()

    def test_three_node_cycle_raises(self):
        g = self._graph_with_nodes(
            ("app", "0001", [("app", "0003")]),
            ("app", "0002", [("app", "0001")]),
            ("app", "0003", [("app", "0002")]),
        )
        with pytest.raises(ValueError, match="cycle"):
            g.execution_order()

    def test_cycle_error_message_contains_migration_names(self):
        g = self._graph_with_nodes(
            ("app", "alpha", [("app", "beta")]),
            ("app", "beta", [("app", "alpha")]),
        )
        with pytest.raises(ValueError) as exc_info:
            g.execution_order()
        msg = str(exc_info.value)
        assert "alpha" in msg or "beta" in msg

    def test_diamond_no_cycle(self):
        g = self._graph_with_nodes(
            ("app", "base", []),
            ("app", "left", [("app", "base")]),
            ("app", "right", [("app", "base")]),
            ("app", "merge", [("app", "left"), ("app", "right")]),
        )
        order = g.execution_order()
        names = [n.name for n in order]
        assert names.index("base") < names.index("left")
        assert names.index("base") < names.index("right")
        assert names.index("left") < names.index("merge")
        assert names.index("right") < names.index("merge")


# =============================================================================
# Fix 1+2: Transaction wrapping + record_migration inside transaction
# =============================================================================

class TestApplyMigrationTransactionWrapping:
    """Unit tests using mocks — no real DB needed."""

    def _make_connection(self):
        conn = AsyncMock()
        # connection.transaction() must return an async context manager
        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        conn.transaction = MagicMock(return_value=tx)
        conn.execute = AsyncMock()
        conn.fetchval = AsyncMock(return_value=None)
        return conn, tx

    @pytest.mark.asyncio
    async def test_py_migration_uses_transaction(self, tmp_path):
        migration_code = '''
from aksara.migrations.base import Migration
from aksara.migrations import operations as op

class Migration(Migration):
    operations = [
        op.CreateTable(
            name="t",
            fields=[("id", op.UUIDField(primary_key=True))],
        ),
    ]
'''
        f = tmp_path / "0001_init.py"
        f.write_text(migration_code)

        conn, tx = self._make_connection()

        op_mock = AsyncMock()
        op_mock.describe = MagicMock(return_value="CreateTable t")

        with patch("aksara.migrations.executor.load_migration_module") as lm, \
             patch("aksara.migrations.executor.record_migration", new_callable=AsyncMock) as rm:
            mock_mig = MagicMock()
            mock_mig.return_value.operations = [op_mock]
            lm.return_value = mock_mig

            await apply_migration(conn, "0001_init", f, fake=False, verbose=False)

        # transaction() must have been called once
        conn.transaction.assert_called_once()
        # op and record_migration must have been called inside __aenter__ context
        op_mock.apply.assert_awaited_once()
        rm.assert_awaited_once()
        call_args = rm.call_args.args
        assert call_args[0] is conn
        assert call_args[1] == "0001_init"
        assert call_args[2] is not None  # checksum stored for Python migrations

    @pytest.mark.asyncio
    async def test_py_migration_fake_no_transaction_no_ops(self, tmp_path):
        f = tmp_path / "0001_init.py"
        f.write_text("")

        conn, tx = self._make_connection()
        op_mock = AsyncMock()
        op_mock.describe = MagicMock(return_value="CreateTable t")

        with patch("aksara.migrations.executor.load_migration_module") as lm, \
             patch("aksara.migrations.executor.record_migration", new_callable=AsyncMock) as rm:
            mock_mig = MagicMock()
            mock_mig.return_value.operations = [op_mock]
            lm.return_value = mock_mig

            await apply_migration(conn, "0001_init", f, fake=True, verbose=False)

        # No transaction when fake=True
        conn.transaction.assert_not_called()
        # No ops run
        op_mock.apply.assert_not_awaited()
        # But record_migration is still called (with checksum)
        rm.assert_awaited_once()
        call_args = rm.call_args.args
        assert call_args[0] is conn
        assert call_args[1] == "0001_init"

    @pytest.mark.asyncio
    async def test_py_migration_op_failure_rolls_back(self, tmp_path):
        """If an op raises, the transaction rolls back and record_migration is NOT called."""
        f = tmp_path / "0001_init.py"
        f.write_text("")

        conn = AsyncMock()
        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        conn.transaction = MagicMock(return_value=tx)

        exploding_op = AsyncMock()
        exploding_op.apply.side_effect = RuntimeError("boom")
        exploding_op.describe = MagicMock(return_value="BrokenOp")

        with patch("aksara.migrations.executor.load_migration_module") as lm, \
             patch("aksara.migrations.executor.record_migration", new_callable=AsyncMock) as rm:
            mock_mig = MagicMock()
            mock_mig.return_value.operations = [exploding_op]
            lm.return_value = mock_mig

            with pytest.raises(RuntimeError, match="boom"):
                await apply_migration(conn, "0001_init", f, fake=False, verbose=False)

        # record_migration must NOT have been called (it's inside the transaction which rolled back)
        rm.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_sql_migration_splits_statements(self, tmp_path):
        sql = "CREATE TABLE a (id SERIAL);\nCREATE TABLE b (id SERIAL);"
        f = tmp_path / "0001_init.sql"
        f.write_text(sql)

        conn, tx = self._make_connection()

        with patch("aksara.migrations.executor.record_migration", new_callable=AsyncMock) as rm:
            await apply_migration(conn, "0001_init", f, fake=False, verbose=False)

        statement_calls = [
            call.args[0]
            for call in conn.execute.await_args_list
            if call.args and call.args[0].startswith("CREATE TABLE ")
        ]
        assert statement_calls == [
            "CREATE TABLE a (id SERIAL)",
            "CREATE TABLE b (id SERIAL)",
        ]
        # record_migration called inside same transaction
        rm.assert_awaited_once()
        conn.transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_sql_migration_with_unterminated_block_comment_fails_before_record(self, tmp_path):
        sql = "CREATE TABLE a(id int); /* unterminated"
        f = tmp_path / "0001_init.sql"
        f.write_text(sql)

        conn, tx = self._make_connection()

        with patch("aksara.migrations.executor.record_migration", new_callable=AsyncMock) as rm:
            with pytest.raises(ValueError, match="Unterminated block comment in SQL migration"):
                await apply_migration(conn, "0001_init", f, fake=False, verbose=False)

        conn.transaction.assert_not_called()
        migration_executes = [
            call.args[0]
            for call in conn.execute.await_args_list
            if call.args and call.args[0].startswith("CREATE TABLE a")
        ]
        assert migration_executes == []
        rm.assert_not_awaited()


# =============================================================================
# Fix 3: Advisory lock in apply_migrations()
# =============================================================================

class TestAdvisoryLock:
    @pytest.mark.asyncio
    async def test_advisory_lock_acquired_and_released(self, tmp_path):
        conn = AsyncMock()
        # First fetchval = lock acquired (True), subsequent = empty list for applied
        conn.fetchval = AsyncMock(side_effect=[True])
        conn.fetch = AsyncMock(return_value=[])
        conn.execute = AsyncMock()

        with patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock), \
             patch("aksara.migrations.executor.get_applied_migrations", new_callable=AsyncMock, return_value=[]), \
             patch("aksara.migrations.executor.discover_all_migrations", return_value=[]), \
             patch("aksara.migrations.executor.get_pending_migrations", return_value=[]):
            await apply_migrations(conn, tmp_path, verbose=False)

        # Verify advisory lock was acquired
        lock_calls = [c for c in conn.fetchval.call_args_list
                      if "pg_try_advisory_lock" in str(c)]
        assert lock_calls, "pg_try_advisory_lock must be called"

        # Verify advisory lock was released in finally block
        unlock_calls = [c for c in conn.execute.call_args_list
                        if "pg_advisory_unlock" in str(c)]
        assert unlock_calls, "pg_advisory_unlock must be called in finally"

    @pytest.mark.asyncio
    async def test_lock_not_acquired_raises(self, tmp_path):
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=False)  # lock NOT acquired
        conn.execute = AsyncMock()

        with pytest.raises(RuntimeError) as exc_info:
            await apply_migrations(conn, tmp_path, verbose=False)

        message = str(exc_info.value)
        assert "Another migration process" in message
        assert "Wait for that process to finish" in message
        assert "pg_locks/pg_stat_activity" in message
        assert "pg_advisory_unlock" not in message

    @pytest.mark.asyncio
    async def test_lock_released_on_exception(self, tmp_path):
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=True)  # lock acquired
        conn.execute = AsyncMock()

        with patch("aksara.migrations.executor.ensure_migrations_table",
                   new_callable=AsyncMock, side_effect=RuntimeError("db down")), \
             pytest.raises(RuntimeError, match="db down"):
            await apply_migrations(conn, tmp_path, verbose=False)

        # Even though ensure_migrations_table raised, the lock must be released
        unlock_calls = [c for c in conn.execute.call_args_list
                        if "pg_advisory_unlock" in str(c)]
        assert unlock_calls, "pg_advisory_unlock must be called even when an error occurs"

    @pytest.mark.asyncio
    async def test_unlock_failure_does_not_mask_original_error(self, tmp_path, caplog):
        import logging

        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=True)
        conn.execute = AsyncMock(side_effect=RuntimeError("unlock failed"))

        with patch("aksara.migrations.executor.ensure_migrations_table",
                   new_callable=AsyncMock, side_effect=RuntimeError("primary failure")), \
             caplog.at_level(logging.WARNING, logger="aksara.migrations.executor"), \
             pytest.raises(RuntimeError, match="primary failure"):
            await apply_migrations(conn, tmp_path, verbose=False)

        assert "unlock failed" in caplog.text
        assert "Failed to release migration advisory lock" in caplog.text

    @pytest.mark.asyncio
    async def test_unlock_failure_logged_on_success_path(self, tmp_path, caplog):
        import logging

        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=True)
        conn.execute = AsyncMock(side_effect=RuntimeError("unlock failed"))

        with patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock), \
             patch(
                 "aksara.migrations.executor.get_applied_migration_records",
                 new_callable=AsyncMock,
                 return_value={},
             ), \
             patch("aksara.migrations.executor.discover_all_migrations", return_value=[]), \
             patch("aksara.migrations.executor.get_pending_migrations", return_value=[]), \
             caplog.at_level(logging.WARNING, logger="aksara.migrations.executor"):
            result = await apply_migrations(conn, tmp_path, verbose=False)

        assert result["errors"] == []
        assert "unlock failed" in caplog.text
        unlock_calls = [c for c in conn.execute.call_args_list
                        if "pg_advisory_unlock" in str(c)]
        assert unlock_calls, "pg_advisory_unlock must still be attempted"

    @pytest.mark.asyncio
    async def test_unlock_failure_preserves_migration_result_error(self, tmp_path, caplog):
        import logging

        migration_path = tmp_path / "0001_fail.py"
        migration_path.write_text("# migration")
        graph = MagicMock()
        graph.execution_order.return_value = [type("Node", (), {"name": "0001_fail"})()]

        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=True)
        conn.execute = AsyncMock(side_effect=RuntimeError("unlock failed"))

        with patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock), \
             patch(
                 "aksara.migrations.executor.get_applied_migration_records",
                 new_callable=AsyncMock,
                 return_value={},
             ), \
             patch(
                 "aksara.migrations.executor.discover_all_migrations",
                 return_value=[("0001_fail", migration_path)],
             ), \
             patch(
                 "aksara.migrations.executor.get_pending_migrations",
                 return_value=[("0001_fail", migration_path)],
             ), \
             patch("aksara.migrations.executor.build_migration_graph", return_value=graph), \
             patch(
                 "aksara.migrations.executor.apply_migration",
                 new_callable=AsyncMock,
                 side_effect=RuntimeError("migration failed"),
             ), \
             caplog.at_level(logging.WARNING, logger="aksara.migrations.executor"):
            result = await apply_migrations(conn, tmp_path, verbose=False)

        assert result["errors"] == [("0001_fail", "migration failed")]
        assert "unlock failed" in caplog.text


# =============================================================================
# Missing-from-disk warning
# =============================================================================

class TestMissingFromDiskWarning:
    @pytest.mark.asyncio
    async def test_applied_migration_missing_from_disk_warns(self, tmp_path, caplog):
        import logging

        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=True)  # advisory lock acquired
        conn.execute = AsyncMock()

        with patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock), \
             patch(
                 "aksara.migrations.executor.get_applied_migration_records",
                 new_callable=AsyncMock,
                 return_value={"0001_deleted": "abc123"},
             ), \
             patch("aksara.migrations.executor.discover_all_migrations", return_value=[]), \
             patch("aksara.migrations.executor.get_pending_migrations", return_value=[]), \
             caplog.at_level(logging.WARNING, logger="aksara.migrations.executor"):
            await apply_migrations(conn, tmp_path, verbose=True)

        assert any(
            "0001_deleted" in record.message
            for record in caplog.records
            if record.levelno == logging.WARNING
        ), "Expected a WARNING mentioning the missing migration name"

    @pytest.mark.asyncio
    async def test_include_internal_false_does_not_warn_for_present_internal_or_apply_it(
        self, tmp_path, caplog
    ):
        import logging

        internal_name = "aksara_internal_present"
        internal_file = tmp_path / f"{internal_name}.py"
        internal_file.write_text("# internal migration")
        internal_checksum = _compute_file_checksum(internal_file)
        user_file = tmp_path / "0002_user.py"
        user_file.write_text("# user migration")
        graph = MagicMock()
        graph.execution_order.return_value = [type("Node", (), {"name": "0002_user"})()]

        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=True)
        conn.execute = AsyncMock()

        with patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock) as ensure_mock, \
             patch(
                 "aksara.migrations.executor.get_applied_migration_records",
                 new_callable=AsyncMock,
                 return_value={internal_name: internal_checksum},
             ), \
             patch(
                 "aksara.migrations.executor.discover_all_migrations",
                 side_effect=[
                     [("0002_user", user_file)],
                     [(internal_name, internal_file), ("0002_user", user_file)],
                 ],
             ) as discover_mock, \
             patch(
                 "aksara.migrations.executor.get_pending_migrations",
                 return_value=[("0002_user", user_file)],
             ), \
             patch("aksara.migrations.executor.build_migration_graph", return_value=graph), \
             patch(
                 "aksara.migrations.executor.apply_migration",
                 new_callable=AsyncMock,
             ) as apply_mock, \
             caplog.at_level(logging.WARNING, logger="aksara.migrations.executor"):
            result = await apply_migrations(
                conn,
                tmp_path,
                verbose=False,
                include_internal=False,
            )

        missing_warnings = [
            record.message
            for record in caplog.records
            if record.levelno == logging.WARNING and "not found on disk" in record.message
        ]
        assert missing_warnings == []
        assert result["applied"] == ["0002_user"]
        ensure_mock.assert_awaited_once()
        assert apply_mock.await_count == 1
        assert apply_mock.await_args.args[1] == "0002_user"
        assert apply_mock.await_args.kwargs["ensure_table"] is False
        assert discover_mock.call_args_list[0].kwargs["include_internal"] is False
        assert discover_mock.call_args_list[1].kwargs["include_internal"] is True

    @pytest.mark.asyncio
    async def test_include_internal_false_still_warns_for_missing_user_migration(
        self, tmp_path, caplog
    ):
        import logging

        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=True)
        conn.execute = AsyncMock()

        with patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock), \
             patch(
                 "aksara.migrations.executor.get_applied_migration_records",
                 new_callable=AsyncMock,
                 return_value={"0001_deleted": "abc123"},
             ), \
             patch(
                 "aksara.migrations.executor.discover_all_migrations",
                 side_effect=[[], []],
             ) as discover_mock, \
             patch("aksara.migrations.executor.get_pending_migrations", return_value=[]), \
             caplog.at_level(logging.WARNING, logger="aksara.migrations.executor"):
            await apply_migrations(conn, tmp_path, verbose=False, include_internal=False)

        assert any(
            "0001_deleted" in record.message and "not found on disk" in record.message
            for record in caplog.records
            if record.levelno == logging.WARNING
        )
        assert discover_mock.call_args_list[0].kwargs["include_internal"] is False
        assert discover_mock.call_args_list[1].kwargs["include_internal"] is True

    @pytest.mark.asyncio
    async def test_include_internal_false_warns_for_truly_missing_internal_migration(
        self, tmp_path, caplog
    ):
        import logging

        missing_internal = "aksara_internal_deleted"
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=True)
        conn.execute = AsyncMock()

        with patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock), \
             patch(
                 "aksara.migrations.executor.get_applied_migration_records",
                 new_callable=AsyncMock,
                 return_value={missing_internal: "abc123"},
             ), \
             patch(
                 "aksara.migrations.executor.discover_all_migrations",
                 side_effect=[[], []],
             ) as discover_mock, \
             patch("aksara.migrations.executor.get_pending_migrations", return_value=[]), \
             caplog.at_level(logging.WARNING, logger="aksara.migrations.executor"):
            await apply_migrations(conn, tmp_path, verbose=False, include_internal=False)

        assert any(
            missing_internal in record.message and "not found on disk" in record.message
            for record in caplog.records
            if record.levelno == logging.WARNING
        )
        assert discover_mock.call_args_list[0].kwargs["include_internal"] is False
        assert discover_mock.call_args_list[1].kwargs["include_internal"] is True

    @pytest.mark.asyncio
    async def test_missing_from_disk_warning_uses_parameterized_delete(self, tmp_path, caplog):
        import logging

        missing_name = "0001_o'hai"
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=True)
        conn.execute = AsyncMock()

        with patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock), \
             patch(
                 "aksara.migrations.executor.get_applied_migration_records",
                 new_callable=AsyncMock,
                 return_value={missing_name: "abc123"},
             ), \
             patch("aksara.migrations.executor.discover_all_migrations", return_value=[]), \
             patch("aksara.migrations.executor.get_pending_migrations", return_value=[]), \
             caplog.at_level(logging.WARNING, logger="aksara.migrations.executor"):
            await apply_migrations(conn, tmp_path, verbose=True)

        warning = next(
            record.message
            for record in caplog.records
            if record.levelno == logging.WARNING and "not found on disk" in record.message
        )
        assert "DELETE FROM aksara_migrations WHERE name = $1;" in warning
        assert f"WHERE name = '{missing_name}'" not in warning
        assert missing_name in warning

    @pytest.mark.asyncio
    async def test_no_warning_when_all_applied_are_on_disk(self, tmp_path, caplog):
        import logging

        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=True)
        conn.execute = AsyncMock()

        mig_file = tmp_path / "0001_present.py"
        mig_file.write_text("# migration")

        with patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock), \
             patch(
                 "aksara.migrations.executor.get_applied_migration_records",
                 new_callable=AsyncMock,
                 # None = applied before checksums were introduced; verification skipped
                 return_value={"0001_present": None},
             ), \
             patch(
                 "aksara.migrations.executor.discover_all_migrations",
                 return_value=[("0001_present", mig_file)],
             ), \
             patch("aksara.migrations.executor.get_pending_migrations", return_value=[]), \
             caplog.at_level(logging.WARNING, logger="aksara.migrations.executor"):
            await apply_migrations(conn, tmp_path, verbose=True)

        missing_warnings = [
            r for r in caplog.records
            if r.levelno == logging.WARNING and "not found on disk" in r.message
        ]
        assert missing_warnings == [], "No missing-from-disk warnings expected"
