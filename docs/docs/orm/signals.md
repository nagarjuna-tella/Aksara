# Model lifecycle signals

Signals are in-process callbacks around individual model lifecycle methods.
They are useful for local hooks, but they are not durable events, after-commit
notifications, or an authorization boundary.

## Built-in events

Import these four objects from `aksara.signals`:

| Signal | When sent | Keyword payload beyond `sender` |
| --- | --- | --- |
| `pre_save` | Before field preparation, validation, and insert/update | `instance`, `is_new` |
| `post_save` | After the insert/update, before `save()` returns | `instance` |
| `pre_delete` | Before the instance deletion work | `instance` |
| `post_delete` | After the instance deletion work | `instance` |

`sender` is the model class. `post_save` does **not** pass `created` or
`update_fields`. A receiver requiring those arguments will fail. Use the
`is_new` value supplied to `pre_save` when the distinction is needed at that
point. Do not infer an insert from a missing ID: new instances can already have
an ID.

There are no built-in `pre_init`, `post_init`, bulk lifecycle, or `m2m_changed`
signals in this module. Do not assume bulk/queryset writes, raw SQL, or relation
changes emit the per-instance callbacks; use the specific operation's contract.

## Register a receiver

Receivers must be async callables that accept the supplied keyword arguments.
Use `signal.connect(receiver, sender=ModelClass)` and retain the receiver for
later disconnection. A signal object is not a decorator. `connect()` returns
`None`, so using `@post_save.connect` would replace the function binding with
`None`.

Register handlers once when the application imports its configuration. For the
tutorial Ticket model:

```python title="app/signals.py"
from aksara.signals import pre_save
from .models import Ticket


async def normalize_subject(sender, instance, is_new, **kwargs):
    instance.subject = instance.subject.strip()


def connect_signals():
    pre_save.connect(normalize_subject, sender=Ticket)


def disconnect_signals():
    return pre_save.disconnect(normalize_subject, sender=Ticket)
```

Call `connect_signals()` during application construction. This hook normalizes
individual saves; it does not enforce a rule across bulk updates or raw SQL.
Use explicit validation and database constraints for invariants that must hold
across all write paths.

## Transaction and failure behavior

Model methods call `send()`, which awaits receivers sequentially. A receiver
exception propagates and stops later receivers. A `post_save` exception does
not automatically undo a statement that already committed: wrap related writes
in an explicit [transaction](expressions-and-transactions.md) when rollback is
required.

Inside an outer transaction, `post_save` runs **before commit**. A later failure
can roll the database write back after the handler has run. Sending email,
writing files, or calling a remote service there cannot be rolled back with the
database. Suppressing an exception does not make an external effect reliable.

For recoverable application work, use the explicit
[Durable Operations](../advanced/durable-operations.md) boundary and its
external-effect contract. Do not treat a lifecycle signal as a durable outbox,
a complete audit trail, or an exactly-once delivery mechanism.

## Custom signals

`Signal(name=None)` creates a process-local dispatcher. `send(sender, **named)`
returns `(receiver, result)` pairs. `send_robust()` catches ordinary `Exception`
instances, returns them alongside successful results, and continues dispatch;
it does not swallow cancellation or other `BaseException` subclasses.

This standalone example needs Aksara installed, but no database:

```python title="check_signals.py"
import asyncio

from aksara.signals import Signal


async def main():
    event = Signal("ticket_observed")
    sender = object()
    seen = []

    async def record(sender, *, subject):
        seen.append(subject)
        return subject.upper()

    event.connect(record, sender=sender)
    try:
        assert await event.send(object(), subject="ignored") == []
        assert await event.send(sender, subject="ticket") == [(record, "TICKET")]
        assert seen == ["ticket"]
    finally:
        assert event.disconnect(record, sender=sender)
    assert await event.send(sender, subject="disconnected") == []


if __name__ == "__main__":
    asyncio.run(main())
```

Run `python check_signals.py`; successful assertions produce no output.
`sender=None` at connection time subscribes to all senders. There is no
`providing_args` constructor option. Bound-method receivers use weak references;
keep their owning object alive while the subscription is needed.
