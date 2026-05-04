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

from pydantic import BaseModel, Field as PydanticField, create_model

from aksara.model.base import Model
from aksara.i18n import serialize_value
from aksara import fields as aksara_fields


# Schema cache for performance
_schema_cache: Dict[str, Dict[str, Type[BaseModel]]] = {}


def _get_python_type(field: aksara_fields.Field) -> type:
    """
    Map Aksara field type to Python/Pydantic type.
    
    Args:
        field: Aksara field instance
        
    Returns:
        Python type for Pydantic schema
    """
    if isinstance(field, aksara_fields.UUID):
        return UUID
    elif isinstance(field, aksara_fields.FileField):
        return str
    elif isinstance(field, aksara_fields.String):
        return str
    elif isinstance(field, aksara_fields.Text):
        return str
    elif isinstance(field, aksara_fields.Email):
        return str
    elif isinstance(field, aksara_fields.URL):
        return str
    elif isinstance(field, aksara_fields.Integer):
        return int
    elif isinstance(field, aksara_fields.Boolean):
        return bool
    elif isinstance(field, aksara_fields.DateTime):
        return datetime
    elif isinstance(field, aksara_fields.JSON):
        return Union[dict, list, None]
    elif isinstance(field, aksara_fields.Decimal):
        return Decimal
    elif isinstance(field, aksara_fields.Enum):
        return str
    elif isinstance(field, aksara_fields.ForeignKey):
        return UUID
    elif isinstance(field, aksara_fields.ManyToMany):
        return List[UUID]
    else:
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
                python_type,
                PydanticField(description=field.ai_description)
            )
        else:
            # Optional field with default
            default_value = field.get_default_value() if has_default else None
            field_definitions[actual_field_name] = (
                Optional[python_type],
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
            Optional[python_type],
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
    
    return result


__all__ = [
    "generate_create_schema",
    "generate_update_schema", 
    "generate_read_schema",
    "get_schemas_for_model",
    "clear_schema_cache",
    "model_to_dict",
]
