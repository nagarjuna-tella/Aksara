"""
v0.5.50 P2-B Guardrails — Regression Tests

Covers:
  1. ManyToManyField constraint names are quoted and length-bounded
  2. IndexOp.where predicate validation
  3. ArrayField.sql_type validation
"""

import pytest

from aksara.migrations.operations import (
    ArrayField,
    IndexOp,
    ManyToManyField,
    _make_constraint_name,
    _validate_array_sql_type,
    _validate_sql_predicate,
)


# =============================================================================
# Task 1: _make_constraint_name helper
# =============================================================================

class TestMakeConstraintName:
    def test_short_name_unchanged(self):
        assert _make_constraint_name("fk", "users", "source") == "fk_users_source"

    def test_empty_parts_skipped(self):
        assert _make_constraint_name("fk", "", "target") == "fk_target"

    def test_exactly_63_chars_unchanged(self):
        part = "a" * 60
        name = _make_constraint_name(part)
        assert name == part
        assert len(name) == 60

    def test_64_char_name_gets_hash_suffix(self):
        part = "a" * 64
        name = _make_constraint_name(part)
        assert len(name.encode("utf-8")) <= 63
        assert "_" in name
        # suffix is last 8 chars after final underscore
        suffix = name.rsplit("_", 1)[-1]
        assert len(suffix) == 8

    def test_deterministic(self):
        name1 = _make_constraint_name("fk", "very_long_table_name_that_is_definitely_over_limit", "source")
        name2 = _make_constraint_name("fk", "very_long_table_name_that_is_definitely_over_limit", "source")
        assert name1 == name2

    def test_different_long_names_produce_different_results(self):
        long_a = "a" * 70
        long_b = "b" * 70
        name_a = _make_constraint_name(long_a)
        name_b = _make_constraint_name(long_b)
        assert name_a != name_b

    def test_custom_max_length(self):
        name = _make_constraint_name("fk", "table", "col", max_length=20)
        assert len(name.encode("utf-8")) <= 20

    def test_max_length_less_than_10_rejected(self):
        with pytest.raises(ValueError, match="at least 10"):
            _make_constraint_name("too", "short", max_length=9)

    def test_max_length_10_is_respected_for_long_input(self):
        name = _make_constraint_name("x" * 50, max_length=10)
        assert len(name.encode("utf-8")) <= 10

    def test_default_63_char_bound_still_applies(self):
        name = _make_constraint_name("x" * 100)
        assert len(name.encode("utf-8")) <= 63

    def test_ascii_long_name_fits_63_bytes(self):
        name = _make_constraint_name("ascii_" + ("x" * 100))
        assert len(name.encode("utf-8")) <= 63

    def test_non_ascii_name_under_byte_limit_returns_unchanged(self):
        part = "é" * 31
        name = _make_constraint_name(part)
        assert name == part
        assert len(name.encode("utf-8")) == 62

    def test_non_ascii_long_name_fits_63_bytes(self):
        name = _make_constraint_name("名" * 30)
        assert len(name.encode("utf-8")) <= 63
        assert "_" in name

    def test_non_ascii_truncation_does_not_split_character(self):
        name = _make_constraint_name("é" * 20, max_length=14)
        prefix, suffix = name.rsplit("_", 1)
        assert prefix == "éé"
        assert len(suffix) == 8
        assert len(name.encode("utf-8")) <= 14

    def test_non_ascii_max_length_10_fits_byte_budget(self):
        name = _make_constraint_name("é" * 20, max_length=10)
        assert len(name.encode("utf-8")) <= 10


class TestManyToManyFieldConstraintNames:
    def _get_sql(self, source="users", target="posts", field="liked_posts"):
        m2m = ManyToManyField(source, target, field)
        return m2m.get_join_table_sql()

    def test_constraint_names_are_quoted(self):
        sql = self._get_sql()
        # Each CONSTRAINT name should be double-quoted
        import re
        constraints = re.findall(r'CONSTRAINT\s+"([^"]+)"', sql)
        assert len(constraints) == 2, f"Expected 2 quoted constraints, got: {constraints}"

    def test_source_constraint_name_correct(self):
        sql = self._get_sql("users", "posts", "liked_posts")
        assert "fk_users_liked_posts_source" in sql

    def test_target_constraint_name_correct(self):
        sql = self._get_sql("users", "posts", "liked_posts")
        assert "fk_users_liked_posts_target" in sql

    def test_referenced_columns_are_quoted(self):
        sql = self._get_sql()
        # REFERENCES "users"("id") — column quoted
        assert 'REFERENCES "users"("id")' in sql or 'REFERENCES "posts"("id")' in sql

    def test_fk_columns_are_quoted(self):
        sql = self._get_sql()
        assert '"source_id"' in sql
        assert '"target_id"' in sql

    def test_long_table_name_constraint_fits_63_chars(self):
        long_table = "a" * 40
        long_field = "b" * 30
        m2m = ManyToManyField(long_table, "posts", long_field)
        sql = m2m.get_join_table_sql()
        import re
        constraints = re.findall(r'CONSTRAINT\s+"([^"]+)"', sql)
        for c in constraints:
            assert len(c) <= 63, f"Constraint name too long: {c!r}"

    def test_join_table_sql_has_expected_structure(self):
        sql = self._get_sql()
        assert "CREATE TABLE IF NOT EXISTS" in sql
        assert "PRIMARY KEY" in sql
        assert "ON DELETE CASCADE" in sql
        assert "UNIQUE" in sql


# =============================================================================
# Task 2: IndexOp.where predicate validation
# =============================================================================

class TestValidateSqlPredicate:
    def test_simple_predicate_passes(self):
        result = _validate_sql_predicate("active = true")
        assert result == "active = true"

    def test_comparison_predicate_passes(self):
        assert _validate_sql_predicate("status != 'deleted'") == "status != 'deleted'"

    def test_complex_but_safe_predicate_passes(self):
        assert _validate_sql_predicate("amount > 0 AND currency = 'USD'") is not None

    def test_semicolon_rejected(self):
        with pytest.raises(ValueError, match="semicolons"):
            _validate_sql_predicate("active = true; DROP TABLE users")

    def test_line_comment_rejected(self):
        with pytest.raises(ValueError, match="line comments"):
            _validate_sql_predicate("active = true -- bypass")

    def test_block_comment_open_rejected(self):
        with pytest.raises(ValueError, match="block comments"):
            _validate_sql_predicate("active = true /* inject */")

    def test_block_comment_close_rejected(self):
        with pytest.raises(ValueError, match="block comments"):
            _validate_sql_predicate("*/ active = true")

    def test_drop_keyword_rejected(self):
        with pytest.raises(ValueError, match="DROP"):
            _validate_sql_predicate("DROP TABLE users")

    def test_delete_keyword_rejected(self):
        with pytest.raises(ValueError, match="DELETE"):
            _validate_sql_predicate("DELETE FROM users")

    def test_insert_keyword_rejected(self):
        with pytest.raises(ValueError, match="INSERT"):
            _validate_sql_predicate("INSERT INTO x VALUES (1)")

    def test_update_keyword_rejected(self):
        with pytest.raises(ValueError, match="UPDATE"):
            _validate_sql_predicate("UPDATE users SET x=1")

    def test_create_keyword_rejected(self):
        with pytest.raises(ValueError, match="CREATE"):
            _validate_sql_predicate("CREATE TABLE evil (x int)")

    def test_truncate_keyword_rejected(self):
        with pytest.raises(ValueError, match="TRUNCATE"):
            _validate_sql_predicate("TRUNCATE users")

    def test_grant_keyword_rejected(self):
        with pytest.raises(ValueError, match="GRANT"):
            _validate_sql_predicate("GRANT ALL ON users TO attacker")

    def test_keyword_case_insensitive(self):
        with pytest.raises(ValueError, match="DROP"):
            _validate_sql_predicate("drop table users")

    def test_non_string_rejected(self):
        with pytest.raises(ValueError):
            _validate_sql_predicate(123)

    def test_column_named_created_at_passes(self):
        # "created" contains "CREATE" as substring but not as a whole word
        assert _validate_sql_predicate("created_at > NOW()") is not None

    def test_custom_context_in_error_message(self):
        with pytest.raises(ValueError, match="my_context"):
            _validate_sql_predicate("DROP TABLE x", context="my_context")

    def test_empty_string_rejected(self):
        with pytest.raises(ValueError, match="must not be empty"):
            _validate_sql_predicate("")

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValueError, match="must not be empty"):
            _validate_sql_predicate("   ")

    def test_predicate_is_stripped(self):
        assert _validate_sql_predicate(" status = 'active' ") == "status = 'active'"


class TestIndexOpWhereValidation:
    def test_valid_where_accepted(self):
        idx = IndexOp(name="idx_active", table="users", columns=["id"], where="active = true")
        assert idx.where == "active = true"

    def test_no_where_accepted(self):
        idx = IndexOp(name="idx_all", table="users", columns=["id"])
        assert idx.where is None

    def test_semicolon_in_where_raises(self):
        with pytest.raises(ValueError, match="semicolons"):
            IndexOp(name="idx_bad", table="users", columns=["id"], where="x=1; DROP TABLE users")

    def test_ddl_keyword_in_where_raises(self):
        with pytest.raises(ValueError, match="DROP"):
            IndexOp(name="idx_bad", table="users", columns=["id"], where="DROP TABLE users")

    def test_line_comment_in_where_raises(self):
        with pytest.raises(ValueError, match="line comments"):
            IndexOp(name="idx_bad", table="users", columns=["id"], where="1=1 -- bypass")

    def test_whitespace_only_where_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            IndexOp(name="idx_bad", table="users", columns=["id"], where="   ")

    def test_where_is_stripped(self):
        idx = IndexOp(
            name="idx_active",
            table="users",
            columns=["id"],
            where=" status = 'active' ",
        )
        assert idx.where == "status = 'active'"

    def test_other_params_unaffected(self):
        idx = IndexOp(
            name="idx_unique_email",
            table="users",
            columns=["email"],
            unique=True,
            where="email IS NOT NULL",
            method="btree",
        )
        assert idx.unique is True
        assert idx.method == "btree"
        assert "email IS NOT NULL" in idx.to_sql()


# =============================================================================
# Task 3: ArrayField.sql_type validation
# =============================================================================

class TestValidateArraySqlType:
    def test_text_array_passes(self):
        assert _validate_array_sql_type("TEXT[]") == "TEXT[]"

    def test_lowercase_normalised_to_uppercase(self):
        assert _validate_array_sql_type("text[]") == "TEXT[]"

    def test_integer_array_passes(self):
        assert _validate_array_sql_type("INTEGER[]") == "INTEGER[]"

    def test_uuid_array_passes(self):
        assert _validate_array_sql_type("UUID[]") == "UUID[]"

    def test_jsonb_array_passes(self):
        assert _validate_array_sql_type("JSONB[]") == "JSONB[]"

    def test_varchar_with_length_passes(self):
        assert _validate_array_sql_type("VARCHAR(255)[]") == "VARCHAR(255)[]"

    def test_numeric_with_precision_scale_passes(self):
        assert _validate_array_sql_type("NUMERIC(10,2)[]") == "NUMERIC(10,2)[]"

    def test_numeric_with_spaced_precision_scale_preserves_spacing(self):
        assert _validate_array_sql_type("numeric(10, 2)[]") == "NUMERIC(10, 2)[]"

    def test_decimal_with_precision_scale_passes(self):
        assert _validate_array_sql_type("DECIMAL(12,4)[]") == "DECIMAL(12,4)[]"

    def test_timestamp_with_time_zone_passes(self):
        assert _validate_array_sql_type("TIMESTAMP WITH TIME ZONE[]") == "TIMESTAMP WITH TIME ZONE[]"

    def test_missing_brackets_rejected(self):
        with pytest.raises(ValueError, match="must end with"):
            _validate_array_sql_type("TEXT")

    def test_empty_string_rejected(self):
        with pytest.raises(ValueError, match="non-empty string"):
            _validate_array_sql_type("")

    def test_none_rejected(self):
        with pytest.raises(ValueError):
            _validate_array_sql_type(None)

    def test_unknown_base_type_rejected(self):
        with pytest.raises(ValueError, match="unknown base type"):
            _validate_array_sql_type("EVIL[]")

    def test_semicolon_rejected(self):
        with pytest.raises(ValueError, match="unsafe characters"):
            _validate_array_sql_type("TEXT[]; DROP TABLE users")

    def test_double_quote_rejected(self):
        with pytest.raises(ValueError, match="unsafe characters"):
            _validate_array_sql_type('TEXT"[]')

    def test_ddl_keyword_rejected(self):
        with pytest.raises(ValueError, match="disallowed keyword"):
            _validate_array_sql_type("DROP[]")

    def test_bigint_array_passes(self):
        assert _validate_array_sql_type("BIGINT[]") == "BIGINT[]"

    def test_boolean_array_passes(self):
        assert _validate_array_sql_type("BOOLEAN[]") == "BOOLEAN[]"

    def test_numeric_array_passes(self):
        assert _validate_array_sql_type("NUMERIC[]") == "NUMERIC[]"

    def test_numeric_with_non_numeric_scale_rejected(self):
        with pytest.raises(ValueError, match="malformed length/precision"):
            _validate_array_sql_type("NUMERIC(10,x)[]")

    def test_numeric_with_too_many_args_rejected(self):
        with pytest.raises(ValueError, match="malformed length/precision"):
            _validate_array_sql_type("NUMERIC(10,2,3)[]")

    def test_numeric_with_unsafe_sql_rejected(self):
        with pytest.raises(ValueError, match="unsafe characters"):
            _validate_array_sql_type("NUMERIC(10); DROP TABLE x;--[]")


class TestArrayFieldSqlTypeValidation:
    def test_default_text_array_accepted(self):
        f = ArrayField()
        assert f.sql_type == "TEXT[]"

    def test_custom_valid_type_accepted(self):
        f = ArrayField(sql_type="INTEGER[]")
        assert f.sql_type == "INTEGER[]"

    def test_lowercase_normalised(self):
        f = ArrayField(sql_type="uuid[]")
        assert f.sql_type == "UUID[]"

    def test_numeric_precision_scale_accepted_at_construction(self):
        f = ArrayField(sql_type="numeric(10,2)[]")
        assert f.sql_type == "NUMERIC(10,2)[]"

    def test_invalid_type_raises_at_construction(self):
        with pytest.raises(ValueError):
            ArrayField(sql_type="EVIL[]")

    def test_missing_brackets_raises_at_construction(self):
        with pytest.raises(ValueError, match="must end with"):
            ArrayField(sql_type="TEXT")

    def test_sql_injection_raises_at_construction(self):
        with pytest.raises(ValueError):
            ArrayField(sql_type="TEXT[]; DROP TABLE users")

    def test_nullable_and_default_still_work(self):
        f = ArrayField(sql_type="JSONB[]", nullable=False, default=[])
        assert f.nullable is False
        assert f.default == []
