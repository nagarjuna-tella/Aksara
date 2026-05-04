"""
Tests for storage backends and file field integration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image

from aksara.conf import settings
from aksara.db import Database
from aksara.fields import FileField, ImageField
from aksara.model.base import Model
from aksara.storage import FieldFile, FileSystemStorage, clear_storage_cache




def build_png_bytes() -> bytes:
    """Generate a tiny valid PNG payload for image storage tests."""
    buffer = BytesIO()
    Image.new("RGBA", (1, 1), (255, 0, 0, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


class StoredDocument(Model):
    file = FileField(upload_to="documents")


class StoredImage(Model):
    image = ImageField(upload_to="images")


class TestFileSystemStorage:
    """Focused tests for local media storage."""

    @pytest.fixture(autouse=True)
    def reset_storage(self):
        clear_storage_cache()
        yield
        clear_storage_cache()

    @pytest.mark.asyncio
    async def test_filesystem_storage_save_and_read(self, tmp_path):
        storage = FileSystemStorage(location=str(tmp_path), base_url="/media/")

        saved_name = await storage.save("avatars/profile.txt", b"hello world")

        assert saved_name == "avatars/profile.txt"
        assert await storage.exists(saved_name) is True
        assert await storage.size(saved_name) == 11
        assert storage.url(saved_name) == "/media/avatars/profile.txt"

        file_handle = await storage.open(saved_name)
        try:
            assert file_handle.read() == b"hello world"
        finally:
            file_handle.close()

    @pytest.mark.asyncio
    async def test_model_save_prepares_file_field(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, "media_root", str(tmp_path), raising=False)
        monkeypatch.setattr(settings, "media_url", "/media/", raising=False)
        monkeypatch.setattr(settings, "media_storage", "filesystem", raising=False)
        clear_storage_cache()

        class FakeDatabase:
            async def fetchrow(self, query, *values):
                assert any(str(value).startswith("documents/") for value in values)
                return {
                    "id": uuid4(),
                    "file": next(value for value in values if isinstance(value, str) and value.startswith("documents/")),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }

            async def execute(self, query, *values):
                return None

        monkeypatch.setattr(Database, "get_instance", classmethod(lambda cls: FakeDatabase()))

        document = StoredDocument(file=("report.txt", b"phase-3"))
        await document.save()

        assert isinstance(document.file, FieldFile)
        assert document.file.name is not None
        assert document.file.name.startswith("documents/")
        assert document.file.url is not None
        assert await document.file.exists() is True
        assert await document.file.read() == b"phase-3"
        assert document.to_dict()["file"].startswith("documents/")

    @pytest.mark.asyncio
    async def test_image_field_rejects_invalid_content(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, "media_root", str(tmp_path), raising=False)
        monkeypatch.setattr(settings, "media_url", "/media/", raising=False)
        monkeypatch.setattr(settings, "media_storage", "filesystem", raising=False)
        clear_storage_cache()

        image_field = StoredImage._fields["image"]

        with pytest.raises(ValueError, match="valid image"):
            await image_field.async_prepare(("avatar.png", b"not-an-image"), instance=None)

    @pytest.mark.asyncio
    async def test_image_field_saves_valid_image(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, "media_root", str(tmp_path), raising=False)
        monkeypatch.setattr(settings, "media_url", "/media/", raising=False)
        monkeypatch.setattr(settings, "media_storage", "filesystem", raising=False)
        clear_storage_cache()

        image_field = StoredImage._fields["image"]
        stored_name = await image_field.async_prepare(("avatar.png", build_png_bytes()), instance=None)

        assert stored_name.startswith("images/")
        wrapped = image_field.to_field_file(stored_name, instance=None)
        assert await wrapped.exists() is True
        assert await wrapped.size() > 0