# Background Tasks

Aksara includes a built-in PostgreSQL-backed task queue for work that should
run outside the request path without adding Redis, Celery, or another service.

---

## Overview

The built-in worker stores queued jobs in `aksara_tasks` and processes them from
the application lifespan. All state lives in your existing PostgreSQL database —
no extra infrastructure required.

Use it for:

- sending email after a write succeeds
- generating exports or reports
- calling third-party APIs without blocking the response
- lightweight asynchronous housekeeping
- recurring background jobs (heartbeats, digest emails, cleanup sweeps)

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
an async `.enqueue()` helper.

### Named Tasks

Override the auto-derived name (defaults to `module.qualname`):

```python
@task(name="notifications.welcome_email")
async def send_welcome_email(user_id: str) -> dict:
    ...
```

### Named Queues

Assign a task to a specific queue to isolate different workloads:

```python
@task(queue="emails")
async def send_welcome_email(user_id: str) -> dict:
    ...

@task(queue="reports")
async def generate_monthly_report(period: str) -> dict:
    ...
```

Workers can be bound to specific queues — see [Worker Configuration](#worker-configuration).

### Recurring Tasks

Register a task with `every=` to have the worker schedule it automatically:

```python
from datetime import timedelta
from aksara import task


@task(every=timedelta(minutes=5))
async def send_digest_emails() -> dict:
    # runs every 5 minutes
    ...

@task(every=300)  # int/float seconds also accepted
async def heartbeat_ping() -> dict:
    ...
```

Recurring tasks are tracked in `aksara_cron_state`. The worker uses an atomic
database claim so that multiple running instances never double-enqueue the same
tick — only one instance wins per interval.

---

## Enqueueing Work

Queue a task with `.enqueue()` or the top-level `enqueue_task()` helper.

```python
user = await User.objects.create(email="ada@example.com")

queued = await send_welcome_email.enqueue(str(user.id))
assert queued.status == "pending"
```

### Delayed Execution

```python
# Run in 30 seconds
await send_welcome_email.enqueue(str(user.id), delay_seconds=30)
```

### Per-Enqueue Overrides

```python
await send_welcome_email.enqueue(
    str(user.id),
    delay_seconds=30,
    max_attempts=5,
    queue="priority",   # override the queue at enqueue time
)
```

---

## Worker Configuration

### Automatic (Default)

When `tasks_enabled=True`, `Aksara(...)` starts a `TaskWorker` during app
startup and stops it gracefully during shutdown.

```python
from aksara.conf import Settings, configure

configure(Settings(
    database_url="postgresql://postgres:postgres@localhost/myapp",
    tasks_enabled=True,
    task_poll_interval_seconds=1.0,
    task_max_attempts=3,
))
```

### Manual Worker

Run the worker directly for full control:

```python
from aksara.tasks import TaskWorker
from aksara.db import Database

db = Database("postgresql://localhost/myapp")
await db.connect()

worker = TaskWorker(
    db,
    poll_interval=0.25,
    retry_delay_seconds=5.0,
    concurrency=4,
)
await worker.start()
```

### Queue Binding

Bind a worker to one or more named queues. A worker with `queues=None`
(the default) processes all queues.

```python
# Dedicated email worker
email_worker = TaskWorker(db, queues=["emails"])

# Handle multiple queues on one worker
mixed_worker = TaskWorker(db, queues=["emails", "reports"])

# Process all queues (default)
general_worker = TaskWorker(db, queues=None)
```

---

## Concurrency

By default a worker processes one task at a time. Increase `concurrency` to
process multiple tasks simultaneously within a single worker process:

```python
worker = TaskWorker(db, concurrency=4)
```

Or set globally:

```bash
AKSARA_TASK_CONCURRENCY=4
```

Each slot runs as an independent asyncio task. The worker drains all in-flight
tasks before shutting down.

---

## Retry Semantics

### Retry Budget

Each task row tracks `attempts` and `max_attempts`. On failure the task is
rescheduled until `attempts == max_attempts`, after which it is marked `failed`.

```python
@task(max_attempts=5)
async def send_webhook(url: str) -> dict:
    ...
```

### Exponential Backoff

Retry delays grow exponentially by default:

```
delay = retry_delay_seconds × retry_backoff_base ^ (attempt − 1)
```

| Attempt | Default delay (`base=2.0`, `delay=5s`) |
|---------|----------------------------------------|
| 1       | 5 s                                    |
| 2       | 10 s                                   |
| 3       | 20 s                                   |
| 4       | 40 s                                   |

The delay is capped at `retry_max_delay_seconds` (default: 3600 s / 1 hour).

```python
worker = TaskWorker(
    db,
    retry_delay_seconds=5.0,
    retry_backoff_base=2.0,
    retry_max_delay_seconds=3600.0,
)
```

Set `retry_backoff_base=1.0` to restore a flat constant delay:

```python
worker = TaskWorker(db, retry_delay_seconds=5.0, retry_backoff_base=1.0)
```

---

## Stale Lock Recovery

If a worker process crashes after claiming a task but before completing it, the
row stays `status='running'` indefinitely. Aksara detects this automatically:

Every `lock_recovery_interval_seconds` (default: 60 s) the worker queries for
tasks whose `locked_at` is older than `stale_lock_timeout_seconds` (default:
300 s / 5 min) and resets them to `pending` so another worker can retry them.

```python
worker = TaskWorker(
    db,
    stale_lock_timeout_seconds=300.0,    # age before "stuck"
    lock_recovery_interval_seconds=60.0, # how often to sweep
)
```

You can also trigger recovery manually:

```python
recovered = await worker.recover_stale_locks()
print(f"Recovered {recovered} stuck task(s)")
```

---

## Completed Task Cleanup

Task rows accumulate forever unless you configure a TTL. Set
`result_ttl_seconds` to have the worker automatically purge old `completed`
rows:

```python
worker = TaskWorker(
    db,
    result_ttl_seconds=7 * 86400,       # keep completed rows for 7 days
    cleanup_interval_seconds=3600,       # run cleanup hourly
)
```

```bash
AKSARA_TASK_RESULT_TTL_SECONDS=604800   # 7 days
AKSARA_TASK_CLEANUP_INTERVAL_SECONDS=3600
```

Purge manually or with a custom status filter:

```python
# Purge completed rows older than 7 days
count = await worker.purge_old_tasks(older_than_seconds=7 * 86400)

# Also purge failed rows older than 30 days
count = await worker.purge_old_tasks(
    statuses=("completed", "failed"),
    older_than_seconds=30 * 86400,
)
```

---

## Inspecting Task State

```python
from aksara import get_task_record

record = await get_task_record(queued.id)
assert record is not None
assert record.status in {"pending", "running", "completed", "failed"}

# Available fields
record.id
record.task_name
record.queue
record.status
record.attempts
record.max_attempts
record.last_error       # last failure message
record.result           # return value (when completed)
record.available_at     # when the task becomes eligible
record.locked_at        # when the worker claimed it
record.completed_at
record.created_at
record.updated_at
```

---

## CLI — Task Queue Management

Aksara ships an `aksara tasks` command group for operational visibility and
dead-letter management.

### Stats

```bash
aksara tasks stats
```

Shows row counts grouped by status and queue:

```
  Queue: default
    pending          3
    running          1
    completed      412
    failed           2

  Total
    pending          3
    running          1
    completed      412
    failed           2
```

### List Tasks

```bash
aksara tasks list                           # failed tasks (default)
aksara tasks list --status pending
aksara tasks list --status failed --queue emails --limit 50
aksara tasks list --task-name send_welcome  # substring match on task_name
```

### Re-enqueue Failed Tasks

Re-enqueue resets `attempts`, `locked_at`, `last_error`, and `available_at`
so the task is picked up as fresh:

```bash
aksara tasks reenqueue <uuid>           # one task by ID
aksara tasks reenqueue --all            # all failed tasks
aksara tasks reenqueue --all --queue emails
aksara tasks reenqueue --all --yes      # skip confirmation
```

### Purge Old Records

```bash
aksara tasks purge                                  # completed, >7 days
aksara tasks purge --status failed --older-than-days 30
aksara tasks purge --status completed --status failed -d 1 --yes
```

---

## Payload Serialization

Task arguments and return values are stored as JSONB. The following Python types
are normalized automatically:

| Type | Encoding |
|------|----------|
| `dict`, `list`, `str`, `int`, `float`, `bool` | Native JSON |
| `UUID` | `str(uuid)` |
| `datetime` | ISO 8601 string |
| `set` | Sorted list |
| Pydantic model | `.model_dump(mode="json")` |
| dataclass | `dataclasses.asdict()` |
| Object with `.to_dict()` | `.to_dict()` |

Tasks should be idempotent when possible, and payloads should be kept small.

---

## Operational Notes

- `aksara migrate` provisions `aksara_tasks` and `aksara_cron_state` through
  an internal migration. Run migrations with a schema-owning release role
  before starting application instances.
- Runtime checks skip DDL when the internal schema is current, so a production
  worker can run with DML-only table grants. Older schemas still use the
  idempotent compatibility path; use a role allowed to alter those tables for
  that one-time migration.
- Workers claim jobs with `FOR UPDATE SKIP LOCKED`, so multiple app instances
  share the same queue safely.
- The built-in queue is intentionally lightweight. For very high throughput
  (thousands of tasks/second) or cross-language consumers, consider a dedicated
  external queue like RabbitMQ or Kafka.

---

## Settings Quick Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `tasks_enabled` | `True` | Start worker automatically |
| `task_poll_interval_seconds` | `1.0` | Idle polling frequency |
| `task_max_attempts` | `3` | Global retry budget |
| `task_retry_delay_seconds` | `5.0` | Base retry delay |
| `task_retry_backoff_base` | `2.0` | Exponential backoff multiplier |
| `task_retry_max_delay_seconds` | `3600.0` | Retry delay ceiling |
| `task_concurrency` | `1` | Parallel slots per worker |
| `task_stale_lock_timeout_seconds` | `300.0` | Age before a running task is considered crashed |
| `task_lock_recovery_interval_seconds` | `60.0` | How often stale-lock sweep runs |
| `task_result_ttl_seconds` | `None` | Age before completed rows are purged (disabled by default) |
| `task_cleanup_interval_seconds` | `3600.0` | How often TTL cleanup runs |
| `task_cron_check_interval_seconds` | `30.0` | How often recurring tasks are checked |

See [Settings Reference](../reference/settings-reference.md#background-task-settings)
for environment variable names.
