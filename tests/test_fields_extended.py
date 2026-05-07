"""
Tests for extended field types added for Django parity.

Covers: Slug, SmallInteger, BigInteger, PositiveInteger,
        PositiveSmallInteger, PositiveBigInteger, Time,
        Duration, IPAddress (+ GenericIPAddressField alias),
        Binary, FilePath.
"""

import os
import re
import tempfile
from datetime import datetime, time as py_time, timedelta

import pytest

from aksara.fields import (
    BigInteger,
    BigIntegerField,
    Binary,
    BinaryField,
    Duration,
    DurationField,
    FilePath,
    FilePathField,
    GenericIPAddressField,
    IPAddress,
    IPAddressField,
    PositiveBigInteger,
    PositiveBigIntegerField,
    PositiveInteger,
    PositiveIntegerField,
    PositiveSmallInteger,
    PositiveSmallIntegerField,
    Slug,
    SlugField,
    SmallInteger,
    SmallIntegerField,
    Time,
    TimeField,
)


# =============================================================================
# SlugField
# =============================================================================


class TestSlugField:
    """Tests for Slug / SlugField."""

    def test_alias(self):
        assert SlugField is Slug

    def test_sql_type(self):
        f = Slug()
        assert f.sql_type == "VARCHAR(50)"

    def test_sql_type_custom_length(self):
        f = Slug(max_length=200)
        assert f.sql_type == "VARCHAR(200)"

    def test_valid_slug(self):
        f = Slug()
        assert f.to_db("hello-world_123") == "hello-world_123"

    def test_valid_slug_passthrough(self):
        f = Slug()
        assert f.to_python("my-slug") == "my-slug"

    def test_invalid_slug_raises(self):
        f = Slug()
        with pytest.raises(ValueError, match="Invalid slug"):
            f.to_db("Hello World!")

    def test_slug_with_spaces_raises(self):
        f = Slug()
        with pytest.raises(ValueError, match="Invalid slug"):
            f.to_db("hello world")

    def test_slug_none(self):
        f = Slug(nullable=True)
        assert f.to_db(None) is None
        assert f.to_python(None) is None

    def test_slug_unicode_disallowed_by_default(self):
        f = Slug()
        with pytest.raises(ValueError, match="Invalid slug"):
            f.to_db("héllo-wörld")

    def test_slug_unicode_allowed(self):
        f = Slug(allow_unicode=True)
        assert f.to_db("héllo-wörld") == "héllo-wörld"

    def test_slug_default_metadata(self):
        f = Slug(ai_description="URL slug")
        assert f.ai_description == "URL slug"

    def test_slug_unique(self):
        f = Slug(unique=True)
        assert f.unique is True


# =============================================================================
# SmallIntegerField
# =============================================================================


class TestSmallIntegerField:
    """Tests for SmallInteger / SmallIntegerField."""

    def test_alias(self):
        assert SmallIntegerField is SmallInteger

    def test_sql_type(self):
        assert SmallInteger().sql_type == "SMALLINT"

    def test_valid_min(self):
        f = SmallInteger()
        assert f.to_db(-32768) == -32768

    def test_valid_max(self):
        f = SmallInteger()
        assert f.to_db(32767) == 32767

    def test_overflow_raises(self):
        f = SmallInteger()
        with pytest.raises(ValueError):
            f.to_db(32768)

    def test_underflow_raises(self):
        f = SmallInteger()
        with pytest.raises(ValueError):
            f.to_db(-32769)

    def test_none(self):
        f = SmallInteger(nullable=True)
        assert f.to_db(None) is None
        assert f.to_python(None) is None

    def test_string_conversion(self):
        f = SmallInteger()
        assert f.to_python("42") == 42


# =============================================================================
# BigIntegerField
# =============================================================================


class TestBigIntegerField:
    """Tests for BigInteger / BigIntegerField."""

    def test_alias(self):
        assert BigIntegerField is BigInteger

    def test_sql_type(self):
        assert BigInteger().sql_type == "BIGINT"

    def test_valid_min(self):
        f = BigInteger()
        val = -(2**63)
        assert f.to_db(val) == val

    def test_valid_max(self):
        f = BigInteger()
        val = 2**63 - 1
        assert f.to_db(val) == val

    def test_overflow_raises(self):
        f = BigInteger()
        with pytest.raises(ValueError, match="out of BIGINT range"):
            f.to_db(2**63)

    def test_underflow_raises(self):
        f = BigInteger()
        with pytest.raises(ValueError, match="out of BIGINT range"):
            f.to_db(-(2**63) - 1)

    def test_none(self):
        f = BigInteger(nullable=True)
        assert f.to_db(None) is None

    def test_to_python(self):
        f = BigInteger()
        assert f.to_python("9999999999999") == 9999999999999


# =============================================================================
# PositiveIntegerField
# =============================================================================


class TestPositiveIntegerField:
    """Tests for PositiveInteger / PositiveIntegerField."""

    def test_alias(self):
        assert PositiveIntegerField is PositiveInteger

    def test_sql_type(self):
        assert PositiveInteger().sql_type == "INTEGER"

    def test_accepts_zero(self):
        f = PositiveInteger()
        assert f.to_db(0) == 0

    def test_accepts_positive(self):
        f = PositiveInteger()
        assert f.to_db(42) == 42

    def test_rejects_negative(self):
        f = PositiveInteger()
        with pytest.raises(ValueError, match="non-negative"):
            f.to_db(-1)

    def test_none(self):
        f = PositiveInteger(nullable=True)
        assert f.to_db(None) is None


# =============================================================================
# PositiveSmallIntegerField
# =============================================================================


class TestPositiveSmallIntegerField:
    """Tests for PositiveSmallInteger / PositiveSmallIntegerField."""

    def test_alias(self):
        assert PositiveSmallIntegerField is PositiveSmallInteger

    def test_sql_type(self):
        assert PositiveSmallInteger().sql_type == "SMALLINT"

    def test_accepts_zero(self):
        f = PositiveSmallInteger()
        assert f.to_db(0) == 0

    def test_accepts_max(self):
        f = PositiveSmallInteger()
        assert f.to_db(32767) == 32767

    def test_rejects_negative(self):
        f = PositiveSmallInteger()
        with pytest.raises(ValueError, match="out of POSITIVE SMALLINT range"):
            f.to_db(-1)

    def test_rejects_overflow(self):
        f = PositiveSmallInteger()
        with pytest.raises(ValueError, match="out of POSITIVE SMALLINT range"):
            f.to_db(32768)

    def test_none(self):
        f = PositiveSmallInteger(nullable=True)
        assert f.to_db(None) is None


# =============================================================================
# PositiveBigIntegerField
# =============================================================================


class TestPositiveBigIntegerField:
    """Tests for PositiveBigInteger / PositiveBigIntegerField."""

    def test_alias(self):
        assert PositiveBigIntegerField is PositiveBigInteger

    def test_sql_type(self):
        assert PositiveBigInteger().sql_type == "BIGINT"

    def test_accepts_zero(self):
        f = PositiveBigInteger()
        assert f.to_db(0) == 0

    def test_accepts_large_positive(self):
        f = PositiveBigInteger()
        assert f.to_db(2**62) == 2**62

    def test_rejects_negative(self):
        f = PositiveBigInteger()
        with pytest.raises(ValueError, match="non-negative"):
            f.to_db(-1)

    def test_none(self):
        f = PositiveBigInteger(nullable=True)
        assert f.to_db(None) is None


# =============================================================================
# TimeField
# =============================================================================


class TestTimeField:
    """Tests for Time / TimeField."""

    def test_alias(self):
        assert TimeField is Time

    def test_sql_type(self):
        assert Time().sql_type == "TIME"

    def test_time_passthrough(self):
        f = Time()
        t = py_time(14, 30, 0)
        assert f.to_python(t) is t
        assert f.to_db(t) is t

    def test_string_hms(self):
        f = Time()
        result = f.to_python("14:30:00")
        assert result == py_time(14, 30, 0)

    def test_string_with_microseconds(self):
        f = Time()
        result = f.to_python("14:30:00.123456")
        assert result == py_time(14, 30, 0, 123456)

    def test_datetime_to_time(self):
        f = Time()
        dt = datetime(2025, 1, 1, 14, 30, 0)
        assert f.to_python(dt) == py_time(14, 30, 0)

    def test_to_db_string(self):
        f = Time()
        result = f.to_db("09:15:30")
        assert result == py_time(9, 15, 30)

    def test_to_db_datetime(self):
        f = Time()
        dt = datetime(2025, 6, 15, 22, 0, 45)
        assert f.to_db(dt) == py_time(22, 0, 45)

    def test_none(self):
        f = Time(nullable=True)
        assert f.to_python(None) is None
        assert f.to_db(None) is None


# =============================================================================
# DurationField
# =============================================================================


class TestDurationField:
    """Tests for Duration / DurationField."""

    def test_alias(self):
        assert DurationField is Duration

    def test_sql_type(self):
        assert Duration().sql_type == "INTERVAL"

    def test_timedelta_passthrough(self):
        f = Duration()
        td = timedelta(hours=1, minutes=30)
        assert f.to_python(td) is td

    def test_int_seconds(self):
        f = Duration()
        result = f.to_python(3600)
        assert result == timedelta(seconds=3600)

    def test_float_seconds(self):
        f = Duration()
        result = f.to_python(90.5)
        assert result == timedelta(seconds=90.5)

    def test_to_db_timedelta(self):
        f = Duration()
        td = timedelta(days=30)
        assert f.to_db(td) is td

    def test_to_db_int(self):
        f = Duration()
        result = f.to_db(7200)
        assert result == timedelta(seconds=7200)

    def test_none(self):
        f = Duration(nullable=True)
        assert f.to_python(None) is None
        assert f.to_db(None) is None


# =============================================================================
# IPAddressField / GenericIPAddressField
# =============================================================================


class TestIPAddressField:
    """Tests for IPAddress / IPAddressField / GenericIPAddressField."""

    def test_aliases(self):
        assert IPAddressField is IPAddress
        assert GenericIPAddressField is IPAddress

    def test_sql_type(self):
        assert IPAddress().sql_type == "INET"

    def test_valid_ipv4(self):
        f = IPAddress()
        assert f.to_db("192.168.1.1") == "192.168.1.1"

    def test_valid_ipv6(self):
        f = IPAddress()
        result = f.to_db("::1")
        assert result == "::1"

    def test_invalid_ip_raises(self):
        f = IPAddress()
        with pytest.raises(ValueError, match="Invalid IP address"):
            f.to_db("not-an-ip")

    def test_ipv4_only_rejects_ipv6(self):
        f = IPAddress(protocol="ipv4")
        with pytest.raises(ValueError, match="Expected an IPv4"):
            f.to_db("::1")

    def test_ipv6_only_rejects_ipv4(self):
        f = IPAddress(protocol="ipv6")
        with pytest.raises(ValueError, match="Expected an IPv6"):
            f.to_db("192.168.1.1")

    def test_unpack_ipv4(self):
        f = IPAddress(unpack_ipv4=True)
        result = f.to_db("::ffff:192.0.2.1")
        assert result == "192.0.2.1"

    def test_to_python_normalizes(self):
        """to_python should normalize through ipaddress for consistent output."""
        f = IPAddress()
        # Standard IPs round-trip cleanly
        assert f.to_python("192.168.1.1") == "192.168.1.1"
        assert f.to_python("::1") == "::1"

    def test_to_python_invalid_falls_back(self):
        """to_python should return str(value) if parsing fails."""
        f = IPAddress()
        assert f.to_python("not-ip") == "not-ip"

    def test_none(self):
        f = IPAddress(nullable=True)
        assert f.to_db(None) is None
        assert f.to_python(None) is None

    def test_invalid_protocol_raises(self):
        with pytest.raises(ValueError, match="protocol"):
            IPAddress(protocol="tcp")


# =============================================================================
# BinaryField
# =============================================================================


class TestBinaryField:
    """Tests for Binary / BinaryField."""

    def test_alias(self):
        assert BinaryField is Binary

    def test_sql_type(self):
        assert Binary().sql_type == "BYTEA"

    def test_bytes_passthrough(self):
        f = Binary()
        data = b"\x00\x01\x02"
        assert f.to_db(data) == data

    def test_bytearray_conversion(self):
        f = Binary()
        data = bytearray(b"\x03\x04")
        result = f.to_db(data)
        assert isinstance(result, bytes)
        assert result == b"\x03\x04"

    def test_memoryview_conversion(self):
        f = Binary()
        data = memoryview(b"\x05\x06")
        result = f.to_db(data)
        assert isinstance(result, bytes)
        assert result == b"\x05\x06"

    def test_string_utf8(self):
        f = Binary()
        result = f.to_db("hello")
        assert result == b"hello"

    def test_to_python_bytes(self):
        f = Binary()
        assert f.to_python(b"\xff") == b"\xff"

    def test_none(self):
        f = Binary(nullable=True)
        assert f.to_db(None) is None
        assert f.to_python(None) is None

    def test_default_ai_sensitive(self):
        """Binary fields default to ai_sensitive=True."""
        f = Binary()
        assert f.ai_sensitive is True

    def test_default_ai_agent_writable(self):
        """Binary fields default to ai_agent_writable=False."""
        f = Binary()
        assert f.ai_agent_writable is False


# =============================================================================
# FilePathField
# =============================================================================


class TestFilePathField:
    """Tests for FilePath / FilePathField."""

    def test_alias(self):
        assert FilePathField is FilePath

    def test_sql_type(self):
        f = FilePath()
        assert f.sql_type == "VARCHAR(100)"

    def test_sql_type_custom_length(self):
        f = FilePath(max_length=500)
        assert f.sql_type == "VARCHAR(500)"

    def test_to_python(self):
        f = FilePath()
        assert f.to_python("/tmp/file.txt") == "/tmp/file.txt"

    def test_to_db(self):
        f = FilePath()
        assert f.to_db("/tmp/file.txt") == "/tmp/file.txt"

    def test_none(self):
        f = FilePath(nullable=True)
        assert f.to_python(None) is None
        assert f.to_db(None) is None

    def test_choices_empty_path(self):
        f = FilePath(path="")
        assert f.choices() == []

    def test_choices_nonexistent_path(self):
        f = FilePath(path="/nonexistent/path/xyz123")
        assert f.choices() == []

    def test_choices_lists_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            open(os.path.join(tmpdir, "a.txt"), "w").close()
            open(os.path.join(tmpdir, "b.py"), "w").close()

            f = FilePath(path=tmpdir)
            result = f.choices()
            paths = [p for p, _ in result]
            assert os.path.join(tmpdir, "a.txt") in paths
            assert os.path.join(tmpdir, "b.py") in paths

    def test_choices_match_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "a.txt"), "w").close()
            open(os.path.join(tmpdir, "b.py"), "w").close()

            f = FilePath(path=tmpdir, match=r".*\.txt$")
            result = f.choices()
            paths = [p for p, _ in result]
            assert os.path.join(tmpdir, "a.txt") in paths
            assert os.path.join(tmpdir, "b.py") not in paths

    def test_choices_allow_folders(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "subdir"))
            open(os.path.join(tmpdir, "file.txt"), "w").close()

            f = FilePath(path=tmpdir, allow_files=False, allow_folders=True)
            result = f.choices()
            paths = [p for p, _ in result]
            assert os.path.join(tmpdir, "subdir") in paths
            assert os.path.join(tmpdir, "file.txt") not in paths

    def test_choices_recursive_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "sub"))
            open(os.path.join(tmpdir, "top.txt"), "w").close()
            open(os.path.join(tmpdir, "sub", "nested.txt"), "w").close()

            f = FilePath(path=tmpdir, recursive=True)
            result = f.choices()
            paths = [p for p, _ in result]
            assert os.path.join(tmpdir, "top.txt") in paths
            assert os.path.join(tmpdir, "sub", "nested.txt") in paths

    def test_choices_recursive_folders(self):
        """Recursive mode should include directories when allow_folders=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "sub"))
            open(os.path.join(tmpdir, "file.txt"), "w").close()

            f = FilePath(
                path=tmpdir, recursive=True, allow_files=False, allow_folders=True
            )
            result = f.choices()
            paths = [p for p, _ in result]
            assert os.path.join(tmpdir, "sub") in paths
            # files should not be included
            assert os.path.join(tmpdir, "file.txt") not in paths

    def test_choices_recursive_match_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "sub"))
            open(os.path.join(tmpdir, "a.txt"), "w").close()
            open(os.path.join(tmpdir, "sub", "b.py"), "w").close()
            open(os.path.join(tmpdir, "sub", "c.txt"), "w").close()

            f = FilePath(path=tmpdir, recursive=True, match=r".*\.txt$")
            result = f.choices()
            paths = [p for p, _ in result]
            assert os.path.join(tmpdir, "a.txt") in paths
            assert os.path.join(tmpdir, "sub", "c.txt") in paths
            assert os.path.join(tmpdir, "sub", "b.py") not in paths


# =============================================================================
# Migration FieldOp Integration
# =============================================================================


class TestMigrationOps:
    """Verify that migration FieldOps produce correct SQL."""

    def test_small_integer_sql(self):
        from aksara.migrations.operations import SmallIntegerField as SmallIntOp

        assert SmallIntOp().to_sql() == "SMALLINT NOT NULL"
        assert SmallIntOp(nullable=True, default=0).to_sql() == "SMALLINT DEFAULT 0"

    def test_slug_sql(self):
        from aksara.migrations.operations import SlugField as SlugOp

        assert SlugOp().to_sql() == "VARCHAR(50) NOT NULL"
        assert SlugOp(max_length=100, unique=True).to_sql() == "VARCHAR(100) NOT NULL UNIQUE"

    def test_time_sql(self):
        from aksara.migrations.operations import TimeField as TimeOp

        assert TimeOp().to_sql() == "TIME NOT NULL"
        assert TimeOp(nullable=True).to_sql() == "TIME"

    def test_duration_sql(self):
        from aksara.migrations.operations import DurationField as DurOp

        assert DurOp().to_sql() == "INTERVAL NOT NULL"
        assert DurOp(nullable=True).to_sql() == "INTERVAL"

    def test_ip_address_sql(self):
        from aksara.migrations.operations import IPAddressField as IPOp

        assert IPOp().to_sql() == "INET NOT NULL"
        assert IPOp(nullable=True, unique=True).to_sql() == "INET UNIQUE"

    def test_binary_sql(self):
        from aksara.migrations.operations import BinaryField as BinOp

        assert BinOp().to_sql() == "BYTEA NOT NULL"
        assert BinOp(nullable=True).to_sql() == "BYTEA"

    def test_filepath_sql(self):
        from aksara.migrations.operations import FilePathField as FPOp

        assert FPOp().to_sql() == "VARCHAR(100) NOT NULL"
        assert FPOp(max_length=255, nullable=True).to_sql() == "VARCHAR(255)"


class TestAutodetectorMapping:
    """Verify that the autodetector maps runtime fields to correct FieldOps."""

    def test_slug_maps_to_slug_op(self):
        from aksara.migrations.autodetector import _model_field_to_op
        from aksara.migrations.operations import SlugField as SlugOp

        result = _model_field_to_op("slug", Slug(max_length=80, unique=True))
        assert isinstance(result, SlugOp)
        assert result.max_length == 80
        assert result.unique is True

    def test_small_integer_maps(self):
        from aksara.migrations.autodetector import _model_field_to_op
        from aksara.migrations.operations import SmallIntegerField as SmallIntOp

        result = _model_field_to_op("x", SmallInteger())
        assert isinstance(result, SmallIntOp)

    def test_time_maps(self):
        from aksara.migrations.autodetector import _model_field_to_op
        from aksara.migrations.operations import TimeField as TimeOp

        result = _model_field_to_op("t", Time(nullable=True))
        assert isinstance(result, TimeOp)
        assert result.nullable is True

    def test_duration_maps(self):
        from aksara.migrations.autodetector import _model_field_to_op
        from aksara.migrations.operations import DurationField as DurOp

        result = _model_field_to_op("d", Duration())
        assert isinstance(result, DurOp)

    def test_ip_address_maps(self):
        from aksara.migrations.autodetector import _model_field_to_op
        from aksara.migrations.operations import IPAddressField as IPOp

        result = _model_field_to_op("ip", IPAddress())
        assert isinstance(result, IPOp)

    def test_binary_maps(self):
        from aksara.migrations.autodetector import _model_field_to_op
        from aksara.migrations.operations import BinaryField as BinOp

        result = _model_field_to_op("data", Binary())
        assert isinstance(result, BinOp)

    def test_filepath_maps(self):
        from aksara.migrations.autodetector import _model_field_to_op
        from aksara.migrations.operations import FilePathField as FPOp

        result = _model_field_to_op("fp", FilePath(max_length=200))
        assert isinstance(result, FPOp)
        assert result.max_length == 200

    def test_positive_integer_maps_to_integer(self):
        from aksara.migrations.autodetector import _model_field_to_op
        from aksara.migrations.operations import IntegerField as IntOp

        result = _model_field_to_op("x", PositiveInteger())
        assert isinstance(result, IntOp)

    def test_positive_big_integer_maps_to_bigint(self):
        from aksara.migrations.autodetector import _model_field_to_op
        from aksara.migrations.operations import BigIntegerField as BigIntOp

        result = _model_field_to_op("x", PositiveBigInteger())
        assert isinstance(result, BigIntOp)

    def test_positive_small_integer_maps_to_smallint(self):
        from aksara.migrations.autodetector import _model_field_to_op
        from aksara.migrations.operations import SmallIntegerField as SmallIntOp

        result = _model_field_to_op("x", PositiveSmallInteger())
        assert isinstance(result, SmallIntOp)
