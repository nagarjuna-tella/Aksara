# AI development console

!!! warning "Experimental development surface"
    The console, analysis pipelines, and provider integrations are outside the
    stable backend contract. They are not required for REST, synchronous MCP,
    or Durable Operations. See [stability labels](../concepts/stability.md).

The console accepts development questions and returns analysis or suggestions.
Some paths use local rules and project inspection; others call a configured
provider. Results depend on loaded application context and provider behavior.
The console is not an authenticated CRUD API for application users or a durable
workflow service.

## Verify the CLI entry point

```bash
aksara ai flows chat "hello" --format json
```

This greeting is handled locally without a provider. The JSON result has
`ok: true`, `intent: "greet"`, `flow_type: "conversational"`, and
`execution.mode: "conversational"`. It proves neither provider connectivity nor
correct analysis of your models.

For the available syntax:

```bash
aksara ai flows chat --help
```

`--provider` and `--model` select overrides for provider-backed requests;
`--format` accepts `text` or `json`. The top-level `aksara ai chat` path in older
examples is not registered in 0.7.0.

## Ask about application context

In a configured development application, prompts can ask to explain a model,
review a route, suggest indexes, or investigate a problem. The implementation
routes through conversational handling, investigation or intent analysis, and
flow/provider paths as appropriate. It is not a fixed list of eleven intents,
and not every prompt produces the same response fields.

Inspect `ok`, `error`, and `error_code` before using a result. `execution` can
contain a local report or a provider response; `prompt_pack` can be absent or
null. Treat these experimental shapes as development output, not a stable
integration contract. Provider availability and result quality require separate
testing with your application.

## Studio access

When Studio is enabled and accessible under your configured authentication,
its console uses `POST /studio/ai/console` with a `message` and optional
`provider_override` and `model_override`. Suggestions use
`GET /studio/ai/console/suggest?q=...`. These are Studio development endpoints;
do not expose them as a public application tool boundary. Follow
[Studio security guidance](../studio/configuration.md) before enabling access.

Autocomplete uses local intent suggestions. A real analysis request can include
application metadata in provider context. Review that context and your provider
configuration before sending development information externally.

## Use results deliberately

Console output is analysis and suggested next actions. Review code changes,
SQL, and migration plans using the ordinary application development process.
Experimental `ai plan apply` is a separate mutation-capable interface, not an
implicit consequence of receiving a console answer.

For agents that need to execute real application actions, use the
[authenticated MCP tutorial](../tutorials/ticket-desk-mcp.md). For work that must
survive retries or permission changes, use
[Durable Operations](../advanced/durable-operations.md). Neither guarantee is
established by a successful console response.
