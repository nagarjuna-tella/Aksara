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
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type
from uuid import UUID

if TYPE_CHECKING:
    from aksara.model.base import Model


class FixtureEncoder(json.JSONEncoder):
    """JSON encoder that handles UUID and datetime objects."""
    
    def default(self, obj: Any) -> Any:
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


async def dump_data(
    model: Type[Model],
    filters: Optional[Dict[str, Any]] = None,
    fields: Optional[List[str]] = None,
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
    for instance in instances:
        record = {
            "model": model.__name__,
            "pk": instance.id,
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
    if format.lower() == "yaml":
        try:
            import yaml
            return yaml.dump(data, default_flow_style=False, sort_keys=False)
        except ImportError:
            raise ImportError("PyYAML is required for YAML format. Install with: pip install pyyaml")
    else:
        # Default to JSON
        return json.dumps(data, indent=2, cls=FixtureEncoder)


async def load_data(
    data: str,
    models: Optional[Dict[str, Type[Model]]] = None,
    format: str = "json",
    strict: bool = False,
) -> Dict[str, int]:
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
            
            # Create or update instance
            if pk:
                # Update existing
                try:
                    instance = await model_class.objects.get(id=pk)
                    for field_name, value in fields.items():
                        if field_name in instance._fields:
                            instance._data[field_name] = value
                except Exception as e:
                    if strict:
                        raise
                    stats["errors"] += 1
                    continue
            else:
                # Create new
                instance = model_class(**fields)
            
            # Save the instance
            try:
                await instance.save()
                stats["loaded"] += 1
            except Exception as e:
                if strict:
                    raise
                stats["errors"] += 1
        
        except Exception as e:
            if strict:
                raise
            stats["errors"] += 1
    
    return stats


async def dump_database(
    app_label: Optional[str] = None,
    models: Optional[List[str]] = None,
    filters: Optional[Dict[str, Any]] = None,
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
        for model_class in ModelRegistry.all():
            if app_label is None or getattr(model_class.Meta, 'app_label', None) == app_label:
                models_to_export.append(model_class)
    
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
            return yaml.dump(all_data, default_flow_style=False, sort_keys=False)
        except ImportError:
            raise ImportError("PyYAML is required for YAML format. Install with: pip install pyyaml")
    else:
        return json.dumps(all_data, indent=2, cls=FixtureEncoder)
