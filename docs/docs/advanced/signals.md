# Signals and application side effects

The canonical [model signal guide](../orm/signals.md) documents the four
built-in events, exact payloads, explicit connection API, exception behavior,
and a runnable custom-signal example.

## Choose the right mechanism

| Requirement | Approach |
| --- | --- |
| Normalize an individual model save | A small `pre_save` receiver; do not assume it covers bulk or raw writes. |
| Validate all supported write paths | Explicit input validation and appropriate database constraints. |
| Commit related database mutations together | An explicit [transaction](../orm/expressions-and-transactions.md) using the same pinned connection. |
| Run ordinary asynchronous work | [Background tasks](background-tasks.md), with their documented retry and delivery limits. |
| Recover authorized work after worker loss | [Durable Operations](durable-operations.md), including explicit external-outcome handling. |

## A callback is not commit evidence

`post_save` describes where a callback runs relative to the model's SQL work.
It does not mean the outer transaction committed. A notification or search-index
write performed there can survive a database rollback; a process crash can
also prevent a callback from running after a committed statement.

For audit requirements, identify the write paths that must be covered and the
retention and transaction guarantees required. Model callbacks alone do not
cover arbitrary SQL, all bulk operations, or durable delivery. Avoid recording
an entire model dictionary without a deliberate sensitive-field policy.

## Test subscriptions, not patched names

A connected receiver is a stored callable. Patching the module attribute after
connection does not replace that stored callback. Connect the test receiver
explicitly and disconnect it in `finally`. Test both successful dispatch and
receiver failures; separately test database rollback and external effects when
those are part of the application contract.
