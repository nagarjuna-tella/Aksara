"""
Fixture Management - dumpdata and loaddata

Export models to JSON/YAML files and import them back.

v0.5.39: Initial implementation.

Usage:
    # Export all users to JSON
    aksara dumpdata User --format json > users.json
    
    # Export specific model with filter
    aksara dumpdata Post --format json --filter "published=true" > published_posts.json
    
    # Load fixture into database
    aksara loaddata users.json
    
    # Load with strict validation
    aksara loaddata users.json --strict
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from aksara.model.base import Model


class FixtureEncoder(json.JSONEncoder):
    """JSON encoder for portable fixture scalar values."""
    
    def default(self, obj: Any) -> Any:
        portable = _to_portable(obj)
        if portable is not obj:
            return portable
        return super().default(obj)


def _to_portable(value: Any) -> Any:
    """Convert supported Python values to JSON/YAML-safe scalar structures."""
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return _to_portable(value.value)
    if isinstance(value, dict):
        return {key: _to_portable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_portable(item) for item in value]
    return value


def _primary_key(model: type[Model]) -> tuple[str, Any]:
    """Return the declared primary-key name and field."""
    for name, field in model._fields.items():
        if field.primary_key:
            return name, field
    raise ValueError(f"Model {model.__name__} has no primary key")


def _prepare_fields(model: type[Model], values: dict[str, Any]) -> dict[str, Any]:
    """Convert portable fixture scalars through their declared fields."""
    prepared: dict[str, Any] = {}
    for name, value in values.items():
        field = model._fields.get(name)
        if field is not None:
            prepared[name] = field.to_python(value)
    return prepared


def _order_models(models: list[type[Model]]) -> list[type[Model]]:
    """Place referenced models before dependants when a fixture can do so."""
    from aksara.fields import ForeignKey
    from aksara.registry import ModelRegistry

    selected = set(models)
    position = {model: index for index, model in enumerate(models)}
    dependencies: dict[type[Model], set[type[Model]]] = {}
    for model in selected:
        dependencies[model] = {
            field.to_model
            for field in model._fields.values()
            if isinstance(field, ForeignKey) and field.to_model in selected
        }

    ordered: list[type[Model]] = []
    remaining = set(selected)
    while remaining:
        ready = sorted(
            (model for model in remaining if not (dependencies[model] & remaining)),
            key=lambda model: (position[model], ModelRegistry.reference(model)),
        )
        if not ready:
            # Cycles cannot be made insert-safe by ordering alone. Preserve all
            # models and leave constraint handling to the caller/database.
            ready = sorted(
                remaining,
                key=lambda model: (position[model], ModelRegistry.reference(model)),
            )
        ordered.extend(ready)
        remaining.difference_update(ready)
    return ordered


async def dump_data(
    model: type[Model],
    filters: dict[str, Any] | None = None,
    fields: list[str] | None = None,
    format: str = "json",
) -> str:
    """
    Export model instances to JSON or YAML.
    
    v0.5.39: Initial implementation.
    
    Args:
        model: The model class to export
        filters: Optional filter conditions (e.g., {"is_active": True})
        fields: Optional list of field names to include (default: all)
        format: "json" or "yaml" (default: "json")
        
    Returns:
        Serialized string in requested format
        
    Usage:
        json_data = await dump_data(User, filters={"is_active": True})
        yaml_data = await dump_data(Post, format="yaml")
    """
    # Query the instances
    queryset = model.objects.filter()
    if filters:
        queryset = queryset.filter(**filters)
    
    instances = await queryset.all()
    
    # Serialize instances
    data = []
    from aksara.registry import ModelRegistry
    pk_name, _pk_field = _primary_key(model)
    for instance in instances:
        record = {
            "model": ModelRegistry.reference(model),
            "pk": instance._data.get(pk_name),
            "fields": {},
        }
        
        for field_name, field in model._fields.items():
            # Skip primary key (included as pk)
            if field.primary_key:
                continue
            
            # Skip fields not in the list (if fields is specified)
            if fields and field_name not in fields:
                continue
            
            value = instance._data.get(field_name)
            
            # Convert ForeignKey values to just the ID
            from aksara.fields import ForeignKey
            if isinstance(field, ForeignKey) and value is not None:
                # Value is already the ID
                record["fields"][field_name] = value
            else:
                record["fields"][field_name] = value
        
        data.append(record)
    
    # Format output
    portable_data = _to_portable(data)
    if format.lower() == "yaml":
        try:
            import yaml
            return yaml.safe_dump(portable_data, default_flow_style=False, sort_keys=False)
        except ImportError:
            raise ImportError("PyYAML is required for YAML format. Install with: pip install pyyaml")
    else:
        # Default to JSON
        return json.dumps(portable_data, indent=2, cls=FixtureEncoder)


async def load_data(
    data: str,
    models: dict[str, type[Model]] | None = None,
    format: str = "json",
    strict: bool = False,
) -> dict[str, int]:
    """
    Load fixture data from JSON or YAML string.
    
    v0.5.39: Initial implementation.
    
    Args:
        data: Serialized fixture data (JSON or YAML string)
        models: Optional dict mapping model names to model classes
               If None, uses ModelRegistry to lookup by name
        format: "json" or "yaml" (default: "json")
        strict: If True, raise on validation errors. If False, log and skip.
        
    Returns:
        Dict with counts: {"loaded": 10, "errors": 1, "skipped": 0}
        
    Usage:
        with open("fixtures/users.json") as f:
            data = f.read()
        
        result = await load_data(data)
        print(f"Loaded {result['loaded']} records")
    """
    from aksara.manager import DoesNotExist
    from aksara.registry import ModelRegistry
    
    # Parse fixture data
    if format.lower() == "yaml":
        try:
            import yaml
            fixtures = yaml.safe_load(data)
        except ImportError:
            raise ImportError("PyYAML is required for YAML format. Install with: pip install pyyaml")
    else:
        # Default to JSON
        fixtures = json.loads(data)
    
    if not isinstance(fixtures, list):
        fixtures = [fixtures]
    
    # Load records
    stats = {"loaded": 0, "errors": 0, "skipped": 0}
    
    for fixture in fixtures:
        try:
            model_name = fixture.get("model")
            pk = fixture.get("pk")
            fields = fixture.get("fields", {})
            
            if not model_name:
                if strict:
                    raise ValueError("Fixture missing 'model' field")
                stats["skipped"] += 1
                continue
            
            # Get the model class
            if models and model_name in models:
                model_class = models[model_name]
            else:
                model_class = ModelRegistry.get(model_name)
            
            if not model_class:
                if strict:
                    raise ValueError(f"Unknown model: {model_name}")
                stats["skipped"] += 1
                continue
            
            prepared_fields = _prepare_fields(model_class, fields)
            pk_name, pk_field = _primary_key(model_class)

            # A supplied primary key has restore semantics: update the matching
            # row, or insert a missing row with that identity. Omitting it has
            # seed semantics and lets the model generate its primary key.
            if pk is not None:
                prepared_pk = pk_field.to_python(pk)
                try:
                    instance = await model_class.objects.get(**{pk_name: prepared_pk})
                except DoesNotExist:
                    instance = model_class(**{pk_name: prepared_pk, **prepared_fields})
                else:
                    for field_name, value in prepared_fields.items():
                        instance._data[field_name] = value
            else:
                instance = model_class(**prepared_fields)
            
            # Save the instance
            try:
                await instance.save()
                stats["loaded"] += 1
            except Exception:
                if strict:
                    raise
                stats["errors"] += 1
        
        except Exception:
            if strict:
                raise
            stats["errors"] += 1
    
    return stats


async def dump_database(
    app_label: str | None = None,
    models: list[str] | None = None,
    filters: dict[str, Any] | None = None,
    format: str = "json",
) -> str:
    """
    Export entire database or specific models to fixture format.
    
    v0.5.39: Initial implementation.
    
    Args:
        app_label: Optional app label to filter models
        models: Optional list of model names to export
        filters: Optional filter conditions (applied to all models)
        format: "json" or "yaml"
        
    Returns:
        Serialized fixture data
        
    Usage:
        # Export all models
        data = await dump_database()
        
        # Export specific models
        data = await dump_database(models=["User", "Post"])
        
        # Export with filter
        data = await dump_database(filters={"created_at__gte": "2024-01-01"})
    """
    from aksara.registry import ModelRegistry
    
    all_data = []
    
    # Get models to export
    models_to_export = []
    if models:
        for model_name in models:
            model_class = ModelRegistry.get(model_name)
            if model_class:
                models_to_export.append(model_class)
    else:
        # Get all models (optionally filtered by app_label)
        for model_class in ModelRegistry.all().values():
            if app_label is None or model_class.meta.app_label == app_label:
                models_to_export.append(model_class)

    models_to_export = _order_models(models_to_export)
    
    # Export each model
    for model_class in models_to_export:
        json_str = await dump_data(
            model_class,
            filters=filters,
            format="json",  # Temporarily use JSON for parsing
        )
        data = json.loads(json_str)
        all_data.extend(data)
    
    # Format output
    if format.lower() == "yaml":
        try:
            import yaml
            return yaml.safe_dump(
                _to_portable(all_data),
                default_flow_style=False,
                sort_keys=False,
            )
        except ImportError:
            raise ImportError("PyYAML is required for YAML format. Install with: pip install pyyaml")
    else:
        return json.dumps(all_data, indent=2, cls=FixtureEncoder)
