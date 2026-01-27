# Exceptions

Complete reference for Aksara exceptions.

---

## Exception Hierarchy

```
BaseException
└── Exception
    └── AksaraError
        ├── ConfigurationError
        ├── DatabaseError
        │   ├── ConnectionError
        │   ├── IntegrityError
        │   └── OperationalError
        ├── ValidationError
        ├── PermissionDenied
        ├── NotAuthenticated
        ├── NotFound
        ├── MethodNotAllowed
        ├── Throttled
        └── APIException
```

---

## Core Exceptions

### AksaraError

Base exception for all Aksara errors.

```python
from aksara.exceptions import AksaraError

try:
    # some operation
    pass
except AksaraError as e:
    print(f"Aksara error: {e}")
```

### ConfigurationError

Raised when configuration is invalid.

```python
from aksara.exceptions import ConfigurationError

raise ConfigurationError("DATABASE_URL is required")
```

---

## Database Exceptions

### DatabaseError

Base exception for database errors.

```python
from aksara.exceptions import DatabaseError

try:
    await Model.objects.raw("INVALID SQL")
except DatabaseError as e:
    print(f"Database error: {e}")
```

### ConnectionError

Raised when database connection fails.

```python
from aksara.exceptions import ConnectionError

try:
    await database.connect()
except ConnectionError as e:
    print("Could not connect to database")
```

### IntegrityError

Raised when database integrity constraints are violated.

```python
from aksara.exceptions import IntegrityError

try:
    await User.objects.create(email="existing@example.com")
except IntegrityError as e:
    print("Duplicate email address")
```

### OperationalError

Raised for operational database errors.

```python
from aksara.exceptions import OperationalError

try:
    await Model.objects.execute("...")
except OperationalError as e:
    print(f"Operational error: {e}")
```

---

## Model Exceptions

### DoesNotExist

Raised when a query expects a single object but finds none.

```python
from aksara.exceptions import DoesNotExist

# Model-specific exception
try:
    user = await User.objects.get(id="nonexistent")
except User.DoesNotExist:
    print("User not found")

# Generic exception
from aksara.exceptions import DoesNotExist
try:
    user = await User.objects.get(id="nonexistent")
except DoesNotExist:
    print("Object not found")
```

### MultipleObjectsReturned

Raised when a query expects a single object but finds multiple.

```python
from aksara.exceptions import MultipleObjectsReturned

try:
    user = await User.objects.get(name="John")
except MultipleObjectsReturned:
    print("Multiple users named John")
```

---

## Validation Exceptions

### ValidationError

Raised when data validation fails.

```python
from aksara.exceptions import ValidationError

# Single error
raise ValidationError("Invalid value")

# Field-specific errors
raise ValidationError({
    "email": "Invalid email format",
    "password": "Password too short",
})

# Multiple errors per field
raise ValidationError({
    "password": [
        "Password too short",
        "Password must contain a digit",
    ],
})

# Non-field errors
raise ValidationError({
    "__all__": "Invalid credentials",
})
```

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `detail` | dict/str | Error details |
| `status_code` | int | HTTP status (400) |

#### Handling

```python
from aksara.exceptions import ValidationError

try:
    await serializer.is_valid(raise_exception=True)
except ValidationError as e:
    print(e.detail)
    # {"email": ["Invalid email format"]}
```

---

## API Exceptions

### APIException

Base exception for API errors.

```python
from aksara.exceptions import APIException

raise APIException(
    detail="Something went wrong",
    status_code=500
)
```

#### Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `detail` | str | Required | Error message |
| `status_code` | int | 500 | HTTP status code |
| `code` | str | None | Error code |

### NotFound

Raised when a resource is not found (404).

```python
from aksara.exceptions import NotFound

raise NotFound("User not found")
raise NotFound(detail="Post not found")
```

### PermissionDenied

Raised when user lacks permission (403).

```python
from aksara.exceptions import PermissionDenied

raise PermissionDenied("You do not have permission to edit this post")
```

### NotAuthenticated

Raised when authentication is required (401).

```python
from aksara.exceptions import NotAuthenticated

raise NotAuthenticated("Authentication required")
```

### MethodNotAllowed

Raised when HTTP method is not allowed (405).

```python
from aksara.exceptions import MethodNotAllowed

raise MethodNotAllowed("GET")
```

### Throttled

Raised when rate limit is exceeded (429).

```python
from aksara.exceptions import Throttled

raise Throttled(wait=60)  # Retry after 60 seconds
```

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `wait` | int | Seconds until retry allowed |

---

## Migration Exceptions

### MigrationError

Raised for migration errors.

```python
from aksara.exceptions import MigrationError

raise MigrationError("Migration failed")
```

### ConflictingMigrations

Raised when migrations conflict.

```python
from aksara.exceptions import ConflictingMigrations

raise ConflictingMigrations(["0002_add_email", "0002_add_name"])
```

### MigrationNotFound

Raised when migration is not found.

```python
from aksara.exceptions import MigrationNotFound

raise MigrationNotFound("0003_update_users")
```

---

## Custom Exceptions

### Creating Custom Exceptions

```python
from aksara.exceptions import APIException

class PaymentError(APIException):
    status_code = 402
    default_detail = "Payment required"
    default_code = "payment_required"

class InsufficientFunds(PaymentError):
    default_detail = "Insufficient funds"
    default_code = "insufficient_funds"

# Usage
raise InsufficientFunds()
raise PaymentError("Card declined")
```

### Exception Handler

```python
from aksara.exceptions import exception_handler

@app.exception_handler(PaymentError)
async def handle_payment_error(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "code": exc.default_code,
        }
    )
```

---

## Error Response Format

Default API error response:

```json
{
    "detail": "Error message",
    "code": "error_code"
}
```

Validation error response:

```json
{
    "detail": {
        "email": ["Invalid email format"],
        "password": ["Too short", "Needs digit"]
    }
}
```

---

## HTTP Status Codes

| Exception | Status Code |
|-----------|-------------|
| `ValidationError` | 400 |
| `NotAuthenticated` | 401 |
| `PermissionDenied` | 403 |
| `NotFound` | 404 |
| `MethodNotAllowed` | 405 |
| `Throttled` | 429 |
| `APIException` | 500 |

---

## Best Practices

### Catching Exceptions

```python
# Specific exceptions first
try:
    user = await User.objects.get(id=user_id)
except User.DoesNotExist:
    raise NotFound("User not found")
except DatabaseError:
    raise APIException("Database error")
```

### Re-raising Exceptions

```python
try:
    result = await external_service.call()
except ExternalError as e:
    raise APIException(f"External service error: {e}")
```

### Logging Exceptions

```python
import logging

logger = logging.getLogger(__name__)

try:
    await dangerous_operation()
except AksaraError as e:
    logger.exception("Operation failed")
    raise
```

---

## Related Documentation

- [API Reference](api-reference.md)
- [Validation](../advanced/validation.md)
