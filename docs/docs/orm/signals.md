# Signals

Aksara provides an integrated event system through Signals, allowing decoupled applications to get notified when certain actions occur elsewhere in the framework.

Aksara provides four built-in model lifecycle signals:

*   `pre_save`: Triggered just before a model's `.save()` executes.
*   `post_save`: Triggered immediately after a model's `.save()` finishes.
*   `pre_delete`: Triggered just before a model's `.delete()` executes.
*   `post_delete`: Triggered immediately after a model's `.delete()` finishes.

---

## Usage

Import the signals from `aksara.signals` and register listeners using the `@signal.connect` pattern, or manually via `.connect()`.

```python
from aksara import Model, fields
from aksara.signals import post_save

class User(Model):
    email = fields.String(unique=True)
    name = fields.String()

# Define a signal handler
async def on_user_created(sender, instance, created=False, **kwargs):
    """
    sender: The Model class (User)
    instance: The model instance that was just saved
    created: True if this was an insert, False if it was an update (only available on pre_save/post_save)
    """
    if created:
        print(f"Sending welcome email to {instance.email}")
        # await send_welcome_email(instance.email)

# Connect the handler to the specific model
post_save.connect(on_user_created, sender=User)
```

Now, whenever a new `User` is saved, the signal will automatically fire:

```python
# This automatically triggers on_user_created
user = await User.objects.create(email="john@example.com", name="John")
```
