# Signals

Hook into model lifecycle events.

---

## Overview

Signals allow you to run code when specific events occur:

- **`pre_save`** — Before a model is saved
- **`post_save`** — After a model is saved
- **`pre_delete`** — Before a model is deleted
- **`post_delete`** — After a model is deleted
- **`pre_init`** — Before a model instance is created
- **`post_init`** — After a model instance is created

---

## Basic Usage

### Signal Decorators

```python
from aksara import Model, fields
from aksara.signals import pre_save, post_save, pre_delete, post_delete

class Post(Model):
    title = fields.String(max_length=200)
    slug = fields.String(max_length=200)
    content = fields.Text()
    view_count = fields.Integer(default=0)

# Pre-save: generate slug
@pre_save(Post)
async def generate_slug(sender, instance, **kwargs):
    if not instance.slug:
        from slugify import slugify
        instance.slug = slugify(instance.title)

# Post-save: send notification
@post_save(Post)
async def notify_followers(sender, instance, created, **kwargs):
    if created:
        await send_new_post_notification(instance)

# Pre-delete: backup data
@pre_delete(Post)
async def backup_before_delete(sender, instance, **kwargs):
    await BackupService.archive(instance)

# Post-delete: cleanup
@post_delete(Post)
async def cleanup_related(sender, instance, **kwargs):
    await SearchIndex.remove(instance)
```

---

## Signal Arguments

### Pre-Save Arguments

| Argument | Description |
|----------|-------------|
| `sender` | The model class |
| `instance` | The model instance |
| `update_fields` | Fields being updated (None for full save) |

```python
@pre_save(Post)
async def handle_pre_save(sender, instance, update_fields=None, **kwargs):
    if update_fields is None or "title" in update_fields:
        # Title is being updated
        instance.updated_at = datetime.now()
```

### Post-Save Arguments

| Argument | Description |
|----------|-------------|
| `sender` | The model class |
| `instance` | The model instance |
| `created` | True if this is a new record |
| `update_fields` | Fields that were updated |

```python
@post_save(Post)
async def handle_post_save(sender, instance, created, **kwargs):
    if created:
        print(f"New post created: {instance.title}")
    else:
        print(f"Post updated: {instance.title}")
```

### Delete Arguments

| Argument | Description |
|----------|-------------|
| `sender` | The model class |
| `instance` | The model instance |

```python
@pre_delete(Post)
async def handle_delete(sender, instance, **kwargs):
    print(f"Deleting: {instance.id}")
```

---

## Connecting Signals Manually

### Using `connect()`

```python
from aksara.signals import pre_save

async def my_handler(sender, instance, **kwargs):
    print(f"Saving {instance}")

# Connect
pre_save.connect(my_handler, sender=Post)

# Disconnect
pre_save.disconnect(my_handler, sender=Post)
```

### Multiple Models

```python
from aksara.signals import post_save

async def log_save(sender, instance, **kwargs):
    print(f"Saved {sender.__name__}: {instance.id}")

# Connect to multiple models
for model in [User, Post, Comment]:
    post_save.connect(log_save, sender=model)
```

### All Models

```python
# Connect to all models (sender=None)
@post_save()  # No sender specified
async def log_all_saves(sender, instance, **kwargs):
    print(f"Saved {sender.__name__}")
```

---

## Custom Signals

### Creating Custom Signals

```python
from aksara.signals import Signal

# Define signal
user_activated = Signal()
order_completed = Signal()

# Send signal
await user_activated.send(sender=User, instance=user)

# Receive signal
@user_activated.connect
async def handle_activation(sender, instance, **kwargs):
    await send_welcome_email(instance)
```

### Signal with Custom Arguments

```python
payment_processed = Signal(providing_args=["amount", "currency"])

@payment_processed.connect
async def handle_payment(sender, instance, amount, currency, **kwargs):
    print(f"Payment of {amount} {currency} processed")

# Send with args
await payment_processed.send(
    sender=Order,
    instance=order,
    amount=99.99,
    currency="USD"
)
```

---

## Practical Examples

### Audit Logging

```python
from aksara.signals import post_save, post_delete
from aksara import Model, fields
import json

class AuditLog(Model):
    model_name = fields.String(max_length=100)
    record_id = fields.String(max_length=36)
    action = fields.String(max_length=20)
    data = fields.JSON()

async def audit_handler(sender, instance, action, **kwargs):
    await AuditLog.objects.create(
        model_name=sender.__name__,
        record_id=str(instance.id),
        action=action,
        data=instance.to_dict()
    )

# Register for models that need auditing
AUDITED_MODELS = [User, Post, Order]

for model in AUDITED_MODELS:
    post_save.connect(
        lambda s, i, created, **k: audit_handler(s, i, "create" if created else "update", **k),
        sender=model
    )
    post_delete.connect(
        lambda s, i, **k: audit_handler(s, i, "delete", **k),
        sender=model
    )
```

### Search Index Updates

```python
from aksara.signals import post_save, post_delete

class SearchService:
    @staticmethod
    async def index(instance):
        # Add to search index
        pass
    
    @staticmethod
    async def remove(instance):
        # Remove from search index
        pass

@post_save(Post)
async def index_post(sender, instance, **kwargs):
    await SearchService.index(instance)

@post_delete(Post)
async def unindex_post(sender, instance, **kwargs):
    await SearchService.remove(instance)
```

### Automatic Timestamps

```python
from aksara.signals import pre_save
from datetime import datetime

@pre_save()  # All models
async def update_timestamps(sender, instance, **kwargs):
    now = datetime.utcnow()
    
    # Set created_at for new records
    if not instance.id and hasattr(instance, 'created_at'):
        instance.created_at = now
    
    # Always update updated_at
    if hasattr(instance, 'updated_at'):
        instance.updated_at = now
```

### Cache Invalidation

```python
from aksara.signals import post_save, post_delete
from aksara.cache import cache

@post_save(Post)
async def invalidate_post_cache(sender, instance, **kwargs):
    # Invalidate specific cache
    await cache.delete(f"post:{instance.id}")
    
    # Invalidate list caches
    await cache.delete("posts:all")
    await cache.delete(f"posts:author:{instance.author_id}")

@post_delete(Post)
async def invalidate_on_delete(sender, instance, **kwargs):
    await cache.delete(f"post:{instance.id}")
    await cache.delete("posts:all")
```

### Notification System

```python
from aksara.signals import post_save

@post_save(Comment)
async def notify_post_author(sender, instance, created, **kwargs):
    if not created:
        return
    
    post = await instance.post
    author = await post.author
    
    # Don't notify if commenting on own post
    if instance.author_id == author.id:
        return
    
    await NotificationService.send(
        user=author,
        type="new_comment",
        message=f"New comment on '{post.title}'",
        data={"post_id": str(post.id), "comment_id": str(instance.id)}
    )
```

---

## Signal Best Practices

### Do

- Keep signal handlers focused and small
- Use async handlers for I/O operations
- Handle exceptions gracefully
- Document signal behavior

### Don't

- Don't put business logic in signals
- Don't create circular dependencies
- Don't modify the instance in post_save (can cause recursion)
- Don't rely on signal execution order

### Error Handling

```python
import logging

logger = logging.getLogger(__name__)

@post_save(Post)
async def safe_handler(sender, instance, **kwargs):
    try:
        await external_service.notify(instance)
    except Exception as e:
        # Log but don't raise (don't break the save)
        logger.error(f"Signal handler failed: {e}")
```

### Disable Signals Temporarily

```python
from aksara.signals import SignalContext

# Disable all signals for a model
async with SignalContext.disable_for(Post):
    await post.save()  # No signals fired

# Or use update_fields to bypass
await Post.objects.filter(id=post_id).update(view_count=F("view_count") + 1)
```

---

## Testing Signals

### Mock Signals

```python
from unittest.mock import patch, AsyncMock

async def test_post_save_signal():
    with patch("myapp.signals.notify_followers", new_callable=AsyncMock) as mock:
        post = await Post.objects.create(title="Test")
        mock.assert_called_once()
```

### Test Signal Handlers Directly

```python
async def test_slug_generation():
    post = Post(title="Hello World")
    await generate_slug(Post, post)
    assert post.slug == "hello-world"
```

---

## Built-in Signals

| Signal | Fired When |
|--------|------------|
| `pre_init` | Before `__init__` returns |
| `post_init` | After `__init__` completes |
| `pre_save` | Before `save()` executes |
| `post_save` | After `save()` completes |
| `pre_delete` | Before `delete()` executes |
| `post_delete` | After `delete()` completes |
| `pre_bulk_create` | Before bulk create |
| `post_bulk_create` | After bulk create |
| `pre_bulk_update` | Before bulk update |
| `post_bulk_update` | After bulk update |
| `m2m_changed` | When M2M relation changes |

---

## Related Documentation

- [Models](../orm/models.md)
- [Custom Fields](custom-fields.md)
- [Testing](testing.md)
