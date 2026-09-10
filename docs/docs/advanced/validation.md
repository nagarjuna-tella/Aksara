# Validation

Advanced validation patterns for models and APIs.

---

## Overview

Aksara provides multiple layers of validation:

1. **Field-level** — Single field validation
2. **Model-level** — Cross-field validation
3. **Serializer-level** — API input validation
4. **Custom validators** — Reusable validation logic

---

## Field-Level Validation

### Built-in Validators

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara import Model, fields
from aksara.validation import (
    MinLength, MaxLength, MinValue, MaxValue,
    Regex, Email, URL, In, NotIn
)

class User(Model):
    username = fields.String(
        max_length=50,
        validators=[
            MinLength(3),
            Regex(r'^[a-zA-Z0-9_]+$', message="Alphanumeric only"),
        ]
    )
    email = fields.Email(validators=[Email()])
    age = fields.Integer(
        validators=[MinValue(13), MaxValue(120)]
    )
    role = fields.String(
        max_length=20,
        validators=[In(["user", "admin", "moderator"])]
    )
```

### Custom Validators

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.validation import Validator, ValidationError

class NoSpaces(Validator):
    """Ensure no spaces in value."""
    
    message = "Value cannot contain spaces"
    
    def __call__(self, value):
        if " " in str(value):
            raise ValidationError(self.message)
        return value

class Unique(Validator):
    """Ensure value is unique in database."""
    
    def __init__(self, model, field_name):
        self.model = model
        self.field_name = field_name
    
    async def __call__(self, value, instance=None):
        query = self.model.objects.filter(**{self.field_name: value})
        
        # Exclude current instance on update
        if instance and instance.id:
            query = query.exclude(id=instance.id)
        
        if await query.exists():
            raise ValidationError(f"{self.field_name} already exists")
        
        return value

# Usage
class User(Model):
    username = fields.String(
        max_length=50,
        validators=[NoSpaces(), Unique(User, "username")]
    )
```

---

## Model-Level Validation

### Clean Method

```python
class Order(Model):
    start_date = fields.Date()
    end_date = fields.Date()
    quantity = fields.Integer()
    unit_price = fields.Decimal(max_digits=10, decimal_places=2)
    
    def clean(self):
        """Validate the entire model."""
        errors = {}
        
        if self.end_date <= self.start_date:
            errors["end_date"] = "End date must be after start date"
        
        if self.quantity <= 0:
            errors["quantity"] = "Quantity must be positive"
        
        if errors:
            raise ValidationError(errors)
    
    async def save(self, **kwargs):
        self.clean()
        return await super().save(**kwargs)
```

### Field Dependencies

```python
class Subscription(Model):
    plan = fields.String(max_length=20, choices=["free", "pro", "enterprise"])
    max_users = fields.Integer()
    
    PLAN_LIMITS = {
        "free": 5,
        "pro": 50,
        "enterprise": 1000,
    }
    
    def clean(self):
        max_allowed = self.PLAN_LIMITS.get(self.plan, 0)
        if self.max_users > max_allowed:
            raise ValidationError({
                "max_users": f"Plan '{self.plan}' allows max {max_allowed} users"
            })
```

---

## Serializer Validation

### Field Validators

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.api import ModelSerializer
from aksara.validation import ValidationError

class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ["email", "username", "password"]
    
    def validate_username(self, value):
        """Validate username field."""
        if len(value) < 3:
            raise ValidationError("Username must be at least 3 characters")
        return value.lower()
    
    def validate_password(self, value):
        """Validate password strength."""
        if len(value) < 8:
            raise ValidationError("Password must be at least 8 characters")
        if not any(c.isupper() for c in value):
            raise ValidationError("Password must contain uppercase letter")
        if not any(c.isdigit() for c in value):
            raise ValidationError("Password must contain a digit")
        return value
```

### Cross-Field Validation

```python
class PasswordChangeSerializer(Serializer):
    old_password = String()
    new_password = String()
    confirm_password = String()
    
    def validate(self, data):
        """Validate all fields together."""
        if data["new_password"] != data["confirm_password"]:
            raise ValidationError({
                "confirm_password": "Passwords do not match"
            })
        
        if data["old_password"] == data["new_password"]:
            raise ValidationError({
                "new_password": "New password must be different"
            })
        
        return data
```

### Async Validation

```python
class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ["email", "username"]
    
    async def validate_email(self, value):
        """Check email is not already registered."""
        existing = await User.objects.filter(email=value).first()
        if existing:
            raise ValidationError("Email already registered")
        return value
    
    async def validate(self, data):
        """Cross-field async validation."""
        # Check for banned usernames
        if await BannedUsername.objects.filter(name=data["username"]).exists():
            raise ValidationError({"username": "This username is not allowed"})
        return data
```

---

## Reusable Validators

### Validator Classes

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.validation import Validator, ValidationError

class PasswordStrength(Validator):
    """Validate password strength."""
    
    def __init__(self, min_length=8, require_upper=True, require_digit=True, require_special=False):
        self.min_length = min_length
        self.require_upper = require_upper
        self.require_digit = require_digit
        self.require_special = require_special
    
    def __call__(self, value):
        errors = []
        
        if len(value) < self.min_length:
            errors.append(f"At least {self.min_length} characters")
        
        if self.require_upper and not any(c.isupper() for c in value):
            errors.append("One uppercase letter")
        
        if self.require_digit and not any(c.isdigit() for c in value):
            errors.append("One digit")
        
        if self.require_special:
            special = "!@#$%^&*()_+-=[]{}|;:,.<>?"
            if not any(c in special for c in value):
                errors.append("One special character")
        
        if errors:
            raise ValidationError("Password must contain: " + ", ".join(errors))
        
        return value

# Usage
class UserSerializer(ModelSerializer):
    password = String(validators=[PasswordStrength(min_length=10, require_special=True)])
```

### Validator Functions

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.validation import validator

@validator
def validate_slug(value):
    """Validate URL-safe slug."""
    import re
    if not re.match(r'^[a-z0-9-]+$', value):
        raise ValidationError("Slug must contain only lowercase letters, numbers, and hyphens")
    return value

@validator
def validate_future_date(value):
    """Ensure date is in the future."""
    from datetime import date
    if value <= date.today():
        raise ValidationError("Date must be in the future")
    return value

# Usage
class Event(Model):
    slug = fields.String(validators=[validate_slug])
    event_date = fields.Date(validators=[validate_future_date])
```

---

## Conditional Validation

### Based on Other Fields

```python
class PaymentSerializer(Serializer):
    payment_type = String(choices=["card", "bank", "crypto"])
    card_number = String(required=False)
    bank_account = String(required=False)
    wallet_address = String(required=False)
    
    def validate(self, data):
        payment_type = data.get("payment_type")
        
        if payment_type == "card":
            if not data.get("card_number"):
                raise ValidationError({"card_number": "Required for card payment"})
        
        elif payment_type == "bank":
            if not data.get("bank_account"):
                raise ValidationError({"bank_account": "Required for bank payment"})
        
        elif payment_type == "crypto":
            if not data.get("wallet_address"):
                raise ValidationError({"wallet_address": "Required for crypto payment"})
        
        return data
```

### Based on Instance State

```python
class OrderSerializer(ModelSerializer):
    class Meta:
        model = Order
        fields = ["status", "shipped_date"]
    
    def validate_status(self, value):
        if self.instance:  # Update
            current = self.instance.status
            
            valid_transitions = {
                "pending": ["confirmed", "cancelled"],
                "confirmed": ["shipped", "cancelled"],
                "shipped": ["delivered"],
                "delivered": [],
                "cancelled": [],
            }
            
            if value not in valid_transitions.get(current, []):
                raise ValidationError(f"Cannot transition from {current} to {value}")
        
        return value
```

---

## Validation Error Handling

### Error Format

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.validation import ValidationError

# Single field error
raise ValidationError("Invalid value")

# Field-specific errors
raise ValidationError({
    "email": "Invalid email format",
    "username": ["Too short", "Contains invalid characters"],
})

# Non-field errors
raise ValidationError({
    "__all__": "Invalid credentials"
})
```

### Custom Error Messages

```python
class User(Model):
    email = fields.Email(
        error_messages={
            "required": "Email address is required",
            "invalid": "Please enter a valid email address",
            "unique": "This email is already registered",
        }
    )
```

### Handling Validation Errors

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.api import ViewSet, action
from aksara.validation import ValidationError

class UserViewSet(ViewSet):
    @action(detail=False, methods=["post"])
    async def register(self, request):
        serializer = UserSerializer(data=request.data)
        
        try:
            await serializer.is_valid(raise_exception=True)
            user = await serializer.save()
            return {"user": UserSerializer(user).data}
        
        except ValidationError as e:
            return {"errors": e.detail}, 400
```

---

## Unique Constraints

### Single Field

```python
class User(Model):
    email = fields.Email(unique=True)

# Or with custom message
class User(Model):
    email = fields.Email(
        unique=True,
        error_messages={"unique": "Email already exists"}
    )
```

### Multiple Fields

**Conceptual application-level validation (not an installed model hook):**

```text title="Conceptual application validation"
class Membership(Model):
    user = fields.ForeignKey(User, on_delete=fields.CASCADE)
    organization = fields.ForeignKey(Organization, on_delete=fields.CASCADE)
    
    class Meta:
        unique_together = [("user", "organization")]
    
    def clean(self):
        # Check uniqueness manually for better error messages
        existing = await Membership.objects.filter(
            user=self.user,
            organization=self.organization
        ).exclude(id=self.id).exists()
        
        if existing:
            raise ValidationError("User is already a member of this organization")
```

---

## Best Practices

### Do

- Validate early (at serializer level for API input)
- Use clear error messages
- Keep validators focused and reusable
- Test edge cases

### Don't

- Don't duplicate validation logic
- Don't validate in views (use serializers)
- Don't silently fix invalid data without user knowledge

### Validation Order

```python
class MySerializer(ModelSerializer):
    # Validation order:
    # 1. Field-level: validate_<field_name>()
    # 2. Object-level: validate()
    # 3. Unique constraints
    # 4. Model clean()
    
    def validate_email(self, value):
        # 1. Called first
        return value
    
    def validate(self, data):
        # 2. Called after all field validators
        return data
```

---

## Related Documentation

- [Fields](../orm/fields.md)
- [Serializers](../api/serializers.md)
- [Custom Fields](custom-fields.md)
