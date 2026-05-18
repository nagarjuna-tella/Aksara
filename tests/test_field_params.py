"""
Tests for field parameter enhancements.

Covers: choices, min_length, min_value/max_value, auto_slug (_slugify),
        regex, and strip_whitespace across String, Text, Integer,
        SmallInteger, Float, Decimal, and Slug.
"""

import asyncio
from decimal import Decimal as PyDecimal
from types import SimpleNamespace

import pytest

from aksara.fields import (
    Decimal,
    Float,
    Integer,
    Slug,
    SmallInteger,
    String,
    Text,
    _normalize_choices,
    _slugify,
)


# =============================================================================
# _normalize_choices helper
# =============================================================================


class TestNormalizeChoices:
    """Unit tests for the _normalize_choices() helper."""

    def test_none_returns_none(self):
        assert _normalize_choices(None) is None

    def test_empty_list_returns_none(self):
        assert _normalize_choices([]) is None

    def test_flat_list(self):
        result = _normalize_choices(["a", "b", "c"])
        assert result == {"a", "b", "c"}

    def test_tuple_pair_list(self):
        result = _normalize_choices([("a", "Label A"), ("b", "Label B")])
        assert result == {"a", "b"}

    def test_mixed_format(self):
        """Flat items and tuple pairs in the same list."""
        result = _normalize_choices(["x", ("y", "Label Y")])
        assert result == {"x", "y"}

    def test_integer_choices(self):
        result = _normalize_choices([1, 2, 3])
        assert result == {1, 2, 3}


# =============================================================================
# _slugify helper
# =============================================================================


class TestSlugify:
    """Unit tests for the _slugify() helper."""

    def test_basic_title(self):
        assert _slugify("Hello World") == "hello-world"

    def test_special_characters(self):
        assert _slugify("Hello, World! (2025)") == "hello-world-2025"

    def test_leading_trailing_whitespace(self):
        assert _slugify("  Hello World  ") == "hello-world"

    def test_consecutive_hyphens_collapsed(self):
        assert _slugify("Hello -- World") == "hello-world"

    def test_leading_trailing_hyphens_stripped(self):
        assert _slugify("--hello--") == "hello"

    def test_unicode_stripped_by_default(self):
        result = _slugify("Héllo Wörld")
        assert result == "hllo-wrld" or result == "hello-world"  # depends on transliteration

    def test_unicode_allowed(self):
        result = _slugify("Héllo Wörld", allow_unicode=True)
        assert "héllo" in result
        assert "wörld" in result

    def test_already_slug(self):
        assert _slugify("hello-world") == "hello-world"

    def test_empty_string(self):
        assert _slugify("") == ""

    def test_underscores_preserved(self):
        assert _slugify("hello_world") == "hello_world"


# =============================================================================
# String choices
# =============================================================================


class TestStringChoices:
    """Tests for choices parameter on String field."""

    def test_valid_choice_accepted(self):
        f = String(max_length=20, choices=["low", "medium", "high"])
        assert f.to_db("medium") == "medium"

    def test_invalid_choice_raises(self):
        f = String(max_length=20, choices=["low", "medium", "high"])
        with pytest.raises(ValueError, match="not a valid choice"):
            f.to_db("critical")

    def test_none_bypasses_validation(self):
        f = String(max_length=20, choices=["low", "medium"], nullable=True)
        assert f.to_db(None) is None

    def test_empty_choices_no_validation(self):
        f = String(max_length=20, choices=[])
        assert f.to_db("anything") == "anything"

    def test_tuple_pair_format(self):
        f = String(
            max_length=20,
            choices=[("low", "Low Priority"), ("high", "High Priority")],
        )
        assert f.to_db("low") == "low"
        with pytest.raises(ValueError, match="not a valid choice"):
            f.to_db("Low Priority")  # display label, not the value

    def test_choices_in_ai_metadata(self):
        choices = ["low", "medium", "high"]
        f = String(max_length=20, choices=choices)
        f.name = "severity"
        meta = f.get_ai_metadata()
        assert meta["choices"] == choices

    def test_no_choices_not_in_metadata(self):
        f = String(max_length=20)
        f.name = "name"
        meta = f.get_ai_metadata()
        assert "choices" not in meta


# =============================================================================
# String min_length
# =============================================================================


class TestStringMinLength:
    """Tests for min_length parameter on String field."""

    def test_below_min_raises(self):
        f = String(max_length=128, min_length=8)
        with pytest.raises(ValueError, match="too short"):
            f.to_db("abc")

    def test_at_min_passes(self):
        f = String(max_length=128, min_length=8)
        assert f.to_db("12345678") == "12345678"

    def test_above_min_passes(self):
        f = String(max_length=128, min_length=8)
        assert f.to_db("abcdefghij") == "abcdefghij"

    def test_none_bypasses_validation(self):
        f = String(max_length=128, min_length=8, nullable=True)
        assert f.to_db(None) is None

    def test_min_length_in_metadata(self):
        f = String(max_length=128, min_length=8)
        f.name = "password"
        meta = f.get_ai_metadata()
        assert meta["min_length"] == 8


# =============================================================================
# String regex
# =============================================================================


class TestStringRegex:
    """Tests for regex parameter on String field."""

    def test_matching_value_passes(self):
        f = String(max_length=20, regex=r"^[A-Z]{3}-\d{3}$")
        assert f.to_db("ABC-123") == "ABC-123"

    def test_non_matching_raises(self):
        f = String(max_length=20, regex=r"^[A-Z]{3}-\d{3}$")
        with pytest.raises(ValueError, match="does not match"):
            f.to_db("abc-12")

    def test_none_bypasses_validation(self):
        f = String(max_length=20, regex=r"^\d+$", nullable=True)
        assert f.to_db(None) is None

    def test_phone_pattern(self):
        f = String(max_length=20, regex=r"^\+?[\d\s\-]{7,15}$")
        assert f.to_db("+1 555-1234") == "+1 555-1234"
        with pytest.raises(ValueError, match="does not match"):
            f.to_db("abc")

    def test_regex_in_metadata(self):
        f = String(max_length=20, regex=r"^\d{4}$")
        f.name = "code"
        meta = f.get_ai_metadata()
        assert meta["regex"] == r"^\d{4}$"

    def test_no_regex_not_in_metadata(self):
        f = String(max_length=20)
        f.name = "name"
        meta = f.get_ai_metadata()
        assert "regex" not in meta


# =============================================================================
# String strip_whitespace
# =============================================================================


class TestStringStripWhitespace:
    """Tests for strip_whitespace parameter on String field."""

    def test_strips_leading_trailing(self):
        f = String(max_length=100, strip_whitespace=True)
        assert f.to_db("  hello  ") == "hello"

    def test_preserves_internal_whitespace(self):
        f = String(max_length=100, strip_whitespace=True)
        assert f.to_db("  hello world  ") == "hello world"

    def test_disabled_by_default(self):
        f = String(max_length=100)
        assert f.to_db("  hello  ") == "  hello  "

    def test_strip_then_min_length(self):
        """Stripping happens before min_length validation."""
        f = String(max_length=100, strip_whitespace=True, min_length=5)
        with pytest.raises(ValueError, match="too short"):
            f.to_db("  ab  ")  # stripped to "ab" (2 chars)

    def test_strip_then_choices(self):
        """Stripping happens before choices validation."""
        f = String(max_length=20, strip_whitespace=True, choices=["yes", "no"])
        assert f.to_db("  yes  ") == "yes"


# =============================================================================
# Text min_length
# =============================================================================


class TestTextMinLength:
    """Tests for min_length parameter on Text field."""

    def test_below_min_raises(self):
        f = Text(min_length=10)
        with pytest.raises(ValueError, match="too short"):
            f.to_db("short")

    def test_at_min_passes(self):
        f = Text(min_length=5)
        assert f.to_db("12345") == "12345"

    def test_none_bypasses(self):
        f = Text(min_length=10, nullable=True)
        assert f.to_db(None) is None

    def test_min_length_in_metadata(self):
        f = Text(min_length=50)
        f.name = "content"
        meta = f.get_ai_metadata()
        assert meta["min_length"] == 50


# =============================================================================
# Text strip_whitespace
# =============================================================================


class TestTextStripWhitespace:
    """Tests for strip_whitespace parameter on Text field."""

    def test_strips_whitespace(self):
        f = Text(strip_whitespace=True)
        assert f.to_db("  hello  ") == "hello"

    def test_disabled_by_default(self):
        f = Text()
        assert f.to_db("  hello  ") == "  hello  "

    def test_strip_before_max_length(self):
        """Stripping happens before max_length check."""
        f = Text(max_length=5, strip_whitespace=True)
        assert f.to_db("  abc  ") == "abc"

    def test_strip_before_min_length(self):
        """Stripping happens before min_length check."""
        f = Text(min_length=5, strip_whitespace=True)
        with pytest.raises(ValueError, match="too short"):
            f.to_db("  ab  ")


# =============================================================================
# Integer min_value / max_value
# =============================================================================


class TestIntegerMinMaxValue:
    """Tests for min_value/max_value on Integer field."""

    def test_below_min_raises(self):
        f = Integer(min_value=1)
        with pytest.raises(ValueError, match="below the minimum"):
            f.to_db(0)

    def test_above_max_raises(self):
        f = Integer(max_value=5)
        with pytest.raises(ValueError, match="exceeds the maximum"):
            f.to_db(6)

    def test_in_range_passes(self):
        f = Integer(min_value=1, max_value=5)
        assert f.to_db(3) == 3

    def test_boundary_values(self):
        f = Integer(min_value=1, max_value=5)
        assert f.to_db(1) == 1
        assert f.to_db(5) == 5

    def test_none_bypasses(self):
        f = Integer(min_value=1, max_value=5, nullable=True)
        assert f.to_db(None) is None

    def test_no_bounds_no_validation(self):
        f = Integer()
        assert f.to_db(-999999) == -999999

    def test_min_max_in_metadata(self):
        f = Integer(min_value=0, max_value=100)
        f.name = "rating"
        meta = f.get_ai_metadata()
        assert meta["min_value"] == 0
        assert meta["max_value"] == 100

    def test_no_bounds_not_in_metadata(self):
        f = Integer()
        f.name = "count"
        meta = f.get_ai_metadata()
        assert "min_value" not in meta
        assert "max_value" not in meta


# =============================================================================
# Integer choices
# =============================================================================


class TestIntegerChoices:
    """Tests for choices parameter on Integer field."""

    def test_valid_choice(self):
        f = Integer(choices=[1, 2, 3])
        assert f.to_db(2) == 2

    def test_invalid_choice_raises(self):
        f = Integer(choices=[1, 2, 3])
        with pytest.raises(ValueError, match="not a valid choice"):
            f.to_db(4)

    def test_none_bypasses(self):
        f = Integer(choices=[1, 2, 3], nullable=True)
        assert f.to_db(None) is None

    def test_choices_in_metadata(self):
        f = Integer(choices=[1, 2, 3])
        f.name = "priority"
        meta = f.get_ai_metadata()
        assert meta["choices"] == [1, 2, 3]

    def test_min_max_with_choices(self):
        """min/max validation runs before choices."""
        f = Integer(min_value=0, max_value=10, choices=[1, 5, 10])
        assert f.to_db(5) == 5
        with pytest.raises(ValueError, match="not a valid choice"):
            f.to_db(3)  # in range but not in choices


# =============================================================================
# SmallInteger choices
# =============================================================================


class TestSmallIntegerChoices:
    """Tests for choices parameter on SmallInteger field."""

    def test_valid_choice(self):
        f = SmallInteger(choices=[1, 2, 3, 4, 5])
        assert f.to_db(3) == 3

    def test_invalid_choice_raises(self):
        f = SmallInteger(choices=[1, 2, 3])
        with pytest.raises(ValueError, match="not a valid choice"):
            f.to_db(4)

    def test_range_check_before_choices(self):
        """SMALLINT range check runs before choices validation."""
        f = SmallInteger(choices=[1, 2])
        with pytest.raises(ValueError, match="out of SMALLINT range"):
            f.to_db(40000)

    def test_none_bypasses(self):
        f = SmallInteger(choices=[1, 2], nullable=True)
        assert f.to_db(None) is None


# =============================================================================
# Float min_value / max_value
# =============================================================================


class TestFloatMinMaxValue:
    """Tests for min_value/max_value on Float field."""

    def test_below_min_raises(self):
        f = Float(min_value=0.0)
        with pytest.raises(ValueError, match="below the minimum"):
            f.to_db(-0.1)

    def test_above_max_raises(self):
        f = Float(max_value=100.0)
        with pytest.raises(ValueError, match="exceeds the maximum"):
            f.to_db(100.1)

    def test_in_range_passes(self):
        f = Float(min_value=0.0, max_value=1.0)
        assert f.to_db(0.5) == 0.5

    def test_boundary_values(self):
        f = Float(min_value=0.0, max_value=1.0)
        assert f.to_db(0.0) == 0.0
        assert f.to_db(1.0) == 1.0

    def test_none_bypasses(self):
        f = Float(min_value=0.0, nullable=True)
        assert f.to_db(None) is None

    def test_min_max_in_metadata(self):
        f = Float(min_value=-10.0, max_value=10.0)
        f.name = "temp"
        meta = f.get_ai_metadata()
        assert meta["min_value"] == -10.0
        assert meta["max_value"] == 10.0


# =============================================================================
# Decimal min_value / max_value
# =============================================================================


class TestDecimalMinMaxValue:
    """Tests for min_value/max_value on Decimal field."""

    def test_below_min_raises(self):
        f = Decimal(max_digits=10, decimal_places=2, min_value=0)
        with pytest.raises(ValueError, match="below the minimum"):
            f.to_db("-0.01")

    def test_above_max_raises(self):
        f = Decimal(max_digits=10, decimal_places=2, max_value=100)
        with pytest.raises(ValueError, match="exceeds the maximum"):
            f.to_db("100.01")

    def test_in_range_passes(self):
        f = Decimal(max_digits=10, decimal_places=2, min_value=0, max_value=100)
        result = f.to_db("50.00")
        assert result == PyDecimal("50.00")

    def test_boundary_values(self):
        f = Decimal(max_digits=10, decimal_places=2, min_value=0, max_value=100)
        assert f.to_db("0") == PyDecimal("0")
        assert f.to_db("100") == PyDecimal("100")

    def test_none_bypasses(self):
        f = Decimal(max_digits=10, decimal_places=2, min_value=0, nullable=True)
        assert f.to_db(None) is None

    def test_precision_runs_before_range(self):
        """Precision check should run before range check."""
        f = Decimal(max_digits=5, decimal_places=2, min_value=0, max_value=100)
        with pytest.raises(ValueError, match="exceeds maximum integer digits"):
            f.to_db("99999.99")  # too many digits

    def test_min_max_in_metadata(self):
        f = Decimal(max_digits=10, decimal_places=2, min_value=0, max_value=999)
        f.name = "price"
        meta = f.get_ai_metadata()
        assert meta["min_value"] == 0.0
        assert meta["max_value"] == 999.0


# =============================================================================
# Slug auto_from
# =============================================================================


class TestSlugAutoFrom:
    """Tests for auto_from parameter on Slug field."""

    def test_auto_generates_slug(self):
        f = Slug(max_length=200, auto_from="title")
        instance = SimpleNamespace(title="Hello World Article")
        result = asyncio.run(f.async_prepare(None, instance=instance))
        assert result == "hello-world-article"

    def test_preserves_existing_slug(self):
        f = Slug(max_length=200, auto_from="title")
        instance = SimpleNamespace(title="Hello World")
        result = asyncio.run(f.async_prepare("custom-slug", instance=instance))
        assert result == "custom-slug"

    def test_truncates_to_max_length(self):
        f = Slug(max_length=10, auto_from="title")
        instance = SimpleNamespace(title="This Is A Very Long Title")
        result = asyncio.run(f.async_prepare(None, instance=instance))
        assert len(result) <= 10
        assert not result.endswith("-")

    def test_no_auto_from_passthrough(self):
        f = Slug(max_length=200)
        result = asyncio.run(f.async_prepare(None, instance=SimpleNamespace()))
        assert result is None

    def test_empty_source_field(self):
        f = Slug(max_length=200, auto_from="title")
        instance = SimpleNamespace(title="")
        result = asyncio.run(f.async_prepare(None, instance=instance))
        # Empty source means no slug generated; returns the original None
        assert result is None

    def test_no_instance_passthrough(self):
        f = Slug(max_length=200, auto_from="title")
        result = asyncio.run(f.async_prepare(None, instance=None))
        assert result is None

    def test_special_characters_in_title(self):
        f = Slug(max_length=200, auto_from="title")
        instance = SimpleNamespace(title="Hello, World! (2025)")
        result = asyncio.run(f.async_prepare(None, instance=instance))
        assert result == "hello-world-2025"

    def test_auto_from_with_unicode(self):
        f = Slug(max_length=200, auto_from="title", allow_unicode=True)
        instance = SimpleNamespace(title="Héllo Wörld")
        result = asyncio.run(f.async_prepare(None, instance=instance))
        assert "héllo" in result
        assert "wörld" in result


# =============================================================================
# Combined validation order tests
# =============================================================================


class TestValidationOrder:
    """Tests verifying that validation steps run in the correct order."""

    def test_string_strip_then_min_length_then_choices_then_regex(self):
        f = String(
            max_length=50,
            min_length=3,
            choices=["abc", "def"],
            regex=r"^[a-z]+$",
            strip_whitespace=True,
        )
        # Valid: stripped, meets min, is a choice, matches regex
        assert f.to_db("  abc  ") == "abc"

    def test_string_strip_causes_min_failure(self):
        f = String(max_length=50, min_length=4, strip_whitespace=True)
        with pytest.raises(ValueError, match="too short"):
            f.to_db("  ab  ")

    def test_integer_range_before_choices(self):
        f = Integer(min_value=0, max_value=10, choices=[1, 5, 10])
        # -1 fails min_value check, not choices check
        with pytest.raises(ValueError, match="below the minimum"):
            f.to_db(-1)


# =============================================================================
# Backward compatibility
# =============================================================================


class TestBackwardCompatibility:
    """Ensure existing usage with no new params is unaffected."""

    def test_string_default_behavior(self):
        f = String(max_length=100)
        assert f.to_db("anything") == "anything"
        assert f.choices is None
        assert f.min_length is None
        assert f.strip_whitespace is False
        assert f._regex is None

    def test_integer_default_behavior(self):
        f = Integer()
        assert f.to_db(42) == 42
        assert f.choices is None
        assert f.min_value is None
        assert f.max_value is None

    def test_text_default_behavior(self):
        f = Text()
        assert f.to_db("hello") == "hello"
        assert f.min_length is None
        assert f.strip_whitespace is False

    def test_float_default_behavior(self):
        f = Float()
        assert f.to_db(3.14) == 3.14
        assert f.min_value is None
        assert f.max_value is None

    def test_decimal_default_behavior(self):
        f = Decimal()
        assert f.to_db("12.34") == PyDecimal("12.34")
        assert f.min_value is None
        assert f.max_value is None

    def test_slug_default_behavior(self):
        f = Slug()
        assert f.to_db("hello-world") == "hello-world"
        assert f.auto_from is None

    def test_small_integer_default_behavior(self):
        f = SmallInteger()
        assert f.to_db(100) == 100
        assert f.choices is None
