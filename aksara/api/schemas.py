"""
Auto-generated Pydantic Schemas from Aksara Models

Generates Create, Update, and Read schemas dynamically based on model fields.

Field Type Mappings:
    - UUID → UUID (pydantic)
    - String → str
    - FileField → str
    - Integer → int  
    - Boolean → bool
    - DateTime → datetime
    - JSON → dict | list
    - ForeignKey → UUID
    - Text → str
    - Email → str (format=email)
    - URL → str (format=uri)
    - Decimal → Decimal
    - Enum → str (with allowed values)
    - ManyToMany → list[UUID]
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Type, Union, get_type_hints
from uuid import UUID

from pydantic import BaseModel, ConfigDict, create_model
from pydantic import Field as PydanticField

from aksara import fields as aksara_fields
from aksara.api.field_policy import advanced_input_type
from aksara.i18n import serialize_value
from aksara.model.base import Model

# Schema cache for performance
_schema_cache: Dict[str, Dict[str, Type[BaseModel]]] = {}

# O(1) dispatch table for simple field → Python type mappings.
# Keyed by the exact field class so subclasses fall through to the
# isinstance slow-path below, preserving correct inheritance semantics.
_FIELD_SIMPLE_TYPES: Dict[type, Any] = {}


def _build_field_type_map() -> None:
    """Populate _FIELD_SIMPLE_TYPES once all field classes are available."""
    _FIELD_SIMPLE_TYPES.update({
        aksara_fields.UUID: UUID,
        aksara_fields.String: str,
        aksara_fields.Text: str,
        aksara_fields.Email: str,
        aksara_fields.URL: str,
        aksara_fields.Slug: str,
        aksara_fields.FilePath: str,
        aksara_fields.IPAddress: str,
        aksara_fields.FileField: str,
        aksara_fields.ImageField: str,
        aksara_fields.Integer: int,
        aksara_fields.SmallInteger: int,
        aksara_fields.BigInteger: int,
        aksara_fields.PositiveInteger: int,
        aksara_fields.PositiveSmallInteger: int,
        aksara_fields.PositiveBigInteger: int,
        aksara_fields.Boolean: bool,
        aksara_fields.DateTime: datetime,
        aksara_fields.Decimal: Decimal,
        aksara_fields.Float: float,
        aksara_fields.Enum: str,
    })


_build_field_type_map()


def _get_python_type(field: aksara_fields.Field) -> type:
    """Map an Aksara field instance to its Python/Pydantic type."""
    # Fast path: O(1) exact-class lookup for simple types.
    pt = _FIELD_SIMPLE_TYPES.get(type(field))
    if pt is not None:
        return pt
    # Slow path: parameterized / inheritance-sensitive types.
    if isinstance(field, aksara_fields.JSON):
        return Union[dict, list, str, int, float, bool, None]
    if isinstance(field, aksara_fields.Vector):
        return List[float]
    if isinstance(field, aksara_fields.Array):
        return List[field.item_type]
    if isinstance(field, aksara_fields.ForeignKey):  # also covers OneToOne
        return UUID
    if isinstance(field, aksara_fields.ManyToMany):
        return List[UUID]
    return Any


def _should_include_in_create(field_name: str, field: aksara_fields.Field) -> bool:
    """
    Determine if a field should be included in Create schema.
    
    Excludes:
        - Primary key (auto-generated)
        - Auto timestamps (created_at, updated_at)
    
    Includes:
        - ManyToMany (as list of UUIDs)
    """
    # Tenant identity is assigned from the authenticated request principal by
    # ModelViewSet. It must never be accepted as client input.
    if field_name == "tenant_id":
        return False

    # Skip primary key
    if field.primary_key:
        return False
    
    # Skip auto timestamps
    if isinstance(field, aksara_fields.DateTime):
        if field.auto_now or field.auto_now_add:
            return False
    
    return True


def _should_include_in_update(field_name: str, field: aksara_fields.Field) -> bool:
    """
    Determine if a field should be included in Update schema.
    
    Excludes:
        - Primary key
        - Auto timestamps
    
    Includes:
        - ManyToMany (as list of UUIDs)
    """
    return _should_include_in_create(field_name, field)


def _should_include_in_read(field_name: str, field: aksara_fields.Field) -> bool:
    """
    Determine if a field should be included in Read schema.
    
    Includes everything (serializable representation).
    """
    return True


def generate_create_schema(model: Type[Model]) -> Type[BaseModel]:
    """
    Generate a Pydantic Create schema for a Aksara model.
    
    The Create schema includes:
        - All user-defined fields
        - Excludes PK and auto-timestamps
        - Respects nullable/default settings
        - ManyToMany as list of UUIDs
    
    Args:
        model: Aksara Model class
        
    Returns:
        Pydantic model class for creation
    """
    model_name = model.__name__
    cache_key = f"{model_name}Create"
    
    if model_name in _schema_cache and cache_key in _schema_cache[model_name]:
        return _schema_cache[model_name][cache_key]
    
    field_definitions = {}
    
    for field_name, field in model._fields.items():
        if not _should_include_in_create(field_name, field):
            continue
        
        python_type = _get_python_type(field)
        
        # Handle ForeignKey - use the _id column name
        if isinstance(field, aksara_fields.ForeignKey):
            actual_field_name = field.db_column_name  # e.g., "author_id"
        else:
            actual_field_name = field_name
        
        # Determine if field is required
        has_default = field.default is not None or callable(field.default)
        is_required = not field.nullable and not has_default
        
        if is_required:
            # Required field
            field_definitions[actual_field_name] = (
                advanced_input_type(field, python_type),
                PydanticField(description=field.ai_description)
            )
        else:
            # Optional field with default
            default_value = field.get_default_value() if has_default else None
            field_definitions[actual_field_name] = (
                advanced_input_type(field, Optional[python_type]),
                PydanticField(default=default_value, description=field.ai_description)
            )
    
    # Add ManyToMany fields as list of UUIDs (optional)
    if hasattr(model, '_m2m_fields'):
        for field_name, field in model._m2m_fields.items():
            field_definitions[field_name] = (
                Optional[List[UUID]],
                PydanticField(default=None, description=field.ai_description)
            )
    
    schema = create_model(
        cache_key,
        __base__=BaseModel,
        __config__=ConfigDict(extra="forbid"),
        **field_definitions
    )
    
    # Cache the schema
    if model_name not in _schema_cache:
        _schema_cache[model_name] = {}
    _schema_cache[model_name][cache_key] = schema
    
    return schema


def generate_update_schema(model: Type[Model]) -> Type[BaseModel]:
    """
    Generate a Pydantic Update schema for a Aksara model.
    
    The Update schema:
        - All fields are optional (partial updates)
        - Excludes PK and auto-timestamps
        - ManyToMany as optional list of UUIDs
    
    Args:
        model: Aksara Model class
        
    Returns:
        Pydantic model class for updates
    """
    model_name = model.__name__
    cache_key = f"{model_name}Update"
    
    if model_name in _schema_cache and cache_key in _schema_cache[model_name]:
        return _schema_cache[model_name][cache_key]
    
    field_definitions = {}
    
    for field_name, field in model._fields.items():
        if not _should_include_in_update(field_name, field):
            continue
        
        python_type = _get_python_type(field)
        
        # Handle ForeignKey - use the _id column name
        if isinstance(field, aksara_fields.ForeignKey):
            actual_field_name = field.db_column_name
        else:
            actual_field_name = field_name
        
        # All fields optional for update (partial update support)
        field_definitions[actual_field_name] = (
            advanced_input_type(field, Optional[python_type]),
            PydanticField(default=None, description=field.ai_description)
        )
    
    # Add ManyToMany fields as optional list of UUIDs
    if hasattr(model, '_m2m_fields'):
        for field_name, field in model._m2m_fields.items():
            field_definitions[field_name] = (
                Optional[List[UUID]],
                PydanticField(default=None, description=field.ai_description)
            )
    
    schema = create_model(
        cache_key,
        __base__=BaseModel,
        __config__=ConfigDict(extra="forbid"),
        **field_definitions
    )
    
    # Cache the schema
    if model_name not in _schema_cache:
        _schema_cache[model_name] = {}
    _schema_cache[model_name][cache_key] = schema
    
    return schema


def generate_read_schema(model: Type[Model]) -> Type[BaseModel]:
    """
    Generate a Pydantic Read schema for a Aksara model.
    
    The Read schema:
        - Includes all fields
        - All types are properly serialized
        - ManyToMany as list of UUIDs
    
    Args:
        model: Aksara Model class
        
    Returns:
        Pydantic model class for responses
    """
    model_name = model.__name__
    cache_key = f"{model_name}Read"
    
    if model_name in _schema_cache and cache_key in _schema_cache[model_name]:
        return _schema_cache[model_name][cache_key]
    
    field_definitions = {}
    
    for field_name, field in model._fields.items():
        if not _should_include_in_read(field_name, field):
            continue
        
        python_type = _get_python_type(field)
        
        # Handle ForeignKey - use the _id column name for serialization
        if isinstance(field, aksara_fields.ForeignKey):
            actual_field_name = field.db_column_name
        else:
            actual_field_name = field_name
        
        # Allow None for nullable fields
        if field.nullable:
            field_definitions[actual_field_name] = (
                Optional[python_type],
                PydanticField(description=field.ai_description)
            )
        else:
            field_definitions[actual_field_name] = (
                python_type,
                PydanticField(description=field.ai_description)
            )
    
    # Add ManyToMany fields as list of UUIDs
    if hasattr(model, '_m2m_fields'):
        for field_name, field in model._m2m_fields.items():
            field_definitions[field_name] = (
                Optional[List[UUID]],
                PydanticField(default=None, description=field.ai_description)
            )
    
    schema = create_model(
        cache_key,
        __base__=BaseModel,
        **field_definitions
    )
    
    # Enable ORM mode for model serialization
    schema.model_config = {"from_attributes": True}
    
    # Cache the schema
    if model_name not in _schema_cache:
        _schema_cache[model_name] = {}
    _schema_cache[model_name][cache_key] = schema
    
    return schema


def get_schemas_for_model(model: Type[Model]) -> Dict[str, Type[BaseModel]]:
    """
    Get all three schemas (Create, Update, Read) for a model.
    
    Args:
        model: Aksara Model class
        
    Returns:
        Dict with 'create', 'update', 'read' schema classes
    """
    return {
        "create": generate_create_schema(model),
        "update": generate_update_schema(model),
        "read": generate_read_schema(model),
    }


def clear_schema_cache() -> None:
    """Clear the schema cache. Useful for testing."""
    global _schema_cache
    _schema_cache = {}


def model_to_dict(instance: Model) -> Dict[str, Any]:
    """
    Convert a model instance to a dictionary suitable for Read schema.
    
    Handles:
        - UUID to string conversion
        - DateTime serialization
        - ForeignKey column name mapping
    
    Args:
        instance: Aksara model instance
        
    Returns:
        Dictionary representation
    """
    result = {}

    for field_name, field in instance._fields.items():
        value = instance._data.get(field_name)

        # Handle ForeignKey - use the _id column name
        if isinstance(field, aksara_fields.ForeignKey):
            key = field.db_column_name
        else:
            key = field_name

        # Serialize values
        if isinstance(value, UUID):
            result[key] = value
        else:
            result[key] = serialize_value(value)

    # Include ManyToMany fields so the serialized payload matches the
    # read schema, which declares them. Use cached IDs (from
    # create/update/prefetch_related) when available, else default to
    # None to keep the shape consistent with the schema's Optional
    # declaration.
    m2m_fields = getattr(instance.__class__, '_m2m_fields', None) or {}
    for field_name in m2m_fields:
        m2m_ids = getattr(instance, f'_{field_name}_ids', None)
        prefetched = None
        if hasattr(instance, '_prefetched_relations'):
            prefetched = instance._prefetched_relations.get(field_name)
        if m2m_ids is not None:
            result[field_name] = list(m2m_ids)
        elif prefetched is not None:
            result[field_name] = [
                getattr(obj, 'id', obj) for obj in prefetched
            ]
        else:
            result[field_name] = None

    return result


__all__ = [
    "generate_create_schema",
    "generate_update_schema", 
    "generate_read_schema",
    "get_schemas_for_model",
    "clear_schema_cache",
    "model_to_dict",
]
