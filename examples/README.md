# Aksara Examples

This folder contains real-world example apps built with Aksara.

Each example demonstrates different patterns and features. Use them as references or starting points for your own projects.

---

## Quick Overview

| Example | Path | What It Shows |
|---------|------|---------------|
| **Blog** | `examples/blog/` | Posts, comments, publish workflow, tags |
| **CRM** | `examples/crm/` | Customers, deals, pipeline stages |
| **Multitenant** | `examples/multitenant/` | Tenant models, middleware, scoped queries |
| **AI Providers** | `examples/ai_providers/` | BYO LLM wiring with OpenAI/Azure/Anthropic |
| **Basic App** | `examples/basic_app/` | Minimal working example |

---

## 1. Blog

**Path:** `examples/blog/`

**What it demonstrates:**

- Post and Comment models with relationships
- CRUD operations with ViewSets
- Publish workflow (draft → published)
- Tag support with JSON fields
- Admin registration and customization

**Key concepts:**

- ForeignKey relationships
- Query filtering
- Boolean state fields

**Docs:** [Blog Pattern](../docs/docs/patterns/blog.md)

---

## 2. CRM

**Path:** `examples/crm/`

**What it demonstrates:**

- Customer, Deal, Pipeline, Stage models
- Multi-model relationships
- Custom ViewSet actions (close deal, move stage)
- List filters in Admin
- Reporting-style queries

**Key concepts:**

- Complex model relationships
- Custom actions on ViewSets
- State machine patterns

**Docs:** [CRM Pattern](../docs/docs/patterns/crm.md)

---

## 3. Multitenant

**Path:** `examples/multitenant/`

**What it demonstrates:**

- Tenant and TenantUser models
- Tenant resolution middleware
- Base model class with automatic tenant FK
- Scoped queries that filter by current tenant

**Key concepts:**

- Middleware for request context
- Automatic query scoping
- SaaS data isolation patterns

**Docs:** [Multitenant Pattern](../docs/docs/patterns/multitenant.md)

---

## 4. AI Providers

**Path:** `examples/ai_providers/`

**What it demonstrates:**

- Protocol-based LLM client adapters
- Soft SDK imports (no hard dependencies)
- Environment-based configuration
- Prompt building from AI route hints
- Example AI-powered ViewSet actions

**Key concepts:**

- Adapter pattern for swappable providers
- Settings from environment variables
- Using `@ai_route_hint` with prompts
- Testing without real API keys

**How to copy to your project:**

```bash
aksara ai examples -o ./ai_adapters
```

**Docs:** [Bring Your Own LLM](../docs/docs/ai-mode/bring-your-own-llm.md)

---

## 5. Basic App

**Path:** `examples/basic_app/`

**What it demonstrates:**

- Minimal working Aksara application
- Single model with ViewSet
- Basic project structure

**Use this if:**

- You want to see the simplest possible setup
- You're debugging or testing

---

## Running an Example

Most examples can be run directly:

```bash
cd examples/blog

# Set up database interactively
aksara dbsetup

# Run migrations
aksara migrate

# Start development server
aksara dev
```

Check each example's README for specific instructions.

---

## Creating a Project from a Pattern

You can create a new project using one of the patterns:

```bash
# Blog pattern
aksara startproject myblog --template blog

# CRM pattern
aksara startproject mycrm --template crm

# Multitenant pattern
aksara startproject saas --template multitenant
```

See [Choosing a Pattern](../docs/docs/getting-started/patterns.md) for help deciding which to use.

---

## Contributing

Have a pattern or example to share? Contributions welcome!

1. Create a new folder under `examples/`
2. Include a README.md explaining what it demonstrates
3. Ensure it runs with a fresh database
4. Submit a pull request
