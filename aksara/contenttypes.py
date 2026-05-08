"""
Content types and generic relation helpers.

Provides a managed content-type table plus runtime helpers used by
GenericForeignKey descriptors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional, Tuple, Type
from uuid import UUID

from aksara import fields
from aksara.db import Database
from aksara.model.base import Model
from aksara.registry import ModelRegistry

if TYPE_CHECKING:
    from aksara.model.base import Model as ModelType


CONTENT_TYPES_TABLE = "aksara_content_types"
CONTENT_TYPES_TABLE_SQL = f'''CREATE TABLE IF NOT EXISTS "{CONTENT_TYPES_TABLE}" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    app_label VARCHAR(255) NOT NULL,
    model VARCHAR(100) NOT NULL,
    module VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_{CONTENT_TYPES_TABLE} UNIQUE (app_label, model)
);'''

_content_type_cache_by_key: Dict[Tuple[str, str], "ContentType"] = {}
_content_type_cache_by_id: Dict[UUID, "ContentType"] = {}
_content_type_sync_token: Optional[Tuple[str, ...]] = None


class ContentType(Model):
    """Internal content type mapping for GenericForeignKey support."""

    __tablename__ = CONTENT_TYPES_TABLE

    app_label = fields.String(max_length=255)
    model = fields.String(max_length=100)
    module = fields.String(max_length=255)

    class Meta:
        ai_name = "ContentType"
        ai_description = "Internal model registry mapping for generic relations"
        ai_agent_exposed = False
        ai_permissions = ["read"]


def _get_db(db: Optional[Database] = None) -> Database:
    """Return the active database instance."""
    if db is not None:
        return db
    return Database.get_instance()


def _get_model_identity(model: Type["ModelType"]) -> tuple[str, str, str]:
    """Derive a stable app/model identity for a registered model."""
    module = getattr(model, "__module__", "") or ""

    meta = getattr(model, "meta", None)
    app_label = getattr(meta, "app_label", None) if meta is not None else None

    if not app_label:
        parts = module.split(".") if module else []
        if len(parts) >= 2 and parts[-1] in {"models", "model"}:
            app_label = ".".join(parts[:-1])
        elif len(parts) >= 2:
            app_label = ".".join(parts[:-1])
        elif parts:
            app_label = parts[0]
        else:
            app_label = "default"

    return app_label, model.__name__, module or app_label


def _registry_signature() -> tuple[str, ...]:
    """Build a token for the currently registered model set."""
    entries = []
    for model in ModelRegistry.all().values():
        app_label, model_name, _ = _get_model_identity(model)
        entries.append(f"{app_label}:{model_name}")
    return tuple(sorted(entries))


def _cache_content_type(content_type: "ContentType") -> "ContentType":
    """Populate in-memory lookup caches for a content type."""
    key = (content_type.app_label, content_type.model)
    _content_type_cache_by_key[key] = content_type
    _content_type_cache_by_id[content_type.id] = content_type
    return content_type


def clear_content_type_cache() -> None:
    """Reset all content type caches."""
    global _content_type_sync_token

    _content_type_cache_by_key.clear()
    _content_type_cache_by_id.clear()
    _content_type_sync_token = None


async def ensure_content_types_table(db: Optional[Database] = None) -> None:
    """Create the internal content types table when missing."""
    database = _get_db(db)
    await database.execute(CONTENT_TYPES_TABLE_SQL)
    # Idempotent schema migrations for tables created by older versions.
    await database.execute(
        f'''
        DO $$
        BEGIN
            -- Add unique constraint if missing (required for ON CONFLICT upsert).
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_{CONTENT_TYPES_TABLE}'
                  AND conrelid = '"{CONTENT_TYPES_TABLE}"'::regclass
            ) THEN
                ALTER TABLE "{CONTENT_TYPES_TABLE}"
                    ADD CONSTRAINT uq_{CONTENT_TYPES_TABLE} UNIQUE (app_label, model);
            END IF;

            -- Ensure created_at and updated_at have defaults so INSERT without
            -- those columns does not fail with a NOT NULL violation.
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = '{CONTENT_TYPES_TABLE}'
                  AND column_name = 'created_at'
                  AND column_default IS NULL
            ) THEN
                ALTER TABLE "{CONTENT_TYPES_TABLE}"
                    ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = '{CONTENT_TYPES_TABLE}'
                  AND column_name = 'updated_at'
                  AND column_default IS NULL
            ) THEN
                ALTER TABLE "{CONTENT_TYPES_TABLE}"
                    ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;
            END IF;
        END$$;
        '''
    )


async def sync_content_types(
    db: Optional[Database] = None,
    *,
    prune_stale: bool = False,
) -> list[ContentType]:
    """Sync the content types table with the current model registry."""
    global _content_type_sync_token

    database = _get_db(db)
    await ensure_content_types_table(database)

    synced: list[ContentType] = []
    registered_keys: set[tuple[str, str]] = set()

    for model in ModelRegistry.all().values():
        app_label, model_name, module = _get_model_identity(model)
        registered_keys.add((app_label, model_name))
        record = await database.fetchrow(
            f'''
            INSERT INTO "{CONTENT_TYPES_TABLE}" (app_label, model, module)
            VALUES ($1, $2, $3)
            ON CONFLICT (app_label, model)
            DO UPDATE SET
                module = EXCLUDED.module,
                updated_at = CURRENT_TIMESTAMP
            RETURNING *
            ''',
            app_label,
            model_name,
            module,
        )
        if record is not None:
            synced.append(_cache_content_type(ContentType._from_record(record)))

    if prune_stale:
        stale_rows = await database.fetch(
            f'SELECT id, app_label, model FROM "{CONTENT_TYPES_TABLE}"'
        )
        for row in stale_rows:
            key = (row["app_label"], row["model"])
            if key in registered_keys:
                continue
            await database.execute(
                f'DELETE FROM "{CONTENT_TYPES_TABLE}" WHERE id = $1',
                row["id"],
            )
            _content_type_cache_by_key.pop(key, None)
            _content_type_cache_by_id.pop(row["id"], None)

    _content_type_sync_token = _registry_signature()
    return synced


async def ensure_content_types_synced(
    db: Optional[Database] = None,
    *,
    prune_stale: bool = False,
) -> None:
    """Synchronize content types when the model registry changed."""
    if _content_type_sync_token == _registry_signature():
        return
    clear_content_type_cache()
    await sync_content_types(db, prune_stale=prune_stale)


def _find_registered_model(app_label: str, model_name: str) -> Type["ModelType"]:
    """Resolve a model class from the current registry."""
    for model in ModelRegistry.all().values():
        candidate_app_label, candidate_model_name, _ = _get_model_identity(model)
        if candidate_app_label == app_label and candidate_model_name == model_name:
            return model
    raise KeyError(f"Model '{app_label}.{model_name}' is not registered")


async def get_content_type_for_model(
    model: Type["ModelType"],
    db: Optional[Database] = None,
) -> ContentType:
    """Return the content type row for a model, creating it on demand."""
    await ensure_content_types_synced(db)

    app_label, model_name, module = _get_model_identity(model)
    key = (app_label, model_name)
    cached = _content_type_cache_by_key.get(key)
    if cached is not None:
        return cached

    database = _get_db(db)
    record = await database.fetchrow(
        f'''
        INSERT INTO "{CONTENT_TYPES_TABLE}" (app_label, model, module)
        VALUES ($1, $2, $3)
        ON CONFLICT (app_label, model)
        DO UPDATE SET
            module = EXCLUDED.module,
            updated_at = CURRENT_TIMESTAMP
        RETURNING *
        ''',
        app_label,
        model_name,
        module,
    )
    if record is None:
        raise RuntimeError(f"Failed to resolve content type for {app_label}.{model_name}")

    return _cache_content_type(ContentType._from_record(record))


async def get_content_type_by_id(
    content_type_id: UUID,
    db: Optional[Database] = None,
) -> ContentType:
    """Resolve a content type row by primary key."""
    cached = _content_type_cache_by_id.get(content_type_id)
    if cached is not None:
        return cached

    await ensure_content_types_synced(db)
    cached = _content_type_cache_by_id.get(content_type_id)
    if cached is not None:
        return cached

    database = _get_db(db)
    record = await database.fetchrow(
        f'SELECT * FROM "{CONTENT_TYPES_TABLE}" WHERE id = $1',
        content_type_id,
    )
    if record is None:
        raise KeyError(f"Unknown content type id: {content_type_id}")

    return _cache_content_type(ContentType._from_record(record))


async def get_model_for_content_type(
    content_type_id: UUID,
    db: Optional[Database] = None,
) -> Type["ModelType"]:
    """Resolve the runtime model class for a content type id."""
    content_type = await get_content_type_by_id(content_type_id, db)
    return _find_registered_model(content_type.app_label, content_type.model)


async def resolve_generic_related_object(
    content_type_id: UUID,
    object_id: str,
    db: Optional[Database] = None,
) -> "ModelType":
    """Resolve a related model instance from a generic relation pair."""
    model = await get_model_for_content_type(content_type_id, db)
    return await model.objects.get(id=object_id)


__all__ = [
    "CONTENT_TYPES_TABLE",
    "ContentType",
    "clear_content_type_cache",
    "ensure_content_types_synced",
    "ensure_content_types_table",
    "get_content_type_by_id",
    "get_content_type_for_model",
    "get_model_for_content_type",
    "resolve_generic_related_object",
    "sync_content_types",
]