"""
Tests for SQL codegen sanitization helpers.

v0.5.40: sanitize_identifier() and sanitize_column_type() coverage.
"""

from __future__ import annotations

import pytest


class TestSanitizeIdentifierImport:
    def test_import(self):
        from aksara.ai.codegen import sanitize_identifier
        assert callable(sanitize_identifier)


class TestSanitizeIdentifier:
    def test_valid_simple_name(self):
        from aksara.ai.codegen import sanitize_identifier
        assert sanitize_identifier("user_id") == "user_id"

    def test_valid_starts_with_underscore(self):
        from aksara.ai.codegen import sanitize_identifier
        assert sanitize_identifier("_private") == "_private"

    def test_valid_mixed_case(self):
        from aksara.ai.codegen import sanitize_identifier
        assert sanitize_identifier("MyTable") == "MyTable"

    def test_empty_raises(self):
        from aksara.ai.codegen import sanitize_identifier
        with pytest.raises(ValueError, match="empty"):
            sanitize_identifier("")

    def test_sql_injection_semicolon_raises(self):
        from aksara.ai.codegen import sanitize_identifier
        with pytest.raises(ValueError):
            sanitize_identifier("users; DROP TABLE users--")

    def test_hyphen_raises(self):
        from aksara.ai.codegen import sanitize_identifier
        with pytest.raises(ValueError):
            sanitize_identifier("my-table")

    def test_space_raises(self):
        from aksara.ai.codegen import sanitize_identifier
        with pytest.raises(ValueError):
            sanitize_identifier("my table")

    def test_starts_with_digit_raises(self):
        from aksara.ai.codegen import sanitize_identifier
        with pytest.raises(ValueError):
            sanitize_identifier("1table")

    def test_dollar_sign_raises(self):
        from aksara.ai.codegen import sanitize_identifier
        with pytest.raises(ValueError):
            sanitize_identifier("table$name")


class TestSanitizeColumnTypeImport:
    def test_import(self):
        from aksara.ai.codegen import sanitize_column_type
        assert callable(sanitize_column_type)


class TestSanitizeColumnType:
    def test_text(self):
        from aksara.ai.codegen import sanitize_column_type
        assert sanitize_column_type("TEXT") == "TEXT"

    def test_varchar_with_length(self):
        from aksara.ai.codegen import sanitize_column_type
        assert sanitize_column_type("VARCHAR(255)") == "VARCHAR(255)"

    def test_integer(self):
        from aksara.ai.codegen import sanitize_column_type
        assert sanitize_column_type("INTEGER") == "INTEGER"

    def test_boolean(self):
        from aksara.ai.codegen import sanitize_column_type
        assert sanitize_column_type("BOOLEAN") == "BOOLEAN"

    def test_jsonb(self):
        from aksara.ai.codegen import sanitize_column_type
        assert sanitize_column_type("JSONB") == "JSONB"

    def test_uuid(self):
        from aksara.ai.codegen import sanitize_column_type
        assert sanitize_column_type("UUID") == "UUID"

    def test_numeric_with_precision(self):
        from aksara.ai.codegen import sanitize_column_type
        assert sanitize_column_type("NUMERIC(10,2)") == "NUMERIC(10,2)"

    def test_timestamp(self):
        from aksara.ai.codegen import sanitize_column_type
        assert sanitize_column_type("TIMESTAMP") == "TIMESTAMP"

    def test_lowercase_accepted(self):
        from aksara.ai.codegen import sanitize_column_type
        assert sanitize_column_type("text") == "text"

    def test_empty_raises(self):
        from aksara.ai.codegen import sanitize_column_type
        with pytest.raises(ValueError, match="empty"):
            sanitize_column_type("")

    def test_injection_type_raises(self):
        from aksara.ai.codegen import sanitize_column_type
        with pytest.raises(ValueError):
            sanitize_column_type("TEXT; DROP TABLE users--")

    def test_unknown_type_raises(self):
        from aksara.ai.codegen import sanitize_column_type
        with pytest.raises(ValueError):
            sanitize_column_type("CURSOR")

    def test_custom_type_raises(self):
        from aksara.ai.codegen import sanitize_column_type
        with pytest.raises(ValueError):
            sanitize_column_type("my_custom_type")
