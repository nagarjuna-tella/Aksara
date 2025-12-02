"""
ModelSerializer - Django/DRF-style Serializer Abstraction

Provides a thin, optional layer on top of Pydantic for developers familiar
with Django REST Framework's serializer patterns.

Features:
    - Meta class API: model, fields, exclude, read_only_fields, expand
    - Validation hooks: validate_<field>(), validate()
    - Async save/create/update methods
    - Nested FK expansion via expand
    - ManyToMany handling (accepts list of UUIDs)
    - Automatic Pydantic model generation

Usage:
    from vidyut.api import ModelSerializer

    class UserSerializer(ModelSerializer):
        class Meta:
            model = User
            fields = ["id", "email", "name", "is_active"]
            read_only_fields = ["id", "created_at"]

        def validate_email(self, value):
            if not "@" in value:
                raise ValueError("Invalid email format")
            return value.lower()

    # Create a new user
    serializer = UserSerializer(data={"email": "user@example.com", "name": "John"})
    if serializer.is_valid():
        user = await serializer.save()

    # Serialize existing instance
    serializer = UserSerializer(instance=user)
    data = serializer.to_representation()
"""

from __future__ import annotations

import inspect
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Type, Union, get_type_hints, TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, Field as PydanticField, ValidationError, create_model

from vidyut.model.base import Model
from vidyut import fields as vidyut_fields


if TYPE_CHECKING:
    from vidyut.manager import Manager


# Cache for generated Pydantic models per serializer class
_serializer_model_cache: Dict[str, Dict[str, Type[BaseModel]]] = {}


def _get_python_type(field: vidyut_fields.Field) -> type:
    """
    Map Vidyut field type to Python/Pydantic type.
    
    Args:
        field: Vidyut field instance
        
    Returns:
        Python type for Pydantic schema
    """
    if isinstance(field, vidyut_fields.UUID):
        return UUID
    elif isinstance(field, vidyut_fields.String):
        return str
    elif isinstance(field, vidyut_fields.Text):
        return str
    elif isinstance(field, vidyut_fields.Email):
        return str
    elif isinstance(field, vidyut_fields.URL):
        return str
    elif isinstance(field, vidyut_fields.Integer):
        return int
    elif isinstance(field, vidyut_fields.Boolean):
        return bool
    elif isinstance(field, vidyut_fields.DateTime):
        return datetime
    elif isinstance(field, vidyut_fields.JSON):
        return Union[dict, list, None]
    elif isinstance(field, vidyut_fields.Decimal):
        return Decimal
    elif isinstance(field, vidyut_fields.Enum):
        return str
    elif isinstance(field, vidyut_fields.ForeignKey):
        return UUID
    elif isinstance(field, vidyut_fields.ManyToMany):
        return List[UUID]
    else:
        return Any


class SerializerMetaclass(type):
    """
    Metaclass for ModelSerializer that validates Meta class.
    """
    
    def __new__(mcs, name: str, bases: tuple, namespace: dict, **kwargs):
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        
        # Skip validation for the base class
        if name == 'ModelSerializer':
            return cls
        
        # Validate Meta class exists and has required attributes
        meta = getattr(cls, 'Meta', None)
        if meta is None:
            raise TypeError(f"{name} must define an inner Meta class")
        
        model = getattr(meta, 'model', None)
        if model is None:
            raise TypeError(f"{name}.Meta must define 'model' attribute")
        
        fields = getattr(meta, 'fields', None)
        if fields is None:
            raise TypeError(f"{name}.Meta must define 'fields' attribute")
        
        return cls


class ModelSerializer(metaclass=SerializerMetaclass):
    """
    Thin abstraction around a generated Pydantic model,
    configured via an inner Meta class.
    
    Provides Django REST Framework-like API for serialization
    and validation while using Pydantic under the hood.
    
    Attributes:
        instance: Model instance being serialized (for reads)
        initial_data: Raw data being deserialized (for writes)
        many: Whether to handle multiple instances
        context: Additional context (e.g., request)
    """
    
    class Meta:
        model: Type[Model] = None  # Required: Vidyut Model subclass
        fields: Union[str, List[str]] = None  # "__all__" or list of field names
        exclude: Optional[List[str]] = None  # Fields to exclude
        read_only_fields: List[str] = []  # Fields in output only
        expand: Union[List[str], Dict[str, Type["ModelSerializer"]]] = []  # FK expansion
    
    def __init__(
        self,
        instance: Optional[Union[Model, List[Model]]] = None,
        data: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
        many: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the serializer.
        
        Args:
            instance: Model instance(s) for serialization
            data: Raw data for deserialization/validation
            many: Whether to handle multiple instances/items
            context: Additional context (e.g., {"request": request})
        """
        self.instance = instance
        self.initial_data = data
        self.many = many
        self.context = context or {}
        self._validated_data: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None
        self._errors: Optional[Dict[str, Any]] = None
        
        # Get model from Meta
        self._model = self.Meta.model
        
        # Generate/cache Pydantic models
        self._input_model = self._get_or_create_input_model()
        self._output_model = self._get_or_create_output_model()
    
    # =========================================================================
    # Pydantic Model Generation
    # =========================================================================
    
    @classmethod
    def _get_cache_key(cls) -> str:
        """Get unique cache key for this serializer class."""
        return f"{cls.__module__}.{cls.__name__}"
    
    @classmethod
    def _get_field_names(cls) -> List[str]:
        """
        Get the list of field names to include.
        
        Respects fields and exclude settings.
        """
        meta = cls.Meta
        model = meta.model
        
        # Start with all model fields
        if meta.fields == "__all__":
            field_names = list(model._fields.keys())
        else:
            field_names = list(meta.fields)
        
        # Apply exclusions
        exclude = getattr(meta, 'exclude', None) or []
        field_names = [f for f in field_names if f not in exclude]
        
        return field_names
    
    @classmethod
    def _get_or_create_input_model(cls) -> Type[BaseModel]:
        """
        Get or create the Pydantic model for input validation.
        
        Read-only fields are excluded from the input model.
        """
        cache_key = cls._get_cache_key()
        
        if cache_key in _serializer_model_cache:
            if "input" in _serializer_model_cache[cache_key]:
                return _serializer_model_cache[cache_key]["input"]
        
        meta = cls.Meta
        model = meta.model
        read_only = set(getattr(meta, 'read_only_fields', []))
        field_names = cls._get_field_names()
        
        field_definitions = {}
        
        for field_name in field_names:
            # Skip read-only fields in input
            if field_name in read_only:
                continue
            
            if field_name not in model._fields:
                continue
            
            field = model._fields[field_name]
            
            # Skip auto-generated fields
            if field.primary_key:
                continue
            if isinstance(field, vidyut_fields.DateTime):
                if field.auto_now or field.auto_now_add:
                    continue
            
            python_type = _get_python_type(field)
            
            # Handle ForeignKey - use the _id column name
            if isinstance(field, vidyut_fields.ForeignKey):
                actual_field_name = field.db_column_name
            else:
                actual_field_name = field_name
            
            # Determine if field is required
            has_default = field.default is not None or callable(field.default)
            is_required = not field.nullable and not has_default
            
            if is_required:
                field_definitions[actual_field_name] = (
                    python_type,
                    PydanticField(description=field.ai_description)
                )
            else:
                default_value = field.get_default_value() if has_default else None
                field_definitions[actual_field_name] = (
                    Optional[python_type],
                    PydanticField(default=default_value, description=field.ai_description)
                )
        
        # Add ManyToMany fields as Optional[List[UUID]]
        if hasattr(model, '_m2m_fields'):
            for field_name, field in model._m2m_fields.items():
                # M2M fields are always optional on input
                field_definitions[field_name] = (
                    Optional[List[UUID]],
                    PydanticField(default=None, description=getattr(field, 'ai_description', None))
                )
        
        input_model = create_model(
            f"{cls.__name__}Input",
            __base__=BaseModel,
            **field_definitions
        )
        
        # Cache it
        if cache_key not in _serializer_model_cache:
            _serializer_model_cache[cache_key] = {}
        _serializer_model_cache[cache_key]["input"] = input_model
        
        return input_model
    
    @classmethod
    def _get_or_create_output_model(cls) -> Type[BaseModel]:
        """
        Get or create the Pydantic model for output serialization.
        
        Includes all fields including read-only ones.
        """
        cache_key = cls._get_cache_key()
        
        if cache_key in _serializer_model_cache:
            if "output" in _serializer_model_cache[cache_key]:
                return _serializer_model_cache[cache_key]["output"]
        
        meta = cls.Meta
        model = meta.model
        field_names = cls._get_field_names()
        
        field_definitions = {}
        
        for field_name in field_names:
            if field_name not in model._fields:
                continue
            
            field = model._fields[field_name]
            python_type = _get_python_type(field)
            
            # Handle ForeignKey - use the _id column name
            if isinstance(field, vidyut_fields.ForeignKey):
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
        
        # Add ManyToMany fields as Optional[List[UUID]]
        if hasattr(model, '_m2m_fields'):
            for field_name, field in model._m2m_fields.items():
                field_definitions[field_name] = (
                    Optional[List[UUID]],
                    PydanticField(default=None, description=getattr(field, 'ai_description', None))
                )
        
        output_model = create_model(
            f"{cls.__name__}Output",
            __base__=BaseModel,
            **field_definitions
        )
        
        # Enable ORM mode
        output_model.model_config = {"from_attributes": True}
        
        # Cache it
        if cache_key not in _serializer_model_cache:
            _serializer_model_cache[cache_key] = {}
        _serializer_model_cache[cache_key]["output"] = output_model
        
        return output_model
    
    def get_input_model(self) -> Type[BaseModel]:
        """Get the Pydantic model for input validation."""
        return self._input_model
    
    def get_output_model(self) -> Type[BaseModel]:
        """Get the Pydantic model for output serialization."""
        return self._output_model
    
    # =========================================================================
    # Validation
    # =========================================================================
    
    def is_valid(self, raise_exception: bool = False) -> bool:
        """
        Validate the initial data.
        
        Runs:
            1. Pydantic model validation
            2. validate_<field>() methods for each field
            3. validate() method for cross-field validation
        
        Args:
            raise_exception: If True, raise ValidationError on failure
            
        Returns:
            True if valid, False otherwise
        """
        if self.initial_data is None:
            self._errors = {"non_field_errors": ["No data provided"]}
            if raise_exception:
                raise ValueError("No data provided")
            return False
        
        try:
            if self.many:
                validated = self._validate_many(self.initial_data)
            else:
                validated = self._validate_single(self.initial_data)
            
            self._validated_data = validated
            self._errors = None
            return True
            
        except ValidationError as e:
            self._errors = self._format_pydantic_errors(e)
            if raise_exception:
                raise
            return False
        except ValueError as e:
            self._errors = {"non_field_errors": [str(e)]}
            if raise_exception:
                raise
            return False
    
    def _validate_single(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a single item."""
        # Step 1: Pydantic validation
        pydantic_instance = self._input_model(**data)
        validated = pydantic_instance.model_dump()
        
        # Step 2: Field-level validation hooks
        for field_name, value in validated.items():
            validator_method = getattr(self, f"validate_{field_name}", None)
            if validator_method is not None:
                validated[field_name] = validator_method(value)
        
        # Step 3: Cross-field validation
        validated = self.validate(validated)
        
        return validated
    
    def _validate_many(self, data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate multiple items."""
        if not isinstance(data_list, list):
            raise ValueError("Expected a list for many=True")
        
        return [self._validate_single(item) for item in data_list]
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cross-field validation hook.
        
        Override this method to add custom validation logic
        that depends on multiple fields.
        
        Args:
            data: Dictionary of validated field values
            
        Returns:
            The (possibly modified) validated data
            
        Raises:
            ValueError: If validation fails
        """
        return data
    
    def _format_pydantic_errors(self, error: ValidationError) -> Dict[str, List[str]]:
        """Format Pydantic validation errors to a dict."""
        errors = {}
        for err in error.errors():
            field = ".".join(str(loc) for loc in err["loc"])
            if field not in errors:
                errors[field] = []
            errors[field].append(err["msg"])
        return errors
    
    @property
    def validated_data(self) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Get validated data.
        
        Only available after is_valid() returns True.
        
        Returns:
            Validated data dictionary (or list if many=True)
            
        Raises:
            AssertionError: If is_valid() hasn't been called
        """
        if self._validated_data is None:
            raise AssertionError(
                "You must call `.is_valid()` before accessing `.validated_data`."
            )
        return self._validated_data
    
    @property
    def errors(self) -> Optional[Dict[str, Any]]:
        """Get validation errors."""
        return self._errors
    
    # =========================================================================
    # Save / Create / Update
    # =========================================================================
    
    async def save(self, **kwargs) -> Union[Model, List[Model]]:
        """
        Save the validated data.
        
        If instance is provided, updates it. Otherwise creates new.
        
        Args:
            **kwargs: Additional fields to include in save
            
        Returns:
            Created or updated model instance(s)
        """
        if self._validated_data is None:
            raise AssertionError(
                "You must call `.is_valid()` before calling `.save()`."
            )
        
        if self.many:
            return await self._save_many(**kwargs)
        else:
            return await self._save_single(**kwargs)
    
    async def _save_single(self, **kwargs) -> Model:
        """Save a single instance."""
        validated = {**self._validated_data, **kwargs}
        
        if self.instance is not None:
            return await self.update(self.instance, validated)
        else:
            return await self.create(validated)
    
    async def _save_many(self, **kwargs) -> List[Model]:
        """Save multiple instances."""
        results = []
        instances = self.instance if self.instance else [None] * len(self._validated_data)
        
        for i, validated in enumerate(self._validated_data):
            data = {**validated, **kwargs}
            instance = instances[i] if i < len(instances) else None
            
            if instance is not None:
                result = await self.update(instance, data)
            else:
                result = await self.create(data)
            results.append(result)
        
        return results
    
    async def create(self, validated_data: Dict[str, Any]) -> Model:
        """
        Create a new instance.
        
        Override this method to customize creation logic.
        Handles ManyToMany fields by applying them after instance creation.
        
        Args:
            validated_data: Validated data dictionary
            
        Returns:
            Created model instance
        """
        # Extract M2M data before creating instance
        m2m_data = {}
        create_data = {}
        
        m2m_field_names = set(getattr(self._model, '_m2m_fields', {}).keys())
        
        for key, value in validated_data.items():
            if key in m2m_field_names:
                m2m_data[key] = value
            else:
                create_data[key] = value
        
        # Create the instance
        instance = await self._model.objects.create(**create_data)
        
        # Apply M2M relationships
        for field_name, ids in m2m_data.items():
            if ids:
                m2m_manager = getattr(instance, field_name)
                # Get target model and fetch instances
                target_model = self._model._m2m_fields[field_name].to_model
                instances = []
                for id_val in ids:
                    try:
                        obj = await target_model.objects.get(id=id_val)
                        instances.append(obj)
                    except Exception:
                        pass  # Skip invalid IDs
                if instances:
                    await m2m_manager.add(*instances)
                # Store IDs for serialization
                setattr(instance, f'_{field_name}_ids', [inst.id for inst in instances])
        
        return instance
    
    async def update(self, instance: Model, validated_data: Dict[str, Any]) -> Model:
        """
        Update an existing instance.
        
        Override this method to customize update logic.
        Handles ManyToMany fields by replacing them.
        
        Args:
            instance: Existing model instance
            validated_data: Validated data dictionary
            
        Returns:
            Updated model instance
        """
        # Extract M2M data before updating instance
        m2m_data = {}
        update_data = {}
        
        m2m_field_names = set(getattr(self._model, '_m2m_fields', {}).keys())
        
        for key, value in validated_data.items():
            if key in m2m_field_names:
                m2m_data[key] = value
            else:
                update_data[key] = value
        
        # Update regular fields
        for key, value in update_data.items():
            if value is not None:
                setattr(instance, key, value)
        
        await instance.save()
        
        # Apply M2M relationships (replace)
        for field_name, ids in m2m_data.items():
            if ids is not None:  # Allow empty list to clear
                m2m_manager = getattr(instance, field_name)
                # Get target model and fetch instances
                target_model = self._model._m2m_fields[field_name].to_model
                instances = []
                for id_val in ids:
                    try:
                        obj = await target_model.objects.get(id=id_val)
                        instances.append(obj)
                    except Exception:
                        pass  # Skip invalid IDs
                await m2m_manager.set(instances)
                # Store IDs for serialization
                setattr(instance, f'_{field_name}_ids', [inst.id for inst in instances])
        
        return instance
    
    # =========================================================================
    # Serialization (to_representation)
    # =========================================================================
    
    def to_representation(self, instance: Optional[Model] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Convert model instance(s) to dictionary representation.
        
        Handles:
            - Field serialization via output model
            - FK expansion via Meta.expand
            - many=True for lists
        
        Args:
            instance: Model instance to serialize (uses self.instance if None)
            
        Returns:
            Dictionary representation (or list if many=True)
        """
        target = instance if instance is not None else self.instance
        
        if target is None:
            return {} if not self.many else []
        
        if self.many:
            if not isinstance(target, (list, tuple)):
                target = list(target)
            return [self._serialize_instance(item) for item in target]
        else:
            return self._serialize_instance(target)
    
    def _serialize_instance(self, instance: Model) -> Dict[str, Any]:
        """
        Serialize a single model instance.
        
        Args:
            instance: Model instance
            
        Returns:
            Dictionary representation
        """
        result = {}
        field_names = self._get_field_names()
        
        for field_name in field_names:
            if field_name not in instance._fields:
                continue
            
            field = instance._fields[field_name]
            value = instance._data.get(field_name)
            
            # Handle ForeignKey - use the _id column name
            if isinstance(field, vidyut_fields.ForeignKey):
                key = field.db_column_name
            else:
                key = field_name
            
            # Serialize value
            if isinstance(value, UUID):
                result[key] = value
            elif isinstance(value, datetime):
                result[key] = value
            else:
                result[key] = value
        
        # Include ManyToMany field IDs if cached
        if hasattr(instance.__class__, '_m2m_fields'):
            for field_name in instance.__class__._m2m_fields.keys():
                # Check if M2M IDs were pre-loaded during create/update
                m2m_ids = getattr(instance, f'_{field_name}_ids', None)
                if m2m_ids is not None:
                    result[field_name] = list(m2m_ids)
        
        # Handle FK expansion
        self._expand_relations(instance, result)
        
        return result
    
    def _expand_relations(self, instance: Model, result: Dict[str, Any]) -> None:
        """
        Expand FK and M2M relations if configured in Meta.expand.
        
        Uses prefetched relations when available to avoid N+1 queries.
        For null FK values, returns null (not an error).
        For empty M2M relations, returns empty list.
        
        Args:
            instance: Model instance
            result: Dictionary being built (modified in place)
        """
        expand = getattr(self.Meta, 'expand', [])
        
        if not expand:
            return
        
        # Normalize expand to dict format
        if isinstance(expand, list):
            expand_config = {name: None for name in expand}
        else:
            expand_config = expand
        
        for relation_name, serializer_cls in expand_config.items():
            # Check if it's a FK/O2O field
            if relation_name in instance._fk_fields:
                field = instance._fk_fields[relation_name]
                
                # Check if the FK value itself is null
                fk_value = instance._data.get(relation_name)
                if fk_value is None:
                    result[relation_name] = None
                    continue
                
                # Check for prefetched relation first (from select_related/prefetch_for_serializer)
                related_obj = None
                if hasattr(instance, '_prefetched_relations') and relation_name in instance._prefetched_relations:
                    related_obj = instance._prefetched_relations[relation_name]
                else:
                    # Fall back to legacy cache mechanisms
                    related_obj = getattr(instance, f"_{relation_name}_cache", None)
                    if related_obj is None:
                        related_obj = instance._data.get(f"_{relation_name}_obj")
                
                if related_obj is not None:
                    if serializer_cls is not None:
                        nested_serializer = serializer_cls(instance=related_obj)
                        result[relation_name] = nested_serializer.to_representation()
                    else:
                        result[relation_name] = _model_to_dict(related_obj)
                # If related_obj is None, keep the _id field in result
                
            # Check if it's a M2M field
            elif hasattr(instance, '_m2m_fields') and relation_name in instance._m2m_fields:
                related_list = []
                
                # Check for prefetched relation first
                if hasattr(instance, '_prefetched_relations') and relation_name in instance._prefetched_relations:
                    related_list = instance._prefetched_relations[relation_name]
                else:
                    # Fall back to cached IDs from create/update
                    m2m_ids = getattr(instance, f'_{relation_name}_ids', None)
                    if m2m_ids is not None:
                        result[relation_name] = list(m2m_ids)
                        continue
                
                # Serialize the related objects
                if related_list:
                    if serializer_cls is not None:
                        result[relation_name] = [
                            serializer_cls(instance=obj).to_representation()
                            for obj in related_list
                        ]
                    else:
                        result[relation_name] = [
                            _model_to_dict(obj)
                            for obj in related_list
                        ]
                else:
                    result[relation_name] = []
    
    # =========================================================================
    # Properties
    # =========================================================================
    
    @property
    def data(self) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Get the serialized representation.
        
        If instance was provided, returns the serialized instance.
        If save() was called, returns the serialized created/updated instance.
        
        Returns:
            Dictionary representation
        """
        return self.to_representation()


def _model_to_dict(instance: Model) -> Dict[str, Any]:
    """
    Convert a model instance to a dictionary.
    
    Args:
        instance: Model instance
        
    Returns:
        Dictionary representation
    """
    result = {}
    
    for field_name, field in instance._fields.items():
        value = instance._data.get(field_name)
        
        # Handle ForeignKey - use the _id column name
        if isinstance(field, vidyut_fields.ForeignKey):
            key = field.db_column_name
        else:
            key = field_name
        
        result[key] = value
    
    return result


def serialize_instance(
    instance: Model,
    serializer_or_schema: Union[Type[ModelSerializer], Type[BaseModel]],
) -> Dict[str, Any]:
    """
    Serialize a model instance using a serializer or Pydantic schema.
    
    Args:
        instance: Model instance to serialize
        serializer_or_schema: Serializer class or Pydantic model
        
    Returns:
        Dictionary representation
    """
    if isinstance(serializer_or_schema, type) and issubclass(serializer_or_schema, ModelSerializer):
        serializer = serializer_or_schema(instance=instance)
        return serializer.to_representation()
    else:
        # Assume it's a Pydantic model
        return _model_to_dict(instance)


def serialize_many(
    instances: List[Model],
    serializer_or_schema: Union[Type[ModelSerializer], Type[BaseModel]],
) -> List[Dict[str, Any]]:
    """
    Serialize multiple model instances.
    
    Args:
        instances: List of model instances
        serializer_or_schema: Serializer class or Pydantic model
        
    Returns:
        List of dictionary representations
    """
    if isinstance(serializer_or_schema, type) and issubclass(serializer_or_schema, ModelSerializer):
        serializer = serializer_or_schema(instance=instances, many=True)
        return serializer.to_representation()
    else:
        return [_model_to_dict(inst) for inst in instances]


def clear_serializer_cache() -> None:
    """Clear the serializer model cache. Useful for testing."""
    global _serializer_model_cache
    _serializer_model_cache = {}


__all__ = [
    "ModelSerializer",
    "serialize_instance",
    "serialize_many",
    "clear_serializer_cache",
]
