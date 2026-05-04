"""
Storage backends and file wrapper objects for Aksara media handling.

Provides filesystem and S3-compatible storage implementations plus the
FieldFile wrapper used by FileField and ImageField.
"""

from __future__ import annotations

import asyncio
import importlib
import io
import mimetypes
import os
import posixpath
import re
import secrets
from abc import ABC, abstractmethod
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Optional
from urllib.parse import quote

from aksara.exceptions import ImproperlyConfigured


if TYPE_CHECKING:
    from aksara.fields import FileField
    from aksara.model.base import Model


def _get_settings():
    """Lazy import to avoid importing settings during module initialization."""
    from aksara.conf import settings

    return settings


def _normalize_media_url(url: str) -> str:
    """Normalize a media URL prefix to a leading-slash, trailing-slash format."""
    if not url:
        return "/media/"

    normalized = url.strip()
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    if not normalized.endswith("/"):
        normalized = f"{normalized}/"
    return normalized


def sanitize_file_name(name: str) -> str:
    """Sanitize a user-provided filename while preserving simple extensions."""
    base_name = os.path.basename((name or "").replace("\\", "/"))
    base_name = re.sub(r"[^A-Za-z0-9._-]+", "_", base_name).strip("._")
    return base_name or f"upload_{secrets.token_hex(4)}"


def build_upload_name(
    *,
    field_name: str,
    upload_to: str | Any,
    original_name: Optional[str],
    instance: Optional["Model"] = None,
) -> str:
    """Build a storage-relative filename for a newly uploaded object."""
    safe_name = sanitize_file_name(original_name or field_name or "upload")
    generated_name = f"{secrets.token_hex(8)}_{safe_name}"

    if callable(upload_to):
        candidate = upload_to(instance, generated_name)
    elif isinstance(upload_to, str) and upload_to:
        candidate = posixpath.join(upload_to.strip("/"), generated_name)
    else:
        candidate = generated_name

    normalized = str(PurePosixPath(candidate)).lstrip("/")
    if normalized in {"", "."}:
        return generated_name
    return normalized


async def read_uploaded_content(content: Any) -> bytes:
    """Read arbitrary upload content into bytes."""
    if content is None:
        return b""
    if isinstance(content, bytes):
        return content
    if isinstance(content, bytearray):
        return bytes(content)
    if isinstance(content, str):
        return content.encode("utf-8")
    if hasattr(content, "read"):
        reader = content.read
        data = reader()
        if asyncio.iscoroutine(data):
            data = await data
        if isinstance(data, str):
            return data.encode("utf-8")
        return bytes(data)
    raise ValueError(f"Unsupported file content type: {type(content).__name__}")


class Storage(ABC):
    """Base class for pluggable media storage backends."""

    @abstractmethod
    async def save(self, name: str, content: Any) -> str:
        """Persist content and return the final storage-relative name."""

    @abstractmethod
    async def open(self, name: str, mode: str = "rb") -> Any:
        """Open a stored file and return a file-like object."""

    @abstractmethod
    async def delete(self, name: str) -> None:
        """Delete a stored file if it exists."""

    @abstractmethod
    async def exists(self, name: str) -> bool:
        """Return whether the stored file exists."""

    @abstractmethod
    async def size(self, name: str) -> int:
        """Return the stored object size in bytes."""

    @abstractmethod
    def url(self, name: str) -> str:
        """Return a public or application-relative URL for the stored file."""

    def path(self, name: str) -> Optional[str]:
        """Return a local filesystem path when the backend exposes one."""
        return None


class FileSystemStorage(Storage):
    """Local-disk storage backed by MEDIA_ROOT."""

    def __init__(self, location: Optional[str] = None, base_url: Optional[str] = None):
        settings = _get_settings()
        self.location = Path(location or getattr(settings, "media_root", "media")).expanduser().resolve()
        self.base_url = _normalize_media_url(
            base_url or getattr(settings, "media_url", "/media/")
        )
        self.location.mkdir(parents=True, exist_ok=True)

    def _safe_name(self, name: str) -> str:
        normalized = str(PurePosixPath(name)).lstrip("/")
        if normalized in {"", "."}:
            raise ValueError("Storage name cannot be empty")
        return normalized

    def _full_path(self, name: str) -> Path:
        relative_name = self._safe_name(name)
        full_path = (self.location / relative_name).resolve()
        base_dir = self.location.resolve()
        if not str(full_path).startswith(str(base_dir)):
            raise ValueError("Resolved storage path escapes MEDIA_ROOT")
        return full_path

    async def _get_available_name(self, name: str) -> str:
        candidate = self._safe_name(name)
        base_path = PurePosixPath(candidate)
        stem = base_path.stem
        suffix = base_path.suffix
        parent = str(base_path.parent)

        while await self.exists(candidate):
            next_name = f"{stem}_{secrets.token_hex(4)}{suffix}"
            candidate = next_name if parent in {"", "."} else posixpath.join(parent, next_name)

        return candidate

    async def save(self, name: str, content: Any) -> str:
        final_name = await self._get_available_name(name)
        payload = await read_uploaded_content(content)
        full_path = self._full_path(final_name)
        await asyncio.to_thread(full_path.parent.mkdir, parents=True, exist_ok=True)

        def _write() -> None:
            with open(full_path, "wb") as file_handle:
                file_handle.write(payload)

        await asyncio.to_thread(_write)
        return final_name

    async def open(self, name: str, mode: str = "rb") -> Any:
        return await asyncio.to_thread(open, self._full_path(name), mode)

    async def delete(self, name: str) -> None:
        full_path = self._full_path(name)

        def _remove() -> None:
            if full_path.exists():
                full_path.unlink()

        await asyncio.to_thread(_remove)

    async def exists(self, name: str) -> bool:
        return await asyncio.to_thread(self._full_path(name).exists)

    async def size(self, name: str) -> int:
        return await asyncio.to_thread(lambda: self._full_path(name).stat().st_size)

    def url(self, name: str) -> str:
        parts = [quote(part) for part in self._safe_name(name).split("/")]
        return f"{self.base_url}{'/'.join(parts)}"

    def path(self, name: str) -> Optional[str]:
        return str(self._full_path(name))


class S3Storage(Storage):
    """Async S3-compatible storage backend using aiobotocore."""

    def __init__(
        self,
        *,
        bucket_name: Optional[str] = None,
        region_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        settings = _get_settings()
        self.bucket_name = bucket_name or getattr(settings, "media_s3_bucket", None)
        if not self.bucket_name:
            raise ImproperlyConfigured("MEDIA_S3_BUCKET must be configured for S3Storage")

        self.region_name = region_name or getattr(settings, "media_s3_region", None)
        self.endpoint_url = endpoint_url or getattr(settings, "media_s3_endpoint_url", None)
        self.access_key = access_key or getattr(settings, "media_s3_access_key", None)
        self.secret_key = secret_key or getattr(settings, "media_s3_secret_key", None)
        self.base_url = base_url or getattr(settings, "media_public_base_url", None)

    def _session(self):
        """Lazy import aiobotocore only when the backend is used."""
        try:
            import aiobotocore.session
        except ImportError as exc:
            raise ImproperlyConfigured(
                "S3Storage requires aiobotocore. Install with: pip install aiobotocore"
            ) from exc

        return aiobotocore.session.get_session()

    def _client_kwargs(self) -> dict[str, Any]:
        return {
            "service_name": "s3",
            "region_name": self.region_name,
            "endpoint_url": self.endpoint_url,
            "aws_access_key_id": self.access_key,
            "aws_secret_access_key": self.secret_key,
        }

    async def save(self, name: str, content: Any) -> str:
        payload = await read_uploaded_content(content)
        content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"

        session = self._session()
        async with session.create_client(**self._client_kwargs()) as client:
            await client.put_object(
                Bucket=self.bucket_name,
                Key=name,
                Body=payload,
                ContentType=content_type,
            )
        return name

    async def open(self, name: str, mode: str = "rb") -> Any:
        if mode not in {"rb", "r"}:
            raise ValueError("S3Storage.open() only supports 'rb' and 'r' modes")

        session = self._session()
        async with session.create_client(**self._client_kwargs()) as client:
            response = await client.get_object(Bucket=self.bucket_name, Key=name)
            data = await response["Body"].read()

        if mode == "r":
            return io.StringIO(data.decode("utf-8"))
        return io.BytesIO(data)

    async def delete(self, name: str) -> None:
        session = self._session()
        async with session.create_client(**self._client_kwargs()) as client:
            await client.delete_object(Bucket=self.bucket_name, Key=name)

    async def exists(self, name: str) -> bool:
        session = self._session()
        async with session.create_client(**self._client_kwargs()) as client:
            try:
                await client.head_object(Bucket=self.bucket_name, Key=name)
                return True
            except Exception:
                return False

    async def size(self, name: str) -> int:
        session = self._session()
        async with session.create_client(**self._client_kwargs()) as client:
            response = await client.head_object(Bucket=self.bucket_name, Key=name)
        return int(response.get("ContentLength", 0))

    def url(self, name: str) -> str:
        if self.base_url:
            return f"{self.base_url.rstrip('/')}/{quote(name, safe='/')}"
        if self.endpoint_url:
            return f"{self.endpoint_url.rstrip('/')}/{self.bucket_name}/{quote(name, safe='/')}"
        if self.region_name and self.region_name != "us-east-1":
            return f"https://{self.bucket_name}.s3.{self.region_name}.amazonaws.com/{quote(name, safe='/')}"
        return f"https://{self.bucket_name}.s3.amazonaws.com/{quote(name, safe='/')}"


class FieldFile:
    """Model-bound wrapper around a stored file reference."""

    def __init__(
        self,
        *,
        instance: Optional["Model"],
        field: "FileField",
        name: Optional[str],
    ):
        self.instance = instance
        self.field = field
        self.name = name

    def __bool__(self) -> bool:
        return bool(self.name)

    def __str__(self) -> str:
        return self.name or ""

    @property
    def storage(self) -> Storage:
        return self.field.get_storage()

    @property
    def url(self) -> Optional[str]:
        if not self.name:
            return None
        return self.storage.url(self.name)

    @property
    def path(self) -> Optional[str]:
        if not self.name:
            return None
        return self.storage.path(self.name)

    async def open(self, mode: str = "rb") -> Any:
        if not self.name:
            raise ValueError("Cannot open an empty file reference")
        return await self.storage.open(self.name, mode)

    async def read(self) -> bytes:
        handle = await self.open("rb")
        if hasattr(handle, "read"):
            data = handle.read()
            if asyncio.iscoroutine(data):
                data = await data
            if hasattr(handle, "close"):
                await asyncio.to_thread(handle.close)
            return bytes(data)
        return bytes(handle)

    async def size(self) -> int:
        if not self.name:
            return 0
        return await self.storage.size(self.name)

    async def exists(self) -> bool:
        if not self.name:
            return False
        return await self.storage.exists(self.name)

    async def delete(self) -> None:
        if not self.name:
            return
        await self.storage.delete(self.name)
        if self.instance is not None:
            self.instance._data[self.field.name] = None
        self.name = None


_storage_cache: tuple[tuple[Any, ...], Storage] | None = None


def _storage_signature() -> tuple[Any, ...]:
    settings = _get_settings()
    return (
        getattr(settings, "media_storage", "filesystem"),
        getattr(settings, "media_root", "media"),
        getattr(settings, "media_url", "/media/"),
        getattr(settings, "media_s3_bucket", None),
        getattr(settings, "media_s3_region", None),
        getattr(settings, "media_s3_endpoint_url", None),
        getattr(settings, "media_s3_access_key", None),
        getattr(settings, "media_s3_secret_key", None),
        getattr(settings, "media_public_base_url", None),
    )


def clear_storage_cache() -> None:
    """Clear cached default storage instances. Useful for tests."""
    global _storage_cache
    _storage_cache = None


def get_default_storage() -> Storage:
    """Return the configured default media storage backend."""
    global _storage_cache

    signature = _storage_signature()
    if _storage_cache is not None and _storage_cache[0] == signature:
        return _storage_cache[1]

    settings = _get_settings()
    backend = getattr(settings, "media_storage", "filesystem")

    if backend in {"filesystem", "file", "local"}:
        storage: Storage = FileSystemStorage()
    elif backend == "s3":
        storage = S3Storage()
    elif isinstance(backend, str) and "." in backend:
        module_name, class_name = backend.rsplit(".", 1)
        module = importlib.import_module(module_name)
        storage_class = getattr(module, class_name)
        storage = storage_class()
    else:
        raise ImproperlyConfigured(f"Unsupported media storage backend: {backend}")

    _storage_cache = (signature, storage)
    return storage


__all__ = [
    "FieldFile",
    "Storage",
    "FileSystemStorage",
    "S3Storage",
    "build_upload_name",
    "sanitize_file_name",
    "read_uploaded_content",
    "get_default_storage",
    "clear_storage_cache",
]