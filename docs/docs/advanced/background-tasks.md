# Background Tasks

Aksara includes a built-in PostgreSQL-backed task queue for work that should
run outside the request path without adding Redis, Celery, or another service.

---

## Overview

The built-in worker stores queued jobs in `aksara_tasks` and processes them from
the application lifespan.

Use it for:

- sending email after a write succeeds
- generating exports or reports
- calling third-party APIs without blocking the response
- lightweight asynchronous housekeeping

---

## Defining a Task

Register a task with `@task`.

```python
from aksara import task


@task
async def send_welcome_email(user_id: str) -> dict[str, str]:
    return {"status": "sent", "user_id": user_id}
```

The decorator keeps the function callable in normal Python code and also adds
an async enqueue helper.

---

## Enqueueing Work

Queue a task with `.enqueue()` or `enqueue_task()`.

```python
user = await User.objects.create(email="ada@example.com")

queued = await send_welcome_email.enqueue(str(user.id))
assert queued.status == "pending"
```

You can delay execution or override retry limits per enqueue call:

```python
await send_welcome_email.enqueue(
    str(user.id),
    delay_seconds=30,
    max_attempts=5,
)
```

---

## Worker Lifecycle

When `tasks_enabled=True`, `Aksara(...)` starts a `TaskWorker` during app
startup and stops it during shutdown.

```python
from aksara import Aksara
from aksara.conf import Settings, configure

configure(Settings(
    database_url="postgresql://postgres:postgres@localhost/myapp",
    tasks_enabled=True,
    task_poll_interval_seconds=0.5,
    task_retry_delay_seconds=2.0,
    task_max_attempts=3,
))

app = Aksara(database_url="postgresql://postgres:postgres@localhost/myapp")
```

If you need full control, you can run the worker manually:

```python
from aksara import TaskWorker
from aksara.db import Database

db = Database.from_settings()
await db.connect()

worker = TaskWorker(db, poll_interval=0.25, retry_delay_seconds=1.0)
await worker.start()
```

---

## Retry Semantics

Each task row tracks:

- `status`: `pending`, `running`, `completed`, or `failed`
- `attempts`
- `max_attempts`
- `last_error`
- `result`

On failure, Aksara requeues the task until `attempts == max_attempts`. After the
last failed attempt, the row is marked `failed` and left in the table for
inspection.

Tasks should therefore be:

- idempotent when possible
- small in payload size
- JSON-serializable in both arguments and results

Common value types like dataclasses, Pydantic models, UUIDs, datetimes, and
sets are normalized automatically.

---

## Inspecting Task State

```python
from aksara import get_task_record

record = await get_task_record(queued.id)
assert record is not None
assert record.status in {"pending", "completed", "failed"}
```

---

## Operational Notes

- `aksara_tasks` is created lazily on first enqueue or worker start.
- The worker claims jobs with `FOR UPDATE SKIP LOCKED`, so multiple workers can
  safely compete for pending rows.
- The built-in queue is intentionally lightweight. For high-throughput,
  scheduled, or distributed workloads, move to a dedicated external queue.