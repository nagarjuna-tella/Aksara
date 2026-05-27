"""
v0.5.50 P1 Migration Safety — Regression Tests

Covers four P1 fixes:
  1. AddField NOT NULL without DEFAULT warning in generated code
  2. Checksum recording (Python) and verification for applied migrations
  3. build_migration_graph raises clearly on migration load errors
  4. apply_migrations reports pending_skipped after a failure
"""

import logging
import os
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from aksara.migrations import operations as op
from aksara.migrations.executor import (
    _compute_file_checksum,
    build_migration_graph,
    apply_migration,
    apply_migrations,
    get_applied_migration_records,
    record_migration,
    ensure_migrations_table,
)
from aksara.migrations.autodetector import operations_to_code


# =============================================================================
# Fix 1: AddField NOT NULL without DEFAULT warning
# =============================================================================

class TestAddFieldNonNullWarning:
    def _code_for(self, field_op, table="posts", name="status"):
        operation = op.AddField(table=table, name=name, field=field_op)
        return operations_to_code([operation])

    def test_non_null_no_default_gets_warning(self):
        code = self._code_for(op.StringField(nullable=False))
        assert "WARNING" in code
        assert "non-null" in code.lower() or "non_null" in code.lower() or "non-null field" in code

    def test_warning_mentions_field_name(self):
        code = self._code_for(op.StringField(nullable=False), name="status")
        assert '"status"' in code

    def test_warning_mentions_table_name(self):
        code = self._code_for(op.StringField(nullable=False), table="articles")
        assert '"articles"' in code

    def test_warning_precedes_add_field(self):
        code = self._code_for(op.StringField(nullable=False))
        warning_pos = code.index("WARNING")
        add_field_pos = code.index("op.AddField")
        assert warning_pos < add_field_pos

    def test_non_null_with_default_no_warning(self):
        code = self._code_for(op.StringField(nullable=False, default="draft"))
        assert "WARNING" not in code

    def test_non_null_string_default_no_warning(self):
        code = self._code_for(op.StringField(nullable=False, default="x"))
        assert "WARNING" not in code

    def test_nullable_no_warning(self):
        code = self._code_for(op.StringField(nullable=True))
        assert "WARNING" not in code

    def test_nullable_default_none_no_warning(self):
        # nullable=True is the risky-free case even without a default
        code = self._code_for(op.StringField(nullable=True, default=None))
        assert "WARNING" not in code

    def test_primary_key_no_warning(self):
        code = self._code_for(op.UUIDField(primary_key=True), name="id")
        assert "WARNING" not in code

    def test_integer_non_null_no_default_gets_warning(self):
        code = self._code_for(op.IntegerField(nullable=False))
        assert "WARNING" in code

    def test_integer_non_null_with_default_no_warning(self):
        code = self._code_for(op.IntegerField(nullable=False, default=0))
        assert "WARNING" not in code

    def test_datetime_auto_now_add_db_default_no_warning(self):
        code = self._code_for(op.DateTimeField(auto_now_add=True, nullable=False))
        assert "WARNING" not in code

    def test_datetime_non_null_no_default_gets_warning(self):
        code = self._code_for(op.DateTimeField(nullable=False))
        assert "WARNING" in code

    def test_boolean_non_null_with_default_no_warning(self):
        code = self._code_for(op.BooleanField(default=True, nullable=False))
        assert "WARNING" not in code

    def test_add_field_still_present_when_warned(self):
        code = self._code_for(op.StringField(nullable=False))
        assert "op.AddField" in code

    def test_no_warning_for_create_table(self):
        operation = op.CreateTable(
            name="posts",
            fields=[
                ("id", op.UUIDField(primary_key=True)),
                ("status", op.StringField(nullable=False)),
            ],
        )
        code = operations_to_code([operation])
        assert "WARNING" not in code


# =============================================================================
# Fix 2: Checksum recording and verification
# =============================================================================

class TestChecksumHelper:
    def test_compute_file_checksum_returns_16_chars(self, tmp_path):
        f = tmp_path / "mig.py"
        f.write_text("hello")
        cs = _compute_file_checksum(f)
        assert len(cs) == 16
        assert cs.isalnum()

    def test_same_content_same_checksum(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("same content")
        f2.write_text("same content")
        assert _compute_file_checksum(f1) == _compute_file_checksum(f2)

    def test_different_content_different_checksum(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("content A")
        f2.write_text("content B")
        assert _compute_file_checksum(f1) != _compute_file_checksum(f2)


class TestApplyMigrationStoresChecksum:
    """Unit tests — verify apply_migration passes checksum to record_migration."""

    def _make_raw_conn(self):
        conn = AsyncMock()
        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        conn.transaction = MagicMock(return_value=tx)
        return conn

    @pytest.mark.asyncio
    async def test_python_migration_stores_checksum(self, tmp_path):
        f = tmp_path / "0001_init.py"
        f.write_text("")
        conn = self._make_raw_conn()

        with patch("aksara.migrations.executor.load_migration_module") as lm, \
             patch("aksara.migrations.executor.record_migration", new_callable=AsyncMock) as rm:
            mock_mig = MagicMock()
            mock_mig.return_value.operations = []
            lm.return_value = mock_mig

            await apply_migration(conn, "0001_init", f, fake=False, verbose=False)

        rm.assert_awaited_once()
        _, call_name, call_checksum = rm.call_args.args
        assert call_checksum is not None
        assert len(call_checksum) == 16

    @pytest.mark.asyncio
    async def test_direct_apply_ensures_tracking_table_before_transaction(self, tmp_path):
        f = tmp_path / "0001_init.py"
        f.write_text("")
        conn = self._make_raw_conn()
        tx = conn.transaction.return_value
        events = []

        def _enter_transaction():
            events.append("tx_enter")
            return tx

        async def _ensure_table(_conn):
            events.append("ensure_table")

        async def _record(*_args):
            events.append("record_migration")

        tx.__aenter__.side_effect = _enter_transaction

        with patch(
            "aksara.migrations.executor.ensure_migrations_table",
            new_callable=AsyncMock,
            side_effect=_ensure_table,
        ) as ensure_mock, patch("aksara.migrations.executor.load_migration_module") as lm, \
             patch(
                 "aksara.migrations.executor.record_migration",
                 new_callable=AsyncMock,
                 side_effect=_record,
             ):
            mock_mig = MagicMock()
            mock_mig.return_value.operations = []
            lm.return_value = mock_mig

            await apply_migration(conn, "0001_init", f, fake=False, verbose=False)

        ensure_mock.assert_awaited_once()
        assert events[:2] == ["ensure_table", "tx_enter"]
        assert "record_migration" in events

    @pytest.mark.asyncio
    async def test_direct_apply_can_skip_tracking_table_setup(self, tmp_path):
        f = tmp_path / "0001_init.py"
        f.write_text("")
        conn = self._make_raw_conn()

        with patch(
            "aksara.migrations.executor.ensure_migrations_table",
            new_callable=AsyncMock,
        ) as ensure_mock, patch("aksara.migrations.executor.load_migration_module") as lm, \
             patch("aksara.migrations.executor.record_migration", new_callable=AsyncMock) as rm:
            mock_mig = MagicMock()
            mock_mig.return_value.operations = []
            lm.return_value = mock_mig

            await apply_migration(
                conn,
                "0001_init",
                f,
                fake=False,
                verbose=False,
                ensure_table=False,
            )

        ensure_mock.assert_not_awaited()
        rm.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sql_migration_stores_checksum(self, tmp_path):
        f = tmp_path / "0001_init.sql"
        f.write_text("CREATE TABLE t (id SERIAL);")
        conn = self._make_raw_conn()

        with patch("aksara.migrations.executor.record_migration", new_callable=AsyncMock) as rm:
            await apply_migration(conn, "0001_init", f, fake=False, verbose=False)

        rm.assert_awaited_once()
        _, call_name, call_checksum = rm.call_args.args
        assert call_checksum is not None
        assert len(call_checksum) == 16


class TestChecksumVerification:
    """Checksum mismatch and NULL-checksum behavior in apply_migrations."""

    def _make_conn(self, lock_acquired=True):
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=lock_acquired)
        conn.execute = AsyncMock()
        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        conn.transaction = MagicMock(return_value=tx)
        return conn

    @pytest.mark.asyncio
    async def test_matching_checksum_allows_skip(self, tmp_path):
        """Already-applied migration with matching checksum is skipped silently."""
        f = tmp_path / "0001_init.py"
        f.write_text("# migration")
        stored_cs = _compute_file_checksum(f)

        conn = self._make_conn()
        with patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock), \
             patch("aksara.migrations.executor.get_applied_migration_records",
                   new_callable=AsyncMock,
                   return_value={"0001_init": stored_cs}), \
             patch("aksara.migrations.executor.discover_all_migrations",
                   return_value=[("0001_init", f)]), \
             patch("aksara.migrations.executor.get_pending_migrations", return_value=[]):
            result = await apply_migrations(conn, tmp_path, verbose=False)

        assert result["errors"] == []
        assert result["applied"] == []

    @pytest.mark.asyncio
    async def test_checksum_mismatch_raises(self, tmp_path):
        """Already-applied migration with changed contents raises ValueError."""
        f = tmp_path / "0001_init.py"
        f.write_text("# MODIFIED after apply")

        conn = self._make_conn()
        with patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock), \
             patch("aksara.migrations.executor.get_applied_migration_records",
                   new_callable=AsyncMock,
                   return_value={"0001_init": "0000000000000000"}), \
             patch("aksara.migrations.executor.discover_all_migrations",
                   return_value=[("0001_init", f)]), \
             patch("aksara.migrations.executor.get_pending_migrations", return_value=[]):
            with pytest.raises(ValueError, match="checksum mismatch"):
                await apply_migrations(conn, tmp_path, verbose=False)

    @pytest.mark.asyncio
    async def test_null_checksum_does_not_fail(self, tmp_path):
        """Backward compat: NULL stored checksum skips verification (warns only)."""
        f = tmp_path / "0001_init.py"
        f.write_text("# migration")

        conn = self._make_conn()
        with patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock), \
             patch("aksara.migrations.executor.get_applied_migration_records",
                   new_callable=AsyncMock,
                   return_value={"0001_init": None}), \
             patch("aksara.migrations.executor.discover_all_migrations",
                   return_value=[("0001_init", f)]), \
             patch("aksara.migrations.executor.get_pending_migrations", return_value=[]):
            result = await apply_migrations(conn, tmp_path, verbose=False)

        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_null_checksum_warning_emitted_when_not_verbose(self, tmp_path, caplog):
        """Operators should see legacy NULL-checksum warnings even in CLI mode."""
        f = tmp_path / "0001_init.py"
        f.write_text("# migration")

        conn = self._make_conn()
        caplog.set_level(logging.WARNING, logger="aksara.migrations.executor")
        with patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock), \
             patch("aksara.migrations.executor.get_applied_migration_records",
                   new_callable=AsyncMock,
                   return_value={"0001_init": None}), \
             patch("aksara.migrations.executor.discover_all_migrations",
                   return_value=[("0001_init", f)]), \
             patch("aksara.migrations.executor.get_pending_migrations", return_value=[]):
            result = await apply_migrations(conn, tmp_path, verbose=False)

        assert result["errors"] == []
        assert "Checksum unavailable" in caplog.text
        assert "0001_init" in caplog.text

    @pytest.mark.asyncio
    async def test_null_checksum_does_not_block_pending_migrations(self, tmp_path):
        legacy = tmp_path / "0001_legacy.py"
        legacy.write_text("# legacy")
        pending = tmp_path / "0002_pending.py"
        pending.write_text("# pending")

        graph = MagicMock()
        graph.execution_order.return_value = [type("Node", (), {"name": "0002_pending"})()]

        conn = self._make_conn()
        with patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock), \
             patch("aksara.migrations.executor.get_applied_migration_records",
                   new_callable=AsyncMock,
                   return_value={"0001_legacy": None}), \
             patch("aksara.migrations.executor.discover_all_migrations",
                   return_value=[("0001_legacy", legacy), ("0002_pending", pending)]), \
             patch("aksara.migrations.executor.get_pending_migrations",
                   return_value=[("0002_pending", pending)]), \
             patch("aksara.migrations.executor.build_migration_graph",
                   return_value=graph), \
             patch("aksara.migrations.executor.apply_migration",
                   new_callable=AsyncMock) as apply_mock:
            result = await apply_migrations(conn, tmp_path, verbose=False)

        assert result["errors"] == []
        assert result["applied"] == ["0002_pending"]
        apply_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_include_internal_false_verifies_applied_internal_checksums(self, tmp_path):
        internal_name = "aksara_contrib_auth_migrations_0001_initial"
        internal_file = tmp_path / "0001_internal.py"
        internal_file.write_text("# internal migration")
        internal_checksum = _compute_file_checksum(internal_file)
        pending = tmp_path / "0002_pending.py"
        pending.write_text("# pending")
        graph = MagicMock()
        graph.execution_order.return_value = [type("Node", (), {"name": "0002_pending"})()]
        original_compute = _compute_file_checksum
        computed_paths = []

        def _track_checksum(path):
            computed_paths.append(path)
            return original_compute(path)

        conn = self._make_conn()
        with patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock), \
             patch(
                 "aksara.migrations.executor.get_applied_migration_records",
                 new_callable=AsyncMock,
                 return_value={internal_name: internal_checksum},
             ), \
             patch(
                 "aksara.migrations.executor.discover_all_migrations",
                 side_effect=[
                     [("0002_pending", pending)],
                     [(internal_name, internal_file), ("0002_pending", pending)],
                 ],
             ), \
             patch(
                 "aksara.migrations.executor.get_pending_migrations",
                 return_value=[("0002_pending", pending)],
             ), \
             patch("aksara.migrations.executor.build_migration_graph", return_value=graph), \
             patch(
                 "aksara.migrations.executor.apply_migration",
                 new_callable=AsyncMock,
             ) as apply_mock, \
             patch(
                 "aksara.migrations.executor._compute_file_checksum",
                 side_effect=_track_checksum,
             ):
            result = await apply_migrations(conn, tmp_path, verbose=False, include_internal=False)

        assert result["errors"] == []
        assert internal_file in computed_paths
        apply_mock.assert_awaited_once()
        assert result["applied"] == ["0002_pending"]

    @pytest.mark.asyncio
    async def test_include_internal_false_raises_on_applied_internal_checksum_mismatch(self, tmp_path):
        internal_name = "aksara_contrib_auth_migrations_0001_initial"
        internal_file = tmp_path / "0001_internal.py"
        internal_file.write_text("# internal migration")
        pending = tmp_path / "0002_pending.py"
        pending.write_text("# pending")

        conn = self._make_conn()
        with patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock), \
             patch(
                 "aksara.migrations.executor.get_applied_migration_records",
                 new_callable=AsyncMock,
                 return_value={internal_name: "deadbeefdeadbeef"},
             ), \
             patch(
                 "aksara.migrations.executor.discover_all_migrations",
                 side_effect=[
                     [("0002_pending", pending)],
                     [(internal_name, internal_file), ("0002_pending", pending)],
                 ],
             ), \
             patch(
                 "aksara.migrations.executor.get_pending_migrations",
                 return_value=[("0002_pending", pending)],
             ), \
             patch(
                 "aksara.migrations.executor.apply_migration",
                 new_callable=AsyncMock,
             ) as apply_mock:
            with pytest.raises(ValueError, match="checksum mismatch"):
                await apply_migrations(conn, tmp_path, verbose=False, include_internal=False)

        apply_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_error_message_includes_migration_name(self, tmp_path):
        f = tmp_path / "app_0002_posts.py"
        f.write_text("# changed")

        conn = self._make_conn()
        with patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock), \
             patch("aksara.migrations.executor.get_applied_migration_records",
                   new_callable=AsyncMock,
                   return_value={"app_0002_posts": "deadbeefdeadbeef"}), \
             patch("aksara.migrations.executor.discover_all_migrations",
                   return_value=[("app_0002_posts", f)]), \
             patch("aksara.migrations.executor.get_pending_migrations", return_value=[]):
            with pytest.raises(ValueError) as exc_info:
                await apply_migrations(conn, tmp_path, verbose=False)

        assert "app_0002_posts" in str(exc_info.value)
        assert "applied" in str(exc_info.value).lower()


# =============================================================================
# DB-backed checksum tests (require DATABASE_URL)
# =============================================================================

@pytest.fixture
async def db():
    from aksara.db import Database
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set")
    database = Database(db_url)
    await database.connect()
    await ensure_migrations_table(database)
    await database.execute("DELETE FROM aksara_migrations WHERE name LIKE 'test_p1_%'")
    yield database
    await database.execute("DELETE FROM aksara_migrations WHERE name LIKE 'test_p1_%'")
    await database.disconnect()


@pytest.mark.asyncio
async def test_python_migration_records_checksum_in_db(db, tmp_path):
    f = tmp_path / "test_p1_0001.py"
    f.write_text("# migration content")
    expected_cs = _compute_file_checksum(f)

    with patch("aksara.migrations.executor.load_migration_module") as lm:
        mock_mig = MagicMock()
        mock_mig.return_value.operations = []
        lm.return_value = mock_mig
        await apply_migration(db, "test_p1_0001", f, fake=False, verbose=False)

    records = await get_applied_migration_records(db)
    assert "test_p1_0001" in records
    assert records["test_p1_0001"] == expected_cs


@pytest.mark.asyncio
async def test_direct_apply_creates_tracking_table_on_fresh_db(db, tmp_path):
    f = tmp_path / "test_p1_0002_fresh.py"
    f.write_text("# migration content")
    expected_cs = _compute_file_checksum(f)
    existing_rows = await db.fetch(
        "SELECT name, checksum, applied_at FROM aksara_migrations ORDER BY applied_at, id"
    )

    try:
        await db.execute("DROP TABLE IF EXISTS aksara_migrations")

        with patch("aksara.migrations.executor.load_migration_module") as lm:
            mock_mig = MagicMock()
            mock_mig.return_value.operations = []
            lm.return_value = mock_mig
            await apply_migration(db, "test_p1_0002_fresh", f, fake=False, verbose=False)

        table_exists = await db.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'aksara_migrations'
            )
            """
        )
        assert table_exists is True

        stored_checksum = await db.fetchval(
            "SELECT checksum FROM aksara_migrations WHERE name = $1",
            "test_p1_0002_fresh",
        )
        assert stored_checksum == expected_cs
    finally:
        await ensure_migrations_table(db)
        await db.execute("DELETE FROM aksara_migrations")
        for row in existing_rows:
            await db.execute(
                """
                INSERT INTO aksara_migrations (name, checksum, applied_at)
                VALUES ($1, $2, $3)
                """,
                row["name"],
                row["checksum"],
                row["applied_at"],
            )


@pytest.mark.asyncio
async def test_null_checksum_backward_compat_in_db(db, tmp_path):
    """Row with NULL checksum must not block apply_migrations."""
    await record_migration(db, "test_p1_legacy", None)

    f = tmp_path / "test_p1_legacy.py"
    f.write_text("# migration")

    conn_mock = AsyncMock()
    conn_mock.fetchval = AsyncMock(return_value=True)
    conn_mock.execute = AsyncMock()
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn_mock.transaction = MagicMock(return_value=tx)

    with patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock), \
         patch("aksara.migrations.executor.get_applied_migration_records",
               new_callable=AsyncMock,
               return_value={"test_p1_legacy": None}), \
         patch("aksara.migrations.executor.discover_all_migrations",
               return_value=[("test_p1_legacy", f)]), \
         patch("aksara.migrations.executor.get_pending_migrations", return_value=[]):
        result = await apply_migrations(conn_mock, tmp_path, verbose=False)

    assert result["errors"] == []


# =============================================================================
# Fix 3: build_migration_graph raises on load errors
# =============================================================================

class TestBuildMigrationGraphStrictErrors:
    def test_syntax_error_raises_value_error(self, tmp_path):
        bad = tmp_path / "0001_bad.py"
        bad.write_text("def broken(:")

        with pytest.raises(ValueError, match="Could not load migration"):
            build_migration_graph(migrations_path=tmp_path, include_internal=False)

    def test_error_includes_migration_name(self, tmp_path):
        bad = tmp_path / "0002_broken.py"
        bad.write_text("def broken(:")

        with pytest.raises(ValueError) as exc_info:
            build_migration_graph(migrations_path=tmp_path, include_internal=False)

        assert "0002_broken" in str(exc_info.value)

    def test_error_includes_file_path(self, tmp_path):
        bad = tmp_path / "0003_broken.py"
        bad.write_text("def broken(:")

        with pytest.raises(ValueError) as exc_info:
            build_migration_graph(migrations_path=tmp_path, include_internal=False)

        assert str(tmp_path) in str(exc_info.value)

    def test_error_chains_original_exception(self, tmp_path):
        bad = tmp_path / "0001_bad.py"
        bad.write_text("import nonexistent_module_xyz")

        with pytest.raises(ValueError) as exc_info:
            build_migration_graph(migrations_path=tmp_path, include_internal=False)

        assert exc_info.value.__cause__ is not None

    def test_non_strict_does_not_raise(self, tmp_path):
        bad = tmp_path / "0001_bad.py"
        bad.write_text("def broken(:")

        # Should not raise; returns graph with the bad node dependency-less
        graph = build_migration_graph(
            migrations_path=tmp_path, include_internal=False, strict=False
        )
        assert len(graph) == 1

    def test_valid_migrations_build_graph_correctly(self, tmp_path):
        good = tmp_path / "0001_good.py"
        good.write_text(
            "from aksara.migrations.base import Migration\n"
            "from aksara.migrations import operations as op\n"
            "class Migration(Migration):\n"
            "    operations = []\n"
        )
        graph = build_migration_graph(migrations_path=tmp_path, include_internal=False)
        assert len(graph) == 1

    def test_sql_migration_load_error_is_not_raised(self, tmp_path):
        """SQL migrations are not loaded for deps — a bad SQL file should not raise."""
        sql = tmp_path / "0001_init.sql"
        sql.write_text("this is not valid SQL but we only read text, don't parse")

        # SQL migrations don't go through load_migration_module, so no error
        graph = build_migration_graph(migrations_path=tmp_path, include_internal=False)
        assert len(graph) == 1


# =============================================================================
# Fix 4: apply_migrations reports pending_skipped after failure
# =============================================================================

class TestPendingSkippedReporting:
    """Unit tests for pending_skipped in apply_migrations result."""

    def _make_conn(self):
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=True)
        conn.execute = AsyncMock()
        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        conn.transaction = MagicMock(return_value=tx)
        return conn

    def _make_py_file(self, tmp_path, name):
        f = tmp_path / f"{name}.py"
        f.write_text(
            "from aksara.migrations.base import Migration\n"
            "from aksara.migrations import operations as op\n"
            "class Migration(Migration):\n"
            "    operations = []\n"
        )
        return f

    @pytest.mark.asyncio
    async def test_no_failure_pending_skipped_empty(self, tmp_path):
        conn = self._make_conn()
        with patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock), \
             patch("aksara.migrations.executor.get_applied_migration_records",
                   new_callable=AsyncMock, return_value={}), \
             patch("aksara.migrations.executor.discover_all_migrations", return_value=[]), \
             patch("aksara.migrations.executor.get_pending_migrations", return_value=[]):
            result = await apply_migrations(conn, tmp_path, verbose=False)

        assert result["pending_skipped"] == []

    @pytest.mark.asyncio
    async def test_failure_in_first_skips_rest(self, tmp_path):
        f1 = self._make_py_file(tmp_path, "0001_a")
        f2 = self._make_py_file(tmp_path, "0002_b")
        f3 = self._make_py_file(tmp_path, "0003_c")
        migs = [("0001_a", f1), ("0002_b", f2), ("0003_c", f3)]

        conn = self._make_conn()

        async def _fail_first(conn, name, path, *, fake, verbose, ensure_table):
            if name == "0001_a":
                raise RuntimeError("first fails")

        with patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock), \
             patch("aksara.migrations.executor.get_applied_migration_records",
                   new_callable=AsyncMock, return_value={}), \
             patch("aksara.migrations.executor.discover_all_migrations", return_value=migs), \
             patch("aksara.migrations.executor.get_pending_migrations", return_value=migs), \
             patch("aksara.migrations.executor.build_migration_graph") as mock_graph, \
             patch("aksara.migrations.executor.apply_migration", side_effect=_fail_first):

            mock_nodes = [MagicMock(name=n) for n, _ in migs]
            for node, (n, _) in zip(mock_nodes, migs):
                node.name = n
            mock_graph.return_value.execution_order.return_value = mock_nodes

            result = await apply_migrations(conn, tmp_path, verbose=False)

        assert len(result["errors"]) == 1
        assert "0001_a" in result["errors"][0][0]
        assert "0002_b" in result["pending_skipped"]
        assert "0003_c" in result["pending_skipped"]
        assert "0001_a" not in result["pending_skipped"]

    @pytest.mark.asyncio
    async def test_failure_in_middle_skips_later(self, tmp_path):
        f1 = self._make_py_file(tmp_path, "0001_a")
        f2 = self._make_py_file(tmp_path, "0002_b")
        f3 = self._make_py_file(tmp_path, "0003_c")
        migs = [("0001_a", f1), ("0002_b", f2), ("0003_c", f3)]
        applied_migs = []

        conn = self._make_conn()

        async def _fail_second(conn, name, path, *, fake, verbose, ensure_table):
            if name == "0002_b":
                raise RuntimeError("second fails")
            applied_migs.append(name)

        with patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock), \
             patch("aksara.migrations.executor.get_applied_migration_records",
                   new_callable=AsyncMock, return_value={}), \
             patch("aksara.migrations.executor.discover_all_migrations", return_value=migs), \
             patch("aksara.migrations.executor.get_pending_migrations", return_value=migs), \
             patch("aksara.migrations.executor.build_migration_graph") as mock_graph, \
             patch("aksara.migrations.executor.apply_migration", side_effect=_fail_second):

            mock_nodes = [MagicMock() for n, _ in migs]
            for node, (n, _) in zip(mock_nodes, migs):
                node.name = n
            mock_graph.return_value.execution_order.return_value = mock_nodes

            result = await apply_migrations(conn, tmp_path, verbose=False)

        assert "0001_a" in result["applied"]
        assert len(result["errors"]) == 1
        assert "0002_b" in result["errors"][0][0]
        assert result["pending_skipped"] == ["0003_c"]
        assert "0003_c" not in applied_migs

    @pytest.mark.asyncio
    async def test_skipped_migrations_not_attempted(self, tmp_path):
        f1 = self._make_py_file(tmp_path, "0001_a")
        f2 = self._make_py_file(tmp_path, "0002_b")
        migs = [("0001_a", f1), ("0002_b", f2)]

        attempted = []
        conn = self._make_conn()

        async def _track_and_fail(conn, name, path, *, fake, verbose, ensure_table):
            attempted.append(name)
            if name == "0001_a":
                raise RuntimeError("fail")

        with patch("aksara.migrations.executor.ensure_migrations_table", new_callable=AsyncMock), \
             patch("aksara.migrations.executor.get_applied_migration_records",
                   new_callable=AsyncMock, return_value={}), \
             patch("aksara.migrations.executor.discover_all_migrations", return_value=migs), \
             patch("aksara.migrations.executor.get_pending_migrations", return_value=migs), \
             patch("aksara.migrations.executor.build_migration_graph") as mock_graph, \
             patch("aksara.migrations.executor.apply_migration", side_effect=_track_and_fail):

            mock_nodes = [MagicMock() for n, _ in migs]
            for node, (n, _) in zip(mock_nodes, migs):
                node.name = n
            mock_graph.return_value.execution_order.return_value = mock_nodes

            result = await apply_migrations(conn, tmp_path, verbose=False)

        assert "0002_b" not in attempted
        assert "0002_b" in result["pending_skipped"]
