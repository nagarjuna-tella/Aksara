# Export durable transition events

Use `DurableOutboxExporter` to send committed transition events to an
application-owned sink. The Operation record remains authoritative: an export
failure does not turn a successful Operation into a failed one.

## Prerequisites

Use a connected `DurableOperationService` with the same application namespace
as the Operations to export, and apply the durable migrations before running
an exporter. The [durable tutorial](../tutorials/ticket-desk-durable.md) shows
service registration and database lifecycle. Run export under a supervised
application process with the appropriate restricted database role.

Choose each tenant scope from trusted application configuration. The exporter
requires an explicit `tenant_id` for every call; `None` selects the non-tenant
scope, not all tenants. It does not discover tenants or provide an HTTP
authorization layer.

## Export one eligible event

This application helper takes the already-configured service and your sink.
It does not create tables or start a background loop:

```python title="app/export_transitions.py"
from aksara.durable import DurableOutboxExporter


def make_exporter(service, sink, *, worker_id):
    return DurableOutboxExporter(
        service,
        sink,
        worker_id=worker_id,
        claim_seconds=30.0,
        retry_seconds=5.0,
    )


async def export_one(exporter, *, tenant_id):
    return await exporter.export_once(tenant_id=tenant_id)
```

Supply a sink callable accepting one payload mapping. It can return normally
or return an awaitable. A successful return means the sink accepted the event
according to **your application's** delivery contract. For durable delivery,
do not acknowledge before the sink has durably accepted it.

`export_once()` returns `True` only when it marks the claimed event exported.
`False` can mean no eligible event, a handled sink exception, or loss of the
claim before acknowledgement. It is not a complete backlog or failure report.
A supervisor must decide polling, backoff, shutdown, and observability behavior.
Database errors and cancellation may propagate.

## Delivery and retry boundary

The exporter claims one eligible row in a short transaction, then calls the
sink outside that transaction. It marks the row exported in another transaction.
If the sink accepts an event but the process dies before acknowledgement,
the event can be delivered again after the claim expires.

This is at-least-once export. The sink must tolerate duplicate delivery and
must not assume globally ordered delivery across multiple exporters. A claim
lease is not a sink timeout: bound slow network calls in the application and
account for claim expiry while they are running. Use a distinct worker identity
for each concurrent exporter.

Ordinary sink exceptions schedule a retry after `retry_seconds`; their message
is retained as an export error. Keep exception messages free of credentials,
request bodies, and other sensitive data. Export failure does not undo the
Operation's database transaction or invalidate its recorded state.

## Payload and retention

Current payloads identify the Operation and state version, event, previous and
next state, reason code, and optional Attempt. They are transition summaries,
not a copy of the full command or a complete application audit record. The
payload does not include an application namespace or tenant identifier; add
trusted routing context in your sink adapter when combining exports from
multiple services or tenant scopes.

Do not expose raw outbox tables as a public API. Define the sink's versioning,
deduplication, access controls, retention, and recovery policy explicitly.
Keep durable export acceptance separate from log output or a successful HTTP
request to an intermediary. Coordinate source pruning with your retention and
backup requirements; the exporter does not operate an archival service.

## Verify the integration

Test a sink failure followed by a successful retry, and confirm the Operation's
state is unchanged by export failure. Test duplicate delivery after acceptance
but before acknowledgement, slow-sink lease expiry, process restart, and tenant
separation in the application's actual sink deployment. A local callback test
alone does not prove durable remote delivery.
