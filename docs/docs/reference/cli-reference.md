# CLI Reference

Command and parameter declarations from installed Aksara **0.7.1rc1**.

This generated reference describes parser syntax, literal defaults, and environment
bindings. It does not execute commands or prove their runtime effects. A `null`
default means no literal parser default; the command may discover configuration
or prompt later. Environment values and credentials are never captured.

Start with [CLI workflows](../cli/commands.md) for migrations, serving, diagnostics,
and worker guidance. See [configuration](settings-reference.md) for settings precedence.

The `agent`, `ai`, `ai-hub`, `ai-provider`, and `studio` command families are
**Experimental**. Their presence is not a stable backend guarantee.

Durable workers use a separate Python module entry point; see
[Durable Operations](../advanced/durable-operations.md). Ordinary `tasks` commands
do not manage Durable Operations.

Regenerate from an isolated wheel environment with
`python scripts/generate_public_cli_reference.py --python /path/to/venv/bin/python`.

<!-- Generated parser declarations; edit the generator, not the tables. -->

## aksara

Command group; choose a subcommand below.

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--quiet` | option / boolean | no | `false` | — |
| `--plain` | option / boolean | no | `false` | — |
| `--no-color` | option / boolean | no | `false` | — |
| `--force-color` | option / boolean | no | `false` | — |
| `--version` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara agent

Command group; choose a subcommand below.

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara agent context

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--sections, -s` | option / text | no | `""` | — |
| `--output, -o` | option / choice: json, pretty | no | `"pretty"` | — |
| `--summary` | option / boolean | no | `false` | — |
| `--size` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara agent playbook-run

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `key` | argument / text | yes | `null` | — |
| `--goal, -g` | option / text | no | `null` | — |
| `--sections, -s` | option / text | no | `""` | — |
| `--format, -f` | option / choice: text, json | no | `"text"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara agent playbooks

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--format, -f` | option / choice: pretty, json | no | `"pretty"` | — |
| `--category, -c` | option / text | no | `null` | — |
| `--risk, -r` | option / text | no | `null` | — |
| `--usage, -u` | option / text | no | `null` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara agent prompt

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--goal, -g` | option / text | yes | `null` | — |
| `--sections, -s` | option / text | no | `""` | — |
| `--custom-system-prompt, -c` | option / text | no | `null` | — |
| `--format, -f` | option / choice: text, json | no | `"text"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara agent workflow

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `goal` | argument / text | yes | `null` | — |
| `--playbook, -p` | option / text | no | `null` | — |
| `--no-diagnostics` | option / boolean | no | `false` | — |
| `--no-search` | option / boolean | no | `false` | — |
| `--search-query` | option / text | no | `null` | — |
| `--limit-search` | option / integer | no | `10` | — |
| `--limit-diagnostics` | option / integer | no | `10` | — |
| `--format, -f` | option / choice: text, json | no | `"text"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai

Command group; choose a subcommand below.

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara ai briefing

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--json` | option / boolean | no | `false` | — |
| `--summary` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai context

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--intent, -i` | option / text | no | `null` | — |
| `--mode, -m` | option / choice: read, design, modify | no | `"modify"` | — |
| `--scope, -s` | option / text | no | `null` | — |
| `--stdin` | option / boolean | no | `false` | — |
| `--format, -f` | option / choice: json, summary | no | `"summary"` | — |
| `--database-url` | option / text | no | `null` | AKSARA_DATABASE_URL, DATABASE_URL |
| `--help` | option / boolean | no | `false` | — |

## aksara ai continue

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--json` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai examples

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--provider, -p` | option / choice: openai, azure, anthropic | no | `null` | — |
| `--output-dir, -o` | option / text | no | `null` | — |
| `--force, -f` | option / boolean | no | `false` | — |
| `--list, -l` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai flows

Command group; choose a subcommand below.

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara ai flows actions

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--format` | option / choice: text, json | no | `"text"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai flows chat

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `message` | argument / text | yes | `null` | — |
| `--provider` | option / text | no | `null` | — |
| `--model` | option / text | no | `null` | — |
| `--format` | option / choice: text, json | no | `"text"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai flows debug

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--query` | option / text | no | `null` | — |
| `--json` | option / boolean | no | `false` | — |
| `--summary` | option / boolean | no | `false` | — |
| `--model` | option / text | no | `null` | — |
| `--route` | option / text | no | `null` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai flows diagnostic

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--issue-id` | option / text | no | `null` | — |
| `--action` | option / text | yes | `null` | — |
| `--format` | option / choice: text, json | no | `"text"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai flows graph

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--json` | option / boolean | no | `false` | — |
| `--summary` | option / boolean | no | `false` | — |
| `--events` | option / boolean | no | `false` | — |
| `--rebuild` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai flows migration

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--app` | option / text | no | `null` | — |
| `--name` | option / text | no | `null` | — |
| `--action` | option / text | yes | `null` | — |
| `--format` | option / choice: text, json | no | `"text"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai flows model

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `model_name` | argument / text | yes | `null` | — |
| `--action` | option / text | yes | `null` | — |
| `--format` | option / choice: text, json | no | `"text"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai flows performance

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--json` | option / boolean | no | `false` | — |
| `--summary` | option / boolean | no | `false` | — |
| `--issues` | option / boolean | no | `false` | — |
| `--metrics` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai flows query

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--sql` | option / text | yes | `null` | — |
| `--action` | option / text | yes | `null` | — |
| `--format` | option / choice: text, json | no | `"text"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai flows review

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--json` | option / boolean | no | `false` | — |
| `--summary` | option / boolean | no | `false` | — |
| `--metrics` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai flows route

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `route_spec` | argument / text | yes | `null` | — |
| `--action` | option / text | yes | `null` | — |
| `--format` | option / choice: text, json | no | `"text"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai hints

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--view, -v` | option / text | no | `null` | — |
| `--route, -r` | option / text | no | `null` | — |
| `--risk` | option / choice: low, medium, high | no | `null` | — |
| `--format, -f` | option / choice: text, json | no | `"text"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai investigate

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--json` | option / boolean | no | `false` | — |
| `--summary` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai models

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--provider, -p` | option / text | no | `null` | — |
| `--format, -f` | option / choice: table, json | no | `"table"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai plan

Command group; choose a subcommand below.

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara ai plan apply

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `path` | argument / text | no | `null` | — |
| `--yes, -y` | option / boolean | no | `false` | — |
| `--format, -f` | option / choice: summary, json | no | `"summary"` | — |
| `--database-url` | option / text | no | `null` | AKSARA_DATABASE_URL, DATABASE_URL |
| `--help` | option / boolean | no | `false` | — |

## aksara ai plan preview

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `path` | argument / text | no | `null` | — |
| `--format, -f` | option / choice: summary, json | no | `"summary"` | — |
| `--database-url` | option / text | no | `null` | AKSARA_DATABASE_URL, DATABASE_URL |
| `--help` | option / boolean | no | `false` | — |

## aksara ai plan template

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--intent, -i` | option / text | yes | `null` | — |
| `--mode, -m` | option / choice: read, design, modify | no | `"modify"` | — |
| `--include-schema` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai providers

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--format, -f` | option / choice: table, json | no | `"table"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai run

Command group; choose a subcommand below.

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara ai run diagnostic

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--issue-id` | option / text | no | `null` | — |
| `--action` | option / text | yes | `null` | — |
| `--provider` | option / text | no | `null` | — |
| `--model` | option / text | no | `null` | — |
| `--format` | option / choice: text, json | no | `"text"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai run migration

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--app` | option / text | no | `null` | — |
| `--name` | option / text | no | `null` | — |
| `--action` | option / text | yes | `null` | — |
| `--provider` | option / text | no | `null` | — |
| `--model` | option / text | no | `null` | — |
| `--format` | option / choice: text, json | no | `"text"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai run model

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `model_name` | argument / text | yes | `null` | — |
| `--action` | option / text | yes | `null` | — |
| `--provider` | option / text | no | `null` | — |
| `--model` | option / text | no | `null` | — |
| `--format` | option / choice: text, json | no | `"text"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai run query

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--sql` | option / text | yes | `null` | — |
| `--action` | option / text | yes | `null` | — |
| `--provider` | option / text | no | `null` | — |
| `--model` | option / text | no | `null` | — |
| `--format` | option / choice: text, json | no | `"text"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai run route

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `route_spec` | argument / text | yes | `null` | — |
| `--action` | option / text | yes | `null` | — |
| `--provider` | option / text | no | `null` | — |
| `--model` | option / text | no | `null` | — |
| `--format` | option / choice: text, json | no | `"text"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai schema-health

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--format, -f` | option / choice: table, json | no | `"table"` | — |
| `--database-url` | option / text | no | `null` | AKSARA_DATABASE_URL, DATABASE_URL |
| `--help` | option / boolean | no | `false` | — |

## aksara ai schema-issues

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--severity, -s` | option / text | no | `null` | — |
| `--kind, -k` | option / text | no | `null` | — |
| `--table, -t` | option / text | no | `null` | — |
| `--app-label, -a` | option / text | no | `null` | — |
| `--format, -f` | option / choice: table, json | no | `"table"` | — |
| `--database-url` | option / text | no | `null` | AKSARA_DATABASE_URL, DATABASE_URL |
| `--help` | option / boolean | no | `false` | — |

## aksara ai secrets

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--format, -f` | option / choice: table, json | no | `"table"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai validate

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--format, -f` | option / choice: text, json | no | `"text"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai-hub

Command group; choose a subcommand below.

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara ai-hub configure

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `provider_name` | argument / choice: openai, azure, anthropic, ollama, custom | yes | `null` | — |
| `--api-key` | option / text | no | `null` | — |
| `--model` | option / text | no | `null` | — |
| `--base-url` | option / text | no | `null` | — |
| `--enable, --disable` | option / boolean | no | `true` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai-hub defaults

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--chat-model` | option / text | no | `null` | — |
| `--code-model` | option / text | no | `null` | — |
| `--embeddings-model` | option / text | no | `null` | — |
| `--chat-provider` | option / text | no | `null` | — |
| `--code-provider` | option / text | no | `null` | — |
| `--embeddings-provider` | option / text | no | `null` | — |
| `--format, -f` | option / choice: pretty, json | no | `"pretty"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai-hub doctor

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--format, -f` | option / choice: pretty, json | no | `"pretty"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai-hub models

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--format, -f` | option / choice: pretty, json | no | `"pretty"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai-hub providers

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--format, -f` | option / choice: pretty, json | no | `"pretty"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai-hub status

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--format, -f` | option / choice: pretty, json | no | `"pretty"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai-provider

Command group; choose a subcommand below.

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara ai-provider configure

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `provider_name` | argument / choice: openai, azure, anthropic, ollama, custom | yes | `null` | — |
| `--api-key` | option / text | no | `null` | — |
| `--model` | option / text | no | `null` | — |
| `--base-url` | option / text | no | `null` | — |
| `--save-to` | option / choice: env, json | no | `"env"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai-provider detect

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara ai-provider list

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--format, -f` | option / choice: pretty, json | no | `"pretty"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara ai-provider ping

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--provider, -p` | option / text | no | `null` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara collectstatic

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara createsuperuser

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--database-url, -d` | option / text | no | `null` | AKSARA_DATABASE_URL, DATABASE_URL |
| `--email, -e` | option / text | no | `null` | — |
| `--password, -p` | option / text | no | `null` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara db

Command group; choose a subcommand below.

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara db clear

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--force, -f` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara db profile

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--app, -a` | option / text | no | `null` | — |
| `--limit, -n` | option / integer | no | `20` | — |
| `--format, -f` | option / choice: pretty, json | no | `"pretty"` | — |
| `--slow` | option / boolean | no | `false` | — |
| `--recent` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara db stats

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--app, -a` | option / text | no | `null` | — |
| `--format, -f` | option / choice: pretty, json | no | `"pretty"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara dbsetup

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--host` | option / text | no | `"localhost"` | — |
| `--port` | option / integer | no | `5432` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara dev

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `app_path` | argument / text | no | `"main:app"` | — |
| `--host, -h` | option / text | no | `"127.0.0.1"` | — |
| `--port, -p` | option / integer | no | `8000` | — |
| `--reload, -r` | option / boolean | no | `true` | — |
| `--no-reload` | option / boolean | no | `false` | — |
| `--log-level, -l` | option / choice: debug, info, warning, error | no | `"info"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara doctor

Command group; choose a subcommand below.

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara doctor ai

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara doctor db

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara doctor fix-plan

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--format, -f` | option / choice: text, json | no | `"text"` | — |
| `--only-errors` | option / boolean | no | `false` | — |
| `--only-with-actions` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara doctor launch-check

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--format, -f` | option / choice: pretty, json | no | `"pretty"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara doctor production-check

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--format, -f` | option / choice: pretty, json | no | `"pretty"` | — |
| `--release` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara doctor run

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--format, -f` | option / choice: pretty, json | no | `"pretty"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara doctor security-check

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--format, -f` | option / choice: pretty, json | no | `"pretty"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara doctor summary

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara examples

Command group; choose a subcommand below.

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara examples validate

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--format, -f` | option / choice: pretty, json | no | `"pretty"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara format

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `path` | argument / text | no | `"."` | — |
| `--check` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara gaps

Command group; choose a subcommand below.

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara gaps fix-plan

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--format, -f` | option / choice: pretty, json | no | `"pretty"` | — |
| `--only-blocking` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara gaps json

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--categories, -c` | option / text | no | `null` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara gaps list-critical

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--format, -f` | option / choice: pretty, json | no | `"pretty"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara gaps list-errors

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--format, -f` | option / choice: pretty, json | no | `"pretty"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara gaps run

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--format, -f` | option / choice: pretty, json | no | `"pretty"` | — |
| `--categories, -c` | option / text | no | `null` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara gaps summary

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara generate

Command group; choose a subcommand below.

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara generate sdk

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--language` | option / choice: typescript | no | `"typescript"` | — |
| `--output` | option / text | no | `"api.ts"` | — |
| `--views-module` | option / text | no | `null` | — |
| `--stdout` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara info

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--database-url, -d` | option / text | no | `null` | AKSARA_DATABASE_URL, DATABASE_URL |
| `--help` | option / boolean | no | `false` | — |

## aksara inspect

Command group; choose a subcommand below.

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara inspect models

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--model, -m` | option / text | no | `null` | — |
| `--fields` | option / boolean | no | `false` | — |
| `--relationships` | option / boolean | no | `false` | — |
| `--json` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara inspect queries

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--limit, -n` | option / integer | no | `10` | — |
| `--json` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara lint

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `path` | argument / text | no | `"."` | — |
| `--fix` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara makemigrations

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--app, -a` | option / text | no | `null` | — |
| `--output, -o` | option / text | no | `null` | — |
| `--name, -n` | option / text | no | `"auto"` | — |
| `--stdout` | option / boolean | no | `false` | — |
| `--sql` | option / boolean | no | `false` | — |
| `--merge` | option / boolean | no | `false` | — |
| `merge_app` | argument / text | no | `null` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara migrate

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--app, -a` | option / text | no | `null` | — |
| `--database-url, -d` | option / text | no | `null` | AKSARA_DATABASE_URL, DATABASE_URL |
| `--migrations-dir, -m` | option / text | no | `null` | — |
| `--dry-run` | option / boolean | no | `false` | — |
| `--fake` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara models

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--app, -a` | option / text | no | `null` | — |
| `--ai` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara precommit

Command group; choose a subcommand below.

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara precommit init

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara precommit run

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--hook, -h` | option / text | no | `null` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara run

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `app_path` | argument / text | yes | `null` | — |
| `--host, -h` | option / text | no | `"127.0.0.1"` | — |
| `--port, -p` | option / integer | no | `8000` | — |
| `--reload, -r` | option / boolean | no | `false` | — |
| `--workers, -w` | option / integer | no | `1` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara search

Command group; choose a subcommand below.

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara search index

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--json-output, --json` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara search query

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `query_text` | argument / text | yes | `null` | — |
| `--kind, -k` | option / text | no | `null` | — |
| `--top, -n` | option / integer | no | `10` | — |
| `--semantic, -s` | option / boolean | no | `false` | — |
| `--json-output, --json` | option / boolean | no | `false` | — |
| `--min-score` | option / float | no | `0.0` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara shell

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--database-url, -d` | option / text | no | `null` | AKSARA_DATABASE_URL, DATABASE_URL |
| `--no-ipython` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara startapp

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `app_name` | argument / text | yes | `null` | — |
| `--directory, -d` | option / text | no | `"."` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara startproject

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `project_name` | argument / text | yes | `null` | — |
| `--directory, -d` | option / text | no | `"."` | — |
| `--template, -t` | option / text | no | `"basic"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara status

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--database-url, -d` | option / text | no | `null` | AKSARA_DATABASE_URL, DATABASE_URL |
| `--help` | option / boolean | no | `false` | — |

## aksara studio

Command group; choose a subcommand below.

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara studio ai-context

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--format, -f` | option / choice: json, summary | no | `"json"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara studio handshake

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--app, -a` | option / text | no | `"main:app"` | — |
| `--format, -f` | option / choice: json, pretty | no | `"pretty"` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara studio open

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--host, -h` | option / text | no | `"127.0.0.1"` | — |
| `--port, -p` | option / integer | no | `8000` | — |
| `--https, --no-https` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara studio ui-path

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara studio url

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--host, -h` | option / text | no | `"localhost"` | — |
| `--port, -p` | option / integer | no | `8000` | — |
| `--https, --no-https` | option / boolean | no | `false` | — |
| `--section, -s` | option / choice: overview, models, routes, migrations, db-queries, ai-profiles, diagnostics | no | `null` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara tasks

Command group; choose a subcommand below.

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara tasks list

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--status, -s` | option / choice: pending, running, completed, failed | no | `"failed"` | — |
| `--queue, -q` | option / text | no | `null` | — |
| `--task-name, -t` | option / text | no | `null` | — |
| `--limit, -n` | option / integer | no | `20` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara tasks purge

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--status, -s` | option / choice: completed, failed | no | `["completed"]` | — |
| `--older-than-days, -d` | option / float | no | `7.0` | — |
| `--yes, -y` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara tasks reenqueue

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `task_id` | argument / text | no | `null` | — |
| `--all` | option / boolean | no | `false` | — |
| `--queue, -q` | option / text | no | `null` | — |
| `--yes, -y` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara tasks stats

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara templates

Command group; choose a subcommand below.

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara templates list

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `--help` | option / boolean | no | `false` | — |

## aksara test

Additional options are forwarded to the underlying tool (pytest for `aksara test`).
Its supported flags and installed plugins determine validity.

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `args` | argument / text (variadic) | no | `null` | — |
| `--help` | option / boolean | no | `false` | — |

## aksara typecheck

| Parameter | Kind / type | Required | Literal default | Environment |
|---|---|---|---|---|
| `path` | argument / text | no | `"."` | — |
| `--strict` | option / boolean | no | `false` | — |
| `--help` | option / boolean | no | `false` | — |
