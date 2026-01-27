# AI Mode

AI-powered development tools built into Aksara.

---

## Overview

Aksara's AI Mode provides developer tools that understand your codebase:

| Tool | Purpose |
|------|---------|
| [Tools](tools.md) | AI-callable functions for CRUD, queries, migrations |
| [Context Engine](context-engine.md) | Gathers relevant code context |
| [Query Engine](query-engine.md) | Natural language to SQL |
| [Codegen](codegen.md) | Generate models, viewsets, tests |
| [Patch Engine](patch-engine.md) | Safe code modifications |
| [Planner](planner.md) | Multi-step task planning |
| [Agent Runtime](agent-runtime.md) | Execute AI agents |
| [Schema Doctor](schema-doctor.md) | Schema analysis and fixes |

---

## Quick Start

### Enable AI Mode

```python
# settings.py
AKSARA = {
    "AI_MODE": True,
    "AI_PROVIDER": "openai",  # or "anthropic", "local"
}
```

### Use AI Commands

```bash
# Generate a model
aksara ai generate "User model with email and name fields"

# Query data
aksara ai query "Find all users who signed up this week"

# Fix schema issues  
aksara ai doctor --fix
```

### Integrate in Code

```python
from aksara.ai import query_natural_language

# Natural language queries
users = await query_natural_language(
    "active users who haven't logged in for 30 days"
)
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      AI Mode Layer                           │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐ │
│  │   Tools   │  │  Context  │  │   Query   │  │  Codegen  │ │
│  │           │  │  Engine   │  │  Engine   │  │           │ │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘ │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐ │
│  │   Patch   │  │  Planner  │  │   Agent   │  │  Schema   │ │
│  │  Engine   │  │           │  │  Runtime  │  │  Doctor   │ │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘ │
├─────────────────────────────────────────────────────────────┤
│                    Safety Layer                              │
├─────────────────────────────────────────────────────────────┤
│                   Aksara Core (ORM, API, Admin)              │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Features

### 🔧 AI Tools

Functions that AI can call to interact with your app:

```python
from aksara.ai.tools import get_tools

tools = get_tools()
# Returns: create_record, update_record, query_records, 
#          run_migration, generate_code, etc.
```

See [Tools](tools.md) for the full list.

### 🔍 Context Engine

Automatically gathers relevant context for AI:

```python
from aksara.ai import ContextEngine

engine = ContextEngine()
context = await engine.gather(
    query="How do I add a tags field to Post?",
    include_models=True,
    include_migrations=True,
)
```

See [Context Engine](context-engine.md).

### 💬 Query Engine

Natural language to database queries:

```python
from aksara.ai import QueryEngine

engine = QueryEngine()
result = await engine.query(
    "Posts published this month with more than 10 comments"
)
```

See [Query Engine](query-engine.md).

### 📝 Codegen

Generate boilerplate code:

```python
from aksara.ai import Codegen

gen = Codegen()
code = await gen.model("BlogPost with title, content, author FK")
# Returns Model class definition
```

See [Codegen](codegen.md).

### 🔨 Patch Engine

Safe code modifications:

```python
from aksara.ai import PatchEngine

engine = PatchEngine()
patch = await engine.create_patch(
    file="models.py",
    instruction="Add 'is_featured' boolean field to Post"
)
await engine.apply(patch, dry_run=True)  # Preview changes
```

See [Patch Engine](patch-engine.md).

### 📋 Planner

Multi-step task planning:

```python
from aksara.ai import Planner

planner = Planner()
plan = await planner.create(
    "Add a tagging system to the blog"
)
# Returns: CreateModel(Tag), AddM2M(Post.tags), CreateViewSet, etc.
```

See [Planner](planner.md).

### 🤖 Agent Runtime

Execute AI agents:

```python
from aksara.ai import AgentRuntime

runtime = AgentRuntime()
result = await runtime.execute(
    "Review the User model and suggest improvements"
)
```

See [Agent Runtime](agent-runtime.md).

### 🏥 Schema Doctor

Analyze and fix schema issues:

```bash
aksara ai doctor
```

```
🔍 Analyzing schema...

⚠️ Issues Found:
  1. Post.author has no index (FK without index)
  2. User.email should be unique
  3. Comment.created_at has no default

💡 Suggested Fixes:
  aksara ai doctor --fix
```

See [Schema Doctor](schema-doctor.md).

---

## Use Cases

### Development Assistant

```bash
# "How do I..." questions
aksara ai ask "How do I add pagination to my viewset?"

# Generate code
aksara ai generate "UserProfile model linked to User"
```

### Data Exploration

```bash
# Query data naturally
aksara ai query "Users who registered but never made a purchase"

# Analyze patterns
aksara ai analyze "What's the most common user flow?"
```

### Code Review

```bash
# Review recent changes
aksara ai review

# Check for issues
aksara ai doctor
```

### Automated Tasks

```python
# In CI/CD
from aksara.ai import SchemaDoctor

doctor = SchemaDoctor()
issues = await doctor.analyze()
if issues.has_critical:
    raise Exception("Critical schema issues found")
```

---

## Safety Features

AI Mode includes multiple safety layers:

### 1. Confirmation Prompts

Destructive operations require confirmation:

```bash
aksara ai query "Delete all inactive users"

⚠️ This will delete 1,234 records.
Proceed? [y/N]
```

### 2. Dry Run Mode

Preview changes before applying:

```bash
aksara ai patch --dry-run "Add status field to Order"

Would modify:
  models.py: +3 lines
  migrations/0005_add_order_status.py: new file
```

### 3. Sandboxed Execution

Queries run in read-only transactions by default:

```python
from aksara.ai import QueryEngine

engine = QueryEngine(read_only=True)  # Default
```

### 4. Audit Logging

All AI operations are logged:

```python
AKSARA = {
    "AI_AUDIT_LOG": True,  # Log all AI operations
}
```

See [Safety](safety.md) for details.

---

## Configuration

```python
# settings.py
AKSARA = {
    # Enable AI Mode
    "AI_MODE": True,
    
    # Provider settings
    "AI_PROVIDER": "openai",
    "AI_MODEL": "gpt-4",
    "AI_API_KEY": os.getenv("OPENAI_API_KEY"),
    
    # Safety settings
    "AI_REQUIRE_CONFIRMATION": True,
    "AI_READ_ONLY_QUERIES": True,
    "AI_AUDIT_LOG": True,
    
    # Context settings
    "AI_CONTEXT_MAX_TOKENS": 8000,
    "AI_INCLUDE_MIGRATIONS": True,
}
```

See [Configuration](config.md) for all options.

---

## Requirements

- Python 3.10+
- OpenAI API key (or Anthropic, or local LLM)
- Aksara 0.4.0+

```bash
pip install aksara[ai]
```

---

## Related Documentation

- [Tools](tools.md) — AI-callable functions
- [Context Engine](context-engine.md) — Context gathering
- [Query Engine](query-engine.md) — Natural language queries
- [Codegen](codegen.md) — Code generation
- [Patch Engine](patch-engine.md) — Code modifications
- [Planner](planner.md) — Task planning
- [Agent Runtime](agent-runtime.md) — Agent execution
- [Schema Doctor](schema-doctor.md) — Schema analysis
- [Configuration](config.md) — AI Mode settings
- [Safety](safety.md) — Safety features
