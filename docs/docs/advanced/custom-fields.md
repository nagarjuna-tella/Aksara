# Custom Fields

Create specialized field types for your application.

---

## Overview

Aksara's field system is extensible. You can create custom fields for:

- Domain-specific data types (phone numbers, currencies)
- Complex validation
- Custom serialization
- Database-specific types

---

## Basic Custom Field

### Field Structure

```python
from aksara.fields import Field
from aksara.exceptions import ValidationError

class PercentageField(Field):
    """Field for percentage values (0-100)."""
    
    def __init__(self, min_value=0, max_value=100, **kwargs):
        self.min_value = min_value
        self.max_value = max_value
        super().__init__(**kwargs)
    
    def validate(self, value):
        """Validate the value."""
        if value is None and self.null:
            return None
        
        if not isinstance(value, (int, float)):
            raise ValidationError("Must be a number")
        
        if value < self.min_value or value > self.max_value:
            raise ValidationError(
                f"Must be between {self.min_value} and {self.max_value}"
            )
        
        return float(value)
    
    def to_db(self, value):
        """Convert to database representation."""
        if value is None:
            return None
        return float(value)
    
    def from_db(self, value):
        """Convert from database representation."""
        if value is None:
            return None
        return float(value)
    
    def get_db_type(self):
        """Return the database column type."""
        return "REAL"
```

### Using the Field

```python
class Product(Model):
    name = fields.String(max_length=100)
    discount = PercentageField(default=0)

# Usage
product = Product(name="Widget", discount=25.5)
await product.save()
```

---

## Field Methods

### Required Methods

| Method | Purpose |
|--------|---------|
| `validate(value)` | Validate and clean the value |
| `to_db(value)` | Convert Python → Database |
| `from_db(value)` | Convert Database → Python |
| `get_db_type()` | Database column type |

### Optional Methods

| Method | Purpose |
|--------|---------|
| `get_default()` | Return the default value |
| `contribute_to_class(cls, name)` | Called when field is added to model |
| `deconstruct()` | For migrations |
| `__get__` / `__set__` | Descriptor protocol |

---

## Practical Examples

### Phone Number Field

```python
import re
from aksara.fields import Field
from aksara.exceptions import ValidationError

class PhoneField(Field):
    """Phone number field with validation."""
    
    PHONE_REGEX = re.compile(r'^\+?1?\d{9,15}$')
    
    def __init__(self, region="US", **kwargs):
        self.region = region
        super().__init__(**kwargs)
    
    def validate(self, value):
        if value is None:
            if self.null:
                return None
            raise ValidationError("Phone number is required")
        
        # Normalize: remove spaces, dashes, parentheses
        normalized = re.sub(r'[\s\-\(\)]', '', str(value))
        
        if not self.PHONE_REGEX.match(normalized):
            raise ValidationError("Invalid phone number format")
        
        return normalized
    
    def to_db(self, value):
        return value
    
    def from_db(self, value):
        return value
    
    def get_db_type(self):
        return "VARCHAR(20)"

# Usage
class Contact(Model):
    name = fields.String(max_length=100)
    phone = PhoneField()
    alt_phone = PhoneField(null=True)
```

### Money Field

```python
from decimal import Decimal
from aksara.fields import Field
from aksara.exceptions import ValidationError

class MoneyField(Field):
    """Field for monetary values."""
    
    def __init__(self, currency="USD", max_digits=10, decimal_places=2, **kwargs):
        self.currency = currency
        self.max_digits = max_digits
        self.decimal_places = decimal_places
        super().__init__(**kwargs)
    
    def validate(self, value):
        if value is None:
            if self.null:
                return None
            raise ValidationError("Value is required")
        
        try:
            decimal_value = Decimal(str(value))
        except:
            raise ValidationError("Invalid monetary value")
        
        if decimal_value < 0:
            raise ValidationError("Value cannot be negative")
        
        # Round to decimal places
        return decimal_value.quantize(Decimal(10) ** -self.decimal_places)
    
    def to_db(self, value):
        if value is None:
            return None
        # Store as integer cents for precision
        return int(value * (10 ** self.decimal_places))
    
    def from_db(self, value):
        if value is None:
            return None
        return Decimal(value) / (10 ** self.decimal_places)
    
    def get_db_type(self):
        return "BIGINT"

# Usage
class Order(Model):
    total = MoneyField(currency="USD")
    tax = MoneyField(currency="USD", default=Decimal("0.00"))
```

### Encrypted Field

```python
from cryptography.fernet import Fernet
from aksara.fields import Field
from aksara.conf import settings

class EncryptedField(Field):
    """Field that encrypts data at rest."""
    
    def __init__(self, **kwargs):
        self._fernet = None
        super().__init__(**kwargs)
    
    @property
    def fernet(self):
        if self._fernet is None:
            key = settings.ENCRYPTION_KEY.encode()
            self._fernet = Fernet(key)
        return self._fernet
    
    def validate(self, value):
        if value is None and self.null:
            return None
        return str(value)
    
    def to_db(self, value):
        if value is None:
            return None
        return self.fernet.encrypt(value.encode()).decode()
    
    def from_db(self, value):
        if value is None:
            return None
        return self.fernet.decrypt(value.encode()).decode()
    
    def get_db_type(self):
        return "TEXT"

# Usage
class User(Model):
    email = fields.Email()
    ssn = EncryptedField()  # Encrypted at rest
```

### Enum Field

```python
from enum import Enum
from aksara.fields import Field
from aksara.exceptions import ValidationError

class EnumField(Field):
    """Field for Python enums."""
    
    def __init__(self, enum_class, **kwargs):
        self.enum_class = enum_class
        super().__init__(**kwargs)
    
    def validate(self, value):
        if value is None:
            if self.null:
                return None
            raise ValidationError("Value is required")
        
        # Accept enum member or string value
        if isinstance(value, self.enum_class):
            return value
        
        try:
            return self.enum_class(value)
        except ValueError:
            valid = [e.value for e in self.enum_class]
            raise ValidationError(f"Must be one of: {valid}")
    
    def to_db(self, value):
        if value is None:
            return None
        return value.value
    
    def from_db(self, value):
        if value is None:
            return None
        return self.enum_class(value)
    
    def get_db_type(self):
        return "VARCHAR(50)"

# Usage
class Status(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"

class Task(Model):
    title = fields.String(max_length=200)
    status = EnumField(Status, default=Status.PENDING)
```

### Slug Field

```python
from slugify import slugify
from aksara.fields import Field
from aksara.exceptions import ValidationError

class SlugField(Field):
    """Auto-generating slug field."""
    
    def __init__(self, source_field=None, **kwargs):
        self.source_field = source_field
        kwargs.setdefault("max_length", 200)
        super().__init__(**kwargs)
    
    def validate(self, value):
        if value is None and self.null:
            return None
        
        if value:
            return slugify(str(value))
        return value
    
    def contribute_to_class(self, cls, name):
        super().contribute_to_class(cls, name)
        
        # Auto-generate from source field
        if self.source_field:
            from aksara.signals import pre_save
            
            @pre_save(cls)
            async def auto_slug(sender, instance, **kwargs):
                if not getattr(instance, name):
                    source_value = getattr(instance, self.source_field, "")
                    setattr(instance, name, slugify(source_value))
    
    def to_db(self, value):
        return value
    
    def from_db(self, value):
        return value
    
    def get_db_type(self):
        return f"VARCHAR({self.max_length})"

# Usage
class Post(Model):
    title = fields.String(max_length=200)
    slug = SlugField(source_field="title", unique=True)
```

### Array Field (PostgreSQL)

```python
import json
from aksara.fields import Field
from aksara.exceptions import ValidationError

class ArrayField(Field):
    """PostgreSQL array field."""
    
    def __init__(self, base_type="text", **kwargs):
        self.base_type = base_type
        super().__init__(**kwargs)
    
    def validate(self, value):
        if value is None:
            if self.null:
                return None
            raise ValidationError("Value is required")
        
        if not isinstance(value, (list, tuple)):
            raise ValidationError("Must be a list")
        
        return list(value)
    
    def to_db(self, value):
        if value is None:
            return None
        # PostgreSQL array format: {item1,item2}
        return "{" + ",".join(str(v) for v in value) + "}"
    
    def from_db(self, value):
        if value is None:
            return None
        if isinstance(value, list):
            return value
        # Parse PostgreSQL array format
        return value.strip("{}").split(",") if value else []
    
    def get_db_type(self):
        return f"{self.base_type.upper()}[]"

# Usage
class Article(Model):
    title = fields.String(max_length=200)
    tags = ArrayField(base_type="text", default=list)
```

---

## Field with Serialization

### Custom Serialization

```python
from aksara.fields import Field
from aksara.api.serializers import SerializerField

class ColorField(Field):
    """RGB color field."""
    
    def validate(self, value):
        if value is None and self.null:
            return None
        
        if isinstance(value, dict):
            # {r: 255, g: 128, b: 0}
            return value
        
        if isinstance(value, str) and value.startswith("#"):
            # #ff8000
            return self.hex_to_rgb(value)
        
        raise ValidationError("Invalid color format")
    
    def hex_to_rgb(self, hex_color):
        hex_color = hex_color.lstrip("#")
        return {
            "r": int(hex_color[0:2], 16),
            "g": int(hex_color[2:4], 16),
            "b": int(hex_color[4:6], 16),
        }
    
    def to_db(self, value):
        if value is None:
            return None
        return f"{value['r']},{value['g']},{value['b']}"
    
    def from_db(self, value):
        if value is None:
            return None
        r, g, b = map(int, value.split(","))
        return {"r": r, "g": g, "b": b}
    
    def get_db_type(self):
        return "VARCHAR(20)"
    
    def get_serializer_field(self):
        """Return the API serializer field."""
        return ColorSerializerField()

class ColorSerializerField(SerializerField):
    """Serializer field for colors."""
    
    def to_representation(self, value):
        """Convert to JSON output."""
        if value is None:
            return None
        return {
            "rgb": value,
            "hex": "#{r:02x}{g:02x}{b:02x}".format(**value),
        }
    
    def to_internal_value(self, data):
        """Convert from JSON input."""
        if isinstance(data, str):
            return {"hex": data}
        return data
```

---

## Migration Support

### Deconstruction

For migrations to work, fields must be deconstructable:

```python
class CustomField(Field):
    def __init__(self, custom_arg, **kwargs):
        self.custom_arg = custom_arg
        super().__init__(**kwargs)
    
    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["custom_arg"] = self.custom_arg
        return name, path, args, kwargs
```

---

## Type Hints

### Add Type Hints

Create a `.pyi` stub file:

```python
# fields.pyi
from typing import TypeVar, Generic, Optional

T = TypeVar("T")

class PercentageField(Field[float]):
    def __init__(
        self,
        min_value: float = 0,
        max_value: float = 100,
        null: bool = False,
        default: Optional[float] = None,
    ) -> None: ...
```

---

## Testing Custom Fields

```python
import pytest
from aksara.testing import AksaraTestCase

class TestPercentageField(AksaraTestCase):
    async def test_valid_value(self):
        field = PercentageField()
        assert field.validate(50) == 50.0
    
    async def test_boundary_values(self):
        field = PercentageField()
        assert field.validate(0) == 0.0
        assert field.validate(100) == 100.0
    
    async def test_invalid_range(self):
        field = PercentageField()
        with pytest.raises(ValidationError):
            field.validate(150)
    
    async def test_custom_range(self):
        field = PercentageField(min_value=10, max_value=50)
        assert field.validate(30) == 30.0
        with pytest.raises(ValidationError):
            field.validate(5)
```

---

## Related Documentation

- [Fields](../orm/fields.md)
- [Validation](validation.md)
- [Migrations](../orm/migrations.md)
