# Handle an external side effect

**Stable boundary:** Aksara can record an intent, preserve its identity across
Attempts and recover according to a provider's capabilities. It cannot roll
back a remote send with a PostgreSQL transaction or promise exactly-once delivery.

Use the [durable tutorial](../tutorials/ticket-desk-durable.md) for admission,
current-identity resolution and worker setup. Choose this path when the action
must call another system, such as a notification service. Keep database-only
mutations on the `postgres_atomic` path.

## Choose an honest recovery contract

| Effect class | Required application/provider behavior |
| --- | --- |
| `EXTERNAL_IDEMPOTENT` | Repeating a request with the supplied downstream key must not duplicate the effect. Verify the provider's retention window, account scope and payload rules. |
| `EXTERNAL_AT_LEAST_ONCE` | Supply reliable reconciliation before repeating an uncertain send. `NOT_FOUND` must establish that another send is safe. |
| `EXTERNAL_NONRETRYABLE` | No safe recovery mechanism exists. Preserve an uncertain outcome instead of blindly sending again. |

An adapter declares `supports_idempotency` and `supports_reconciliation`.
These are assertions about your integration, not capabilities Aksara adds to
a provider. Keep them consistent with the action's effect class.

## Route the send through the effect context

The following adapter expects an application-owned asynchronous client with
`send(request, idempotency_key=...)`, returning a mapping with `message_id`.
That client must implement a real provider's documented idempotency contract.
It is not a built-in Aksara client. Configure its credentials and network
timeouts outside the persisted command.

```python title="app/external_notifications.py"
from aksara.durable import (
    DurableAction,
    EffectClass,
    ExternalEffectResult,
)


class NotificationAdapter:
    supports_idempotency = True
    supports_reconciliation = False

    def __init__(self, client):
        self.client = client

    async def perform(self, request, *, idempotency_key):
        response = await self.client.send(request, idempotency_key=idempotency_key)
        message_id = response["message_id"]
        return ExternalEffectResult(
            {"message_id": message_id}, provider_reference=message_id
        )

    async def reconcile(self, *, idempotency_key, provider_reference):
        raise NotImplementedError("This adapter relies on provider idempotency")


def notification_action(adapter, *, effect_class: EffectClass):
    async def send_notification(context, command):
        return await context.perform("notification", 1, command, adapter)

    return DurableAction(
        name="tickets.notify",
        version="1",
        handler=send_notification,
        effect_class=effect_class,
        required_scopes=("tickets:notify",),
    )
```

Register `notification_action(NotificationAdapter(client),
effect_class=EffectClass.EXTERNAL_IDEMPOTENT)` in your action registry. Register
a trusted current-identity resolver as in the tutorial. Validate command fields
and recipients in the application's admission/authorization boundary before
persisting them; add the action's normalizer and object-specific `authorizer`
for your domain. A required scope alone does not validate a recipient.

For an explicitly claimed external Operation, run
`await ExternalOperationExecutor(service).execute(claim)`, importing the executor
from `aksara.durable`. A normal `DurableWorker` can dispatch registered external
actions too. Do not invoke the adapter directly from a `postgres_atomic` handler.

The effect name and positive ordinal identify one logical effect within the
Operation. Keep `"notification", 1` stable across retries, and use a distinct
ordinal/name for each additional effect. A changed payload for the same effect
identity is not a new send. Aksara persists and checks its request hash. Avoid
credentials in commands, results, references or exception messages.

## Understand a lost response

A provider may accept a message and then the connection may fail before your
application sees the response. With the idempotent adapter, a later Attempt
uses the same downstream key. The provider must return the same logical result
without delivering a second message. Retry eligibility is still bounded by the
Operation's attempt budget and deadline; inspect its returned state and error.
An executor call returning normally does not by itself mean `succeeded`.

The downstream key is distinct from the admission idempotency key: it binds
the Operation ID, effect name and ordinal. Re-admitting a new Operation can
produce a new key and a duplicate remote effect. Do not create replacement work
just because the first HTTP response was lost.

With reconciliation, return `ReconciliationResult` with `CONFIRMED` and an
`ExternalEffectResult` only when the provider establishes success. `NOT_FOUND`
allows another send; eventual-consistency lag alone is not safe evidence of
absence. `UNKNOWN` preserves uncertainty. A provider reference may be `None`
after a lost response, so reconciliation must support the supplied key too.

If neither mechanism can establish the result, a failed Operation can contain
`external_outcome_unknown`. This means **the remote action may have happened**.
Show that uncertainty to an operator and investigate the provider before taking
another business action. Do not describe it as a clean rollback or an unsent
message. There is no generic automatic compensation in this helper.

## Keep authorization and operational limits explicit

The executor resolves current identity and checks authority before execution
and effect boundaries. Approval does not preserve revoked access. Cancellation
and ownership checks cannot recall a message already accepted by the provider.
No atomic commit spans that provider and PostgreSQL.

The example's execution gate uses a simulated client that accepts a message,
loses its acknowledgement and deduplicates the retry. It proves Aksara supplies
the same key and records the result against an installed wheel and PostgreSQL.
It does not prove any real provider's retention, durability, timeout behavior or
delivery guarantees. Validate those properties separately for your integration.
See the [durable reference](../advanced/durable-operations.md#external-effects)
for the surrounding contract and the
[production runbook](../tutorials/deployment.md) for operator duties.
