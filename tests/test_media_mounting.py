"""
Tests for automatic media mounting in Aksara applications.
"""

from __future__ import annotations

from aksara.routing import iter_routes

from aksara import Aksara
from aksara.conf import settings
from aksara.storage import clear_storage_cache


class TestMediaMounting:
    """Verify local media mounting behavior in debug mode."""

    def test_media_mounts_in_debug_with_filesystem_storage(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, "media_root", str(tmp_path), raising=False)
        monkeypatch.setattr(settings, "media_url", "/media/", raising=False)
        monkeypatch.setattr(settings, "media_storage", "filesystem", raising=False)
        monkeypatch.setattr(settings, "debug", False, raising=False)
        clear_storage_cache()

        app = Aksara(database_url=None, debug=True, enable_admin=False, auto_discover_views=False)

        route_paths = [route.path for route in iter_routes(app)]
        assert "/media" in route_paths

    def test_media_does_not_mount_outside_debug(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, "media_root", str(tmp_path), raising=False)
        monkeypatch.setattr(settings, "media_url", "/media/", raising=False)
        monkeypatch.setattr(settings, "media_storage", "filesystem", raising=False)
        monkeypatch.setattr(settings, "debug", False, raising=False)
        clear_storage_cache()

        app = Aksara(database_url=None, debug=False, enable_admin=False, auto_discover_views=False)

        route_paths = [route.path for route in iter_routes(app)]
        assert "/media" not in route_paths