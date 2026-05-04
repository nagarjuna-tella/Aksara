"""
Tests for i18n helpers and timezone-aware serialization.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from aksara import Model, fields
from aksara.api.schemas import model_to_dict
from aksara.api.serializers import ModelSerializer
from aksara.conf import settings
from aksara.i18n import _, activate_timezone, reset_timezone, serialize_value
from aksara.registry import ModelRegistry


@pytest.fixture(autouse=True)
def clear_registry():
    """Prevent test-local models from leaking into other tests."""
    original_models = ModelRegistry._models.copy()
    ModelRegistry._models.clear()
    ModelRegistry._models.update(original_models)
    yield
    ModelRegistry._models.clear()
    ModelRegistry._models.update(original_models)


class TestI18nAndTimezoneHelpers:
    """Tests for the first Phase 4 i18n/timezone slice."""

    def test_datetime_field_to_db_normalizes_naive_value_using_active_timezone(self, monkeypatch):
        """Naive datetimes should be interpreted in the active timezone and stored in UTC."""
        monkeypatch.setattr(settings, "use_tz", True, raising=False)
        monkeypatch.setattr(settings, "time_zone", "UTC", raising=False)

        token = activate_timezone("America/New_York")
        try:
            field = fields.DateTime()
            value = field.to_db(datetime(2026, 1, 15, 9, 30, 0))
        finally:
            reset_timezone(token)

        assert value is not None
        assert value.tzinfo == timezone.utc
        assert value.hour == 14
        assert value.minute == 30

    def test_datetime_field_to_python_attaches_utc_to_naive_string_value(self, monkeypatch):
        """Naive string timestamps should be restored as UTC-aware datetimes."""
        monkeypatch.setattr(settings, "use_tz", True, raising=False)

        field = fields.DateTime()
        value = field.to_python("2026-01-15T14:30:00")

        assert value is not None
        assert value.tzinfo == timezone.utc
        assert value.hour == 14

    def test_model_to_dict_localizes_datetime_output(self, monkeypatch):
        """Model serialization should convert datetimes into the active request timezone."""
        monkeypatch.setattr(settings, "use_tz", True, raising=False)
        monkeypatch.setattr(settings, "time_zone", "UTC", raising=False)

        class EventModel(Model):
            starts_at = fields.DateTime()

        token = activate_timezone("America/New_York")
        try:
            instance = EventModel(starts_at=datetime(2026, 1, 15, 14, 30, 0, tzinfo=timezone.utc))
            payload = model_to_dict(instance)
        finally:
            reset_timezone(token)

        assert payload["starts_at"].hour == 9
        assert payload["starts_at"].utcoffset().total_seconds() == -18000

    def test_serializer_localizes_datetime_output(self, monkeypatch):
        """Serializer output should use the active request timezone for datetimes."""
        monkeypatch.setattr(settings, "use_tz", True, raising=False)
        monkeypatch.setattr(settings, "time_zone", "UTC", raising=False)

        class Event(Model):
            starts_at = fields.DateTime()

        class EventSerializer(ModelSerializer):
            class Meta:
                model = Event
                fields = ["starts_at"]

        token = activate_timezone("Europe/Berlin")
        try:
            instance = Event(starts_at=datetime(2026, 1, 15, 14, 30, 0, tzinfo=timezone.utc))
            payload = EventSerializer(instance=instance).to_representation()
        finally:
            reset_timezone(token)

        assert payload["starts_at"].hour == 15
        assert payload["starts_at"].utcoffset().total_seconds() == 3600

    def test_lazy_translation_resolves_at_serialization_time(self):
        """Lazy translation wrappers should resolve to plain strings during serialization."""
        resolved = serialize_value(_("Hello {name}", name="Aksara"))
        assert resolved == "Hello Aksara"