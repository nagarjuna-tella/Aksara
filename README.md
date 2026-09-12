<p align="center">
  <img src="https://raw.githubusercontent.com/nagarjuna-tella/Aksara/main/aksara/studio/static/icons/aksara-logo.svg" width="64" alt="Aksara logo"/>
</p>

<h1 align="center">Aksara</h1>

<p align="center">
  An async PostgreSQL backend framework that generates REST APIs and authorized MCP tools from the same model and policy boundary.
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a href="https://github.com/nagarjuna-tella/Aksara/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-22c55e?style=flat-square" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/release-v0.7.1-22c55e?style=flat-square" alt="Release v0.7.1">
  <img src="https://img.shields.io/badge/PostgreSQL-required-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL required">
</p>

## What is Aksara?

Aksara is a PostgreSQL-backed Python application framework with generated APIs,
shared authorization boundaries, and durable actions that recheck authority
before supported effects.

It is for backend engineers building tenant-aware applications such as support
desks, internal operations tools and SaaS APIs. Start with ordinary models and
REST endpoints; agents can become clients later. You operate the Python service
and PostgreSQL yourself.

## Why Aksara?

FastAPI supplies typed HTTP endpoints, validation and dependency injection.
Aksara adds an opinionated ORM/migration path, generated model APIs, application
policy and tenant enforcement, and opt-in durable execution. Choose it when
that shared contract is useful enough to justify adopting its data model.

The distinctive use case is an action that waits, retries, or outlives its
worker: current authority must still permit the mutation when it eventually
runs. With `postgres_atomic`, supported application changes and authoritative
Operation success commit in the same PostgreSQL transaction. External effects
have a separate reconciliation contract; no unconditional exactly-once promise
is made.

Aksara is pre-1.0. The backend and durable contracts are bounded and tested;
planners, autonomous workflows, provider quality, memory and Studio internals
remain experimental. Applications supply credential verification and business
policy. Ordinary tasks do not automatically preserve a complete Principal.
Read the [v0.7 stability contract](https://nagarjuna-tella.github.io/Aksara/roadmap/v0-7-stability-contract/)
for the required production profile and exclusions.

## 10-Minute Quickstart

Build a protected ticket API using a disposable PostgreSQL database:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install "aksara-framework==0.7.1"
aksara startproject ticket_desk
cd ticket_desk
aksara dbsetup
```

Continue with [First project: a ticket desk](docs/docs/getting-started/first-project.md)
for the complete model, routes, local authentication adapter, migrations,
curl calls and standard-library API tests. The guide uses the installed package
and keeps MCP, AI and Studio out of the initial application path.

`aksara doctor launch-check` diagnoses the local project. Production requires
separate role, tenant and operating checks; see the
[deployment guide](docs/docs/tutorials/deployment.md).

## REST and MCP

The two MCP-related paths have different meanings:

| Path | Purpose |
| --- | --- |
| `/mcp/` | MCP Streamable HTTP protocol endpoint used by official clients |
| `/ai/tools/mcp` | Permission-filtered HTTP JSON inspection catalog of generated tool metadata |

MCP requires trusted server-side authentication that resolves the bearer
credential into a `Principal`; enabling the route does not verify credentials
for your application. Follow the
[complete MCP quickstart](https://nagarjuna-tella.github.io/Aksara/getting-started/mcp/)
for the copy-pasteable model → migration → REST → Principal → official client →
persisted invocation path.

## Core Features

| Classification | Surface |
| --- | --- |
| Stable v0.6 | Async PostgreSQL ORM, relations and migrations |
| Stable v0.6 | Generated REST CRUD, validation, filters and pagination |
| Stable v0.6 | Principal, permissions, PolicyEngine, tenant and field enforcement |
| Stable v0.6 | MCP Streamable HTTP, generated tools, approval boundary, audit events, structured failures and runtime limits |
| Stable v0.6 | Core CLI, Doctor production policy, and PostgreSQL task queue |
| Stable v0.7 | Opt-in durable Operations, Attempts, idempotency, fencing, current reauthorization, decisions, retention, and external-effect recovery |
| Functional but evolving | Admin details, storage backends, email, search, SDK generation and `DurableStep` |
| Experimental | Studio/Studio AI, planners, prompt providers, investigation sessions, code patches, memory and autonomous workflows |

Application approval workflow UX, durable compliance retention, and external
exactly-once effects remain application-owned. Protocol-level durable MCP Tasks
are deferred because the official SDK does not yet implement the current Tasks
extension; synchronous MCP tools remain unchanged.

## Security boundary

Applications verify credentials and resolve a server-owned `Principal`. Aksara
then applies covered permission, object, policy, field, tenant, ORM transaction,
and RLS checks to REST and MCP execution. Schemas and hidden UI controls are
helpful descriptions; they are not authorization controls.

For production:

```bash
aksara doctor security-check
aksara doctor production-check --release
```

Read the
[Security Overview](https://nagarjuna-tella.github.io/Aksara/security/overview/)
and
[Production Hardening guide](https://nagarjuna-tella.github.io/Aksara/security/production-hardening/).
Release gates and security tests provide repository evidence; they are not an
external audit or certification.

## Configuration

The global `aksara.conf.settings` object is the runtime source of truth. Use
environment variables for deploy-time values and `configure(...)` for explicit
Python overrides. Precedence is explicit configuration, `AKSARA_*` environment
variables, supported aliases such as `DATABASE_URL`, then defaults.

```dotenv
DATABASE_URL=postgresql://user:password@localhost:5432/opsdesk
AKSARA_DEBUG=true
AKSARA_MCP_ENABLED=false
AKSARA_AI_ENABLED=false
AKSARA_ENABLE_STUDIO=false
```

An `AKSARA = {...}` dictionary does not configure the runtime. See the
[Settings Reference](https://nagarjuna-tella.github.io/Aksara/reference/settings-reference/).

## Open Studio

Studio is an experimental inspection and AI surface at `/studio/ui`. It is
disabled in new projects. Enabling it requires its secret/authentication and
production exposure settings; see the
[Studio guide](https://nagarjuna-tella.github.io/Aksara/studio/).

## Use AI

Provider-backed prompt execution is optional and experimental. Configure the
current AI Hub path when you need it:

```bash
aksara ai-hub configure openai
aksara ai-hub status
aksara ai-hub doctor
```

There is no public `AgentRuntime` or `Planner` class in v0.7.1. The documented
real primitives remain experimental and are described in the
[AI Mode guide](https://nagarjuna-tella.github.io/Aksara/ai-mode/).

## Use MCP

Set `AKSARA_MCP_ENABLED=true` only after adding server-side Principal
resolution, then connect an official MCP client to
`http://127.0.0.1:8000/mcp/`. MCP does not require an AI model provider.

## Examples

- [Basic app](https://github.com/nagarjuna-tella/Aksara/tree/main/examples/basic_app)
- [Blog](https://github.com/nagarjuna-tella/Aksara/tree/main/examples/blog)
- [CRM](https://github.com/nagarjuna-tella/Aksara/tree/main/examples/crm)
- [Multi-tenant app](https://github.com/nagarjuna-tella/Aksara/tree/main/examples/multitenant)
- [Support Desk production reference](https://github.com/nagarjuna-tella/Aksara/tree/main/examples/support_desk)

From a source checkout, validate bundled examples with:

```bash
aksara examples validate --format json
```

## Documentation

- [Installation](https://nagarjuna-tella.github.io/Aksara/getting-started/installation/)
- [First Project](https://nagarjuna-tella.github.io/Aksara/getting-started/first-project/)
- [MCP Quickstart](https://nagarjuna-tella.github.io/Aksara/getting-started/mcp/)
- [Durable Authorized Operations](https://nagarjuna-tella.github.io/Aksara/advanced/durable-operations/)
- [v0.7 Stability Contract](https://nagarjuna-tella.github.io/Aksara/roadmap/v0-7-stability-contract/)
- [ORM](https://nagarjuna-tella.github.io/Aksara/orm/)
- [API](https://nagarjuna-tella.github.io/Aksara/api/)
- [Security](https://nagarjuna-tella.github.io/Aksara/security/overview/)
- [CLI](https://nagarjuna-tella.github.io/Aksara/cli/)
- [Runtime compatibility](https://nagarjuna-tella.github.io/Aksara/reference/runtime-compatibility/)

## Roadmap

v0.7.0 implements the accepted Durable Authorized Operations architecture
while preserving the v0.6 synchronous surfaces and PostgreSQL-first deployment
profile. See the
[Roadmap](https://nagarjuna-tella.github.io/Aksara/roadmap/).

## Contributing

Read the
[Contributing Guide](https://github.com/nagarjuna-tella/Aksara/blob/main/CONTRIBUTING.md)
and [Code of Conduct](https://github.com/nagarjuna-tella/Aksara/blob/main/CODE_OF_CONDUCT.md).
Run the relevant tests and strict documentation build before opening a pull
request.

## License

[MIT](https://github.com/nagarjuna-tella/Aksara/blob/main/LICENSE)
