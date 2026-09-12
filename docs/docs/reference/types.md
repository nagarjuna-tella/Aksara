# Types and annotations

Aksara includes inline annotations and a `py.typed` marker. These help editors
and type checkers, but do not establish complete strict typing coverage. The
framework still has recorded mypy debt. Do not treat handwritten interface
sketches as exported classes or assume a `py.typed` marker guarantees that an
application passes strict checking.

## Public contracts

Use the installed classes and their current signatures rather than copying
replacement stubs into an application.

| Surface | Sync/async boundary | Reference |
| --- | --- | --- |
| Query builders | `filter`, `order_by`, `limit`, and `offset` are synchronous; await terminal methods such as `all` and `first`. | [ORM](orm-reference.md) |
| Model persistence | Await individual `save` and `delete` operations. | [Models](../orm/models.md) |
| Serializer validation | `is_valid`, `validate`, and `validate_<field>` are synchronous; persistence through `save` is async. | [Serializers](../api/serializers.md) |
| ViewSet list query hook | `get_queryset` is synchronous. Configure operation-specific serializers, not `serializer_class`. | [ViewSets](../api/viewsets.md) |
| Permission hooks | `has_permission` and `has_object_permission` return booleans synchronously. | [Permissions](../api/permissions.md) |
| Signal receivers | Async callables, invoked with keyword arguments; `send` returns receiver/result pairs. | [Signals](../orm/signals.md) |

An async permission method returns a coroutine object when called synchronously;
that object is not an evaluated permission decision. Do not change a documented
sync hook to async merely to perform database I/O there.

## Fields and relations

Declare model fields with the actual constructors in `aksara.fields`.
Use `nullable=True` for database nullability. Constructor options are
type-specific; there is no generic field stub accepting arbitrary validators
or Django-style options.

A forward foreign key exposes its stored identifier. It is not a lazy,
awaitable related object. Use explicit loading or the documented
`select_related`/`get_related` pair. See [relations](../orm/relations.md) before
annotating a relation as though accessing it returns a model instance.

## HTTP inputs and outputs

Use FastAPI/Starlette request and response types for HTTP handlers. A
`(dictionary, status_code)` tuple is not a framework response-status contract.
Inspect the application's generated OpenAPI and the
[API reference](api-reference.md) for the response schema actually exposed.
Do not substitute a handwritten pagination `TypedDict` for that schema.

Application-owned payload types can describe your own contract, but annotations
do not replace runtime validation, authentication, or field-write policy.

## Configuration and experimental results

`aksara.conf.Settings` is the actual configuration type. The
[settings reference](settings-reference.md) documents its fields, defaults, and
environment variables. A handwritten uppercase `TypedDict` does not define new
configuration options.

AI planner, provider, and Studio result shapes remain experimental. Use their
actual exported types where available and handle the documented experimental
boundary; this page does not promise universal `AgentResult` or `QueryResult`
shapes across those systems.

## Type checking an application

Run the type checker your project uses against your own code and installed
dependencies. Review diagnostics explicitly. There is no documented bundled
`aksara.mypy` plugin to add to a mypy configuration, and this page does not
claim a complete parallel set of public `.pyi` stubs.

The [TypeScript client guide](../how-to/typescript-client.md) separately records
the generated client's known compilation limitation. Python annotations do not
prove the generated TypeScript package compiles.
