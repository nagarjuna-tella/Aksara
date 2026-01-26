# Types

Type definitions for Vidyut.

---

## Overview

Vidyut is fully typed and provides type stubs for IDE support.

```python
# py.typed marker included
# Use with mypy, pyright, etc.
```

---

## Core Types

### Model Types

```python
from vidyut import Model
from typing import TypeVar, Generic

# Model type variable
ModelT = TypeVar("ModelT", bound=Model)

# Generic model type
class ModelViewSet(Generic[ModelT]):
    model: type[ModelT]
```

### ID Types

```python
from uuid import UUID
from typing import Union

# Primary key type
PK = Union[str, UUID]

# Model ID
class Model:
    id: UUID
    pk: UUID  # Alias for id
```

### QuerySet Types

```python
from typing import TypeVar, Generic, AsyncIterator, List, Optional

ModelT = TypeVar("ModelT", bound=Model)

class QuerySet(Generic[ModelT]):
    async def all(self) -> List[ModelT]: ...
    async def first(self) -> Optional[ModelT]: ...
    async def get(self, **kwargs) -> ModelT: ...
    async def filter(self, **kwargs) -> "QuerySet[ModelT]": ...
    async def count(self) -> int: ...
    async def exists(self) -> bool: ...
    def __aiter__(self) -> AsyncIterator[ModelT]: ...
```

---

## Field Types

### Basic Field Types

```python
from vidyut.fields import (
    StringField,
    IntegerField,
    FloatField,
    BooleanField,
    DateTimeField,
    DateField,
    UUIDField,
    TextField,
    EmailField,
    JSONField,
)

# Type inference
class User(Model):
    name: str = StringField(max_length=100)
    age: int = IntegerField()
    score: float = FloatField()
    is_active: bool = BooleanField(default=True)
    email: str = EmailField()
    metadata: dict = JSONField(default=dict)
```

### Optional Fields

```python
from typing import Optional
from datetime import datetime

class Post(Model):
    title: str = StringField(max_length=200)
    published_at: Optional[datetime] = DateTimeField(null=True)
```

### Relationship Types

```python
from vidyut.fields import ForeignKey, ManyToManyField
from typing import List

class Post(Model):
    author: "User" = ForeignKey("User", on_delete="CASCADE")
    tags: List["Tag"] = ManyToManyField("Tag", related_name="posts")
```

---

## API Types

### Request Types

```python
from typing import Any, Dict, Optional
from vidyut.api.request import Request

class Request:
    user: "User"
    data: Dict[str, Any]
    query_params: Dict[str, str]
    headers: Dict[str, str]
    method: str
    path: str
```

### Response Types

```python
from typing import Any, Dict, Optional, Union, Tuple

# Response can be:
ResponseType = Union[
    Dict[str, Any],                    # JSON dict
    Tuple[Dict[str, Any], int],        # Dict with status code
    "Response",                         # Response object
]
```

### Serializer Types

```python
from typing import TypeVar, Generic, Type, Dict, Any, List

ModelT = TypeVar("ModelT", bound=Model)

class ModelSerializer(Generic[ModelT]):
    class Meta:
        model: Type[ModelT]
        fields: Union[List[str], str]
    
    async def is_valid(self, raise_exception: bool = False) -> bool: ...
    async def save(self, **kwargs) -> ModelT: ...
    @property
    def data(self) -> Dict[str, Any]: ...
    @property
    def errors(self) -> Dict[str, List[str]]: ...
```

### ViewSet Types

```python
from typing import TypeVar, Generic, Type, List, Optional

ModelT = TypeVar("ModelT", bound=Model)

class ModelViewSet(Generic[ModelT]):
    model: Type[ModelT]
    serializer_class: Type[ModelSerializer[ModelT]]
    permission_classes: List[Type["BasePermission"]]
    
    def get_queryset(self) -> QuerySet[ModelT]: ...
    async def get_object(self) -> ModelT: ...
```

---

## Permission Types

```python
from typing import Protocol

class BasePermission(Protocol):
    async def has_permission(
        self,
        request: "Request",
        view: "ViewSet"
    ) -> bool: ...
    
    async def has_object_permission(
        self,
        request: "Request",
        view: "ViewSet",
        obj: Model
    ) -> bool: ...
```

---

## Pagination Types

```python
from typing import TypedDict, List, Any, Optional

class PagedResponse(TypedDict):
    count: int
    next: Optional[str]
    previous: Optional[str]
    results: List[Any]
```

---

## Filter Types

```python
from typing import Dict, Any, TypeVar

FilterValue = Any
FilterDict = Dict[str, FilterValue]
```

---

## Cache Types

```python
from typing import TypeVar, Optional, Any, Callable, Awaitable

T = TypeVar("T")
CacheKey = str
CacheTTL = int

class Cache:
    async def get(self, key: CacheKey, default: T = None) -> Optional[T]: ...
    async def set(self, key: CacheKey, value: Any, ttl: CacheTTL = None) -> None: ...
    async def delete(self, key: CacheKey) -> None: ...
```

---

## Signal Types

```python
from typing import Callable, Awaitable, Any, TypeVar

ModelT = TypeVar("ModelT", bound=Model)

SignalHandler = Callable[..., Awaitable[None]]

class Signal:
    def connect(
        self,
        handler: SignalHandler,
        sender: type[ModelT] = None
    ) -> None: ...
    
    async def send(
        self,
        sender: type[ModelT],
        **kwargs: Any
    ) -> None: ...
```

---

## AI Types

```python
from typing import TypedDict, List, Optional, Any

class QueryResult(TypedDict):
    data: List[Any]
    count: int
    sql: str

class SchemaIssue(TypedDict):
    severity: str  # "critical", "high", "medium", "low"
    message: str
    fix_hint: Optional[str]
    model: str
    field: Optional[str]

class AgentResult(TypedDict):
    output: str
    session_id: str
    steps: List[str]
```

---

## Utility Types

### Settings Type

```python
from typing import TypedDict, List, Dict, Any, Optional

class VidyutSettings(TypedDict, total=False):
    DEBUG: bool
    SECRET_KEY: str
    DATABASE_URL: str
    INSTALLED_APPS: List[str]
    MIDDLEWARE: List[str]
    CACHE: Dict[str, Any]
    AI_MODE: bool
    AI_API_KEY: Optional[str]
```

### Callable Types

```python
from typing import Callable, Awaitable, TypeVar

T = TypeVar("T")

# Async function
AsyncFunc = Callable[..., Awaitable[T]]

# Validator
Validator = Callable[[Any], Any]

# Async validator
AsyncValidator = Callable[[Any], Awaitable[Any]]
```

---

## Type Checking

### Using mypy

```bash
# Install
pip install mypy

# Run
mypy myapp/

# Configuration in pyproject.toml
[tool.mypy]
plugins = ["vidyut.mypy"]
strict = true
```

### Using pyright

```bash
# Install
pip install pyright

# Run
pyright myapp/

# Configuration in pyrightconfig.json
{
    "typeCheckingMode": "strict"
}
```

---

## Type Stubs

Vidyut includes inline type annotations and a `py.typed` marker. Type stubs are available for all public APIs.

```python
# Example stub (fields.pyi)
from typing import TypeVar, Generic, Optional, Any

T = TypeVar("T")

class Field(Generic[T]):
    def __init__(
        self,
        null: bool = False,
        default: Optional[T] = None,
        unique: bool = False,
        db_index: bool = False,
        validators: list = ...,
        **kwargs: Any
    ) -> None: ...
    
    def __get__(self, obj: Any, type: Any = None) -> T: ...
    def __set__(self, obj: Any, value: T) -> None: ...

class StringField(Field[str]):
    def __init__(
        self,
        max_length: int = ...,
        min_length: int = ...,
        **kwargs: Any
    ) -> None: ...

class IntegerField(Field[int]): ...
class FloatField(Field[float]): ...
class BooleanField(Field[bool]): ...
```

---

## Related Documentation

- [ORM Reference](orm-reference.md)
- [API Reference](api-reference.md)
- [Custom Fields](../advanced/custom-fields.md)
