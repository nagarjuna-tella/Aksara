"""
Migration support tests for FileField and ImageField.
"""

from __future__ import annotations

from aksara import fields
from aksara.migrations.autodetector import _field_op_to_code, _model_field_to_op, build_state_from_models
from aksara.model.base import Model


class MediaAsset(Model):
    file = fields.FileField(upload_to="assets")
    image = fields.ImageField(upload_to="images", nullable=True)


class TestMediaFieldMigrations:
    """Verify media fields round-trip through migration helpers."""

    def test_build_state_marks_media_field_types(self):
        state = build_state_from_models({"MediaAsset": MediaAsset})
        table = state.tables[MediaAsset.__tablename__]

        assert table.fields["file"].field_type == "FileField"
        assert table.fields["image"].field_type == "ImageField"

    def test_media_fields_convert_to_migration_ops(self):
        file_op = _model_field_to_op("file", MediaAsset._fields["file"])
        image_op = _model_field_to_op("image", MediaAsset._fields["image"])

        assert type(file_op).__name__ == "FileField"
        assert type(image_op).__name__ == "ImageField"
        assert _field_op_to_code(file_op).startswith("op.FileField(")
        assert _field_op_to_code(image_op).startswith("op.ImageField(")