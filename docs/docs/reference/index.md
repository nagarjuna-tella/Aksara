# Reference

Use this section to look up supported interfaces and configuration. For a
complete install-to-application sequence, start with
[First project: a ticket desk](../getting-started/first-project.md).

## Find a contract

| You need to look up… | Reference |
| --- | --- |
| Configuration fields, environment variables and precedence | [Settings](settings-reference.md) |
| ViewSets, serializers, permissions and actions | [API](api-reference.md) |
| Models, fields, queries and managers | [ORM](orm-reference.md) |
| Command arguments, flags and parser defaults | [CLI](cli-reference.md) |
| Exception families and HTTP error handling | [Exceptions](exceptions.md) |
| Type aliases and their import paths | [Types](types.md) |
| Supported Python, PostgreSQL and web dependencies | [Runtime compatibility](runtime-compatibility.md) |

The settings and CLI references expose declarations from the implementation.
A parser default does not establish the effects of running a command. Use the
linked workflows for prerequisites, database setup and operational checks.
The API and ORM pages describe selected public contracts; they are not a
catalog of every internal class or method.

## Choose guidance by task

- **Create and run an application:** follow the [first project](../getting-started/first-project.md), or the [template-specific setup](../getting-started/patterns.md) when using `startproject`.
- **Understand data access:** read [models](../orm/models.md), [queries](../orm/querying.md) and [transactions](../orm/expressions-and-transactions.md).
- **Protect an endpoint:** start with [authentication](../api/authentication.md) and [permissions](../api/permissions.md); check the [custom-action boundary](../api/actions.md) before adding an action.
- **Operate a deployment:** use the [production guide](../tutorials/deployment.md), [Doctor](../diagnostics.md) and [upgrade guide](../operations/upgrade-v07.md).

For terminology and maturity, see the [glossary](../glossary.md) and
[stability guide](../concepts/stability.md). A successful import alone does not
make an internal or experimental interface stable.

## Check the installed version

```bash
aksara --version
```

Use the [changelog](../changelog.md) and release stability contracts to understand
the installed version's supported surface. The local package can differ from
the version used to build the documentation.
