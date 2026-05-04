"""
Schema generation tests for file-backed model fields.
"""

from __future__ import annotations

from aksara import fields
from aksara.api.schemas import clear_schema_cache, get_schemas_for_model
from aksara.model.base import Model


class Asset(Model):
    file = fields.FileField(upload_to="assets")
    image = fields.ImageField(upload_to="images", nullable=True)


class TestFileFieldSchemas:
    """Ensure media fields map cleanly into generated Pydantic schemas."""

    def setup_method(self):
        clear_schema_cache()

    def test_media_fields_map_to_strings(self):
        schemas = get_schemas_for_model(Asset)

        assert schemas["create"].model_fields["file"].annotation is str
        assert schemas["update"].model_fields["file"].annotation == (str | None)
        assert schemas["read"].model_fields["file"].annotation is str
        assert schemas["read"].model_fields["image"].annotation == (str | None)