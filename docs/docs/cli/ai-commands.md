# AI development commands

!!! warning "Experimental"
    These development tools sit outside the stable backend contract. Analysis,
    provider quality, planning, and Studio internals remain experimental. They
    are not required for REST, synchronous MCP, or Durable Operations. See
    [stability boundaries](../concepts/stability.md).

The installed CLI has several distinct AI command families. Use actual
subcommand help and the [generated reference](../reference/cli-reference.md) to
find their arguments. Historical `ai query`, `ai generate`, `ai doctor`,
`ai agent`, `ai patch`, `ai ask`, and `ai config` commands are not registered in
0.7.0. A code-generation or autonomous-execution example using those names does
not describe a supported shortcut.

## Discover the available surface

```bash
aksara ai --help
aksara ai flows --help
aksara ai run --help
aksara ai plan --help
aksara ai-provider --help
aksara ai-hub --help
aksara agent --help
```

| Family | Purpose |
|---|---|
| `ai context`, `ai hints` | Assemble development context or inspect hint metadata |
| `ai schema-health`, `ai schema-issues` | Inspect schema analysis reports |
| `ai flows` | Flow-oriented analysis and console entry points |
| `ai run` | Provider-backed flow execution |
| `ai plan` | Generate a JSON plan template, preview a file, or apply a plan |
| `ai-provider`, `ai-hub` | Provider configuration and inspection |
| `agent` | Development context, prompts, playbooks and workflow analysis |

The names are not interchangeable. In particular, experimental plan application
is not a Durable Operation, and an analysis suggestion is not an approval grant.

## Inspect schema guidance

With your models and database configured:

```bash
aksara ai schema-health --format json
aksara ai schema-issues --severity danger --format json
```

See [Schema Doctor](../ai-mode/schema-doctor.md) for prerequisites and report
meaning. These commands do not automatically fix models or apply migrations.
For deployment readiness, use [Doctor](../diagnostics.md) instead.

## Try the console without a provider

```bash
aksara ai flows chat "hello" --format json
```

The greeting path returns a local conversational response. This verifies the
console entry point, not model quality or application analysis. Other prompts
can require a configured provider and can send assembled context to it; inspect
your provider and application configuration before running those prompts.

See the [console guide](../ai-mode/console.md) for its boundaries. The correct
CLI path is `ai flows chat`, even where historical help examples omit `flows`.

## Work with a plan file

```bash
aksara ai plan template --intent "Describe the ticket model" --mode read
aksara ai plan preview --help
aksara ai plan apply --help
```

`template` prints a starter JSON structure. It does not infer a complete plan
from the description. `preview` takes a plan file or stdin; `apply` is a separate
mutation-capable command. Neither is the free-form `ai plan "do this"` interface
shown in older documentation. Review plan operations, configuration, and code
changes independently before applying one. This release does not claim an
end-to-end provider or plan-application validation from help output.

## Configuration and safe MCP use

Use the [settings reference](../reference/settings-reference.md) and
[provider guide](../ai-mode/providers.md) for configuration. Do not pass actual
provider keys in copied command examples or attach them to diagnostic evidence.

To expose application actions safely to an external agent, follow the
[official MCP client tutorial](../tutorials/ticket-desk-mcp.md). Development
console access is not a substitute for that authenticated, scoped application
execution boundary.
