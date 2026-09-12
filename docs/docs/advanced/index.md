# Application patterns beyond the basics

Choose a guide when your application needs the behavior below. Start with the
[ticket desk tutorial](../getting-started/first-project.md) if you have not yet
created models, applied migrations and exposed a protected API.

## Work and recovery

| You need to… | Read | Boundary |
| --- | --- | --- |
| Queue work outside a request | [Background tasks](background-tasks.md) | Ordinary tasks have their own retry and delivery contract. |
| Recover an authorized operation after failure | [Durable Operations](durable-operations.md) | Application mutations are atomic only within the supported same-database transaction boundary. |
| Reuse a persisted step result | [Generic relations and persisted steps](generic-relations-and-durable-workflows.md) | DurableStep is evolving and is distinct from a durable Operation. |
| React to an individual model save or delete | [Signals](signals.md) | A callback is not proof that the surrounding transaction committed. |

For a working example that grows the tutorial application, follow
[background reports](../tutorials/ticket-desk-reports.md), then
[durable ticket resolution](../tutorials/ticket-desk-durable.md).

## Data and application behavior

| You need to… | Read |
| --- | --- |
| Reject or normalize input | [Validation](validation.md) and [serializer hooks](../api/serializers.md) |
| Define a custom field | [Custom fields](custom-fields.md) |
| Store files or send application email | [Media and email](media-and-email.md) |
| Select request language and timezone | [Internationalization and timezones](internationalization-and-timezones.md) |
| Reference different model types | [Generic relations](generic-relations-and-durable-workflows.md) |

## Testing and performance

Use [testing](testing.md) for application fixtures and isolation boundaries,
[performance](performance.md) for measurement and query design, and
[query profiling](../debugging/query-profiling.md) for the available diagnostics.

The [caching guide](caching.md) explains application-owned caching. Aksara does
not provide a public general-purpose `aksara.cache` API.

These guides build on [models](../orm/models.md),
[ViewSets](../api/viewsets.md) and [application boundaries](../concepts/application-boundaries.md).
Consult [stability](../concepts/stability.md) before relying on an evolving or
experimental surface, and the [production guide](../tutorials/deployment.md)
when moving a working application into service.
