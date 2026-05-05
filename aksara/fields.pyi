"""Type stub file for Aksara fields module.

This provides better IDE support for field types.
"""

from typing import TypeVar, Generic, Optional, Any, Callable, Union
from datetime import datetime
from uuid import UUID as PyUUID

T = TypeVar('T')


class Field(Generic[T]):
    """Base field type."""
    name: Optional[str]
    nullable: bool
    default: Any
    unique: bool
    primary_key: bool
    
    def get_default_value(self) -> T: ...
    def to_python(self, value: Any) -> T: ...
    def to_db(self, value: T) -> Any: ...
    def get_column_definition(self) -> str: ...
    @property
    def sql_type(self) -> str: ...


class String(Field[str]):
    """String field - maps to VARCHAR."""
    max_length: int
    
    def __init__(
        self,
        max_length: int = 255,
        *,
        nullable: bool = False,
        default: Optional[str] = None,
        unique: bool = False,
    ) -> None: ...


class Integer(Field[int]):
    """Integer field - maps to INTEGER."""
    
    def __init__(
        self,
        *,
        nullable: bool = False,
        default: Optional[int] = None,
        unique: bool = False,
    ) -> None: ...


class Boolean(Field[bool]):
    """Boolean field - maps to BOOLEAN."""
    
    def __init__(
        self,
        *,
        nullable: bool = False,
        default: Optional[bool] = None,
    ) -> None: ...


class DateTime(Field[datetime]):
    """DateTime field - maps to TIMESTAMP WITH TIME ZONE."""
    auto_now: bool
    auto_now_add: bool
    
    def __init__(
        self,
        *,
        auto_now: bool = False,
        auto_now_add: bool = False,
        nullable: bool = False,
    ) -> None: ...


class UUID(Field[PyUUID]):
    """UUID field - maps to UUID."""
    
    def __init__(
        self,
        *,
        primary_key: bool = False,
        nullable: bool = False,
        default: Optional[Union[PyUUID, Callable[[], PyUUID]]] = None,
    ) -> None: ...


class JSON(Field[Any]):
    """JSON field - maps to JSONB."""
    
    def __init__(
        self,
        *,
        nullable: bool = True,
        default: Optional[Any] = None,
    ) -> None: ...


class Vector(Field[list[float]]):
    """pgvector-backed embedding field."""

    dimensions: Optional[int]

    def __init__(
        self,
        dimensions: Optional[int] = None,
        *,
        nullable: bool = False,
        default: Optional[Any] = None,
    ) -> None: ...


class FileField(Field[str]):
    """File field storing a storage-relative path."""

    max_length: int

    def __init__(
        self,
        max_length: int = 500,
        *,
        upload_to: Any = "",
        storage: Any = None,
        nullable: bool = False,
        default: Optional[str] = None,
        unique: bool = False,
    ) -> None: ...


class ImageField(FileField):
    """Image-specialized file field."""


class GenericForeignKeyAccessor:
    """Async accessor for generic relations."""

    async def __call__(self) -> Any: ...
    async def set(self, value: Any) -> None: ...


class GenericForeignKey:
    """Virtual relation backed by content_type_id/object_id."""

    name: Optional[str]
    content_type_field: str
    object_id_field: str
    nullable: bool

    def __init__(
        self,
        *,
        content_type_field: str = "content_type_id",
        object_id_field: str = "object_id",
        nullable: bool = True,
        object_id_max_length: int = 255,
    ) -> None: ...


# Aliases
StringField = String
IntegerField = Integer
BooleanField = Boolean
DateTimeField = DateTime
UUIDField = UUID
JSONField = JSON
VectorField = Vector
GenericForeignKeyField = GenericForeignKey
