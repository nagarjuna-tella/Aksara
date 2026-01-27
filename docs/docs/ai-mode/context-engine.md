# Context Engine

Gather relevant code context for AI operations.

---

## Overview

The Context Engine analyzes your codebase to provide AI with relevant information:

- **Model definitions** — Fields, relations, constraints
- **Existing code** — ViewSets, serializers, tests
- **Migrations** — Schema history and changes
- **Documentation** — Docstrings and comments

```python
from aksara.ai import ContextEngine

engine = ContextEngine()
context = await engine.gather("Add a featured flag to Post model")
```

---

## Quick Start

### Basic Context Gathering

```python
from aksara.ai import ContextEngine

engine = ContextEngine()

# Gather context for a task
context = await engine.gather(
    query="How do I filter posts by author?"
)

print(context.models)      # Relevant models
print(context.code)        # Related code snippets
print(context.summary)     # Human-readable summary
```

### Include Specific Sources

```python
context = await engine.gather(
    query="Add tags to Post model",
    include_models=True,      # Model definitions
    include_migrations=True,  # Migration history
    include_viewsets=True,    # ViewSet code
    include_tests=True,       # Related tests
)
```

---

## Context Sources

### Models

```python
context = await engine.gather(
    query="User model fields",
    include_models=True,
)

print(context.models)
# [
#     {
#         "name": "User",
#         "file": "models.py",
#         "code": "class User(Model):\n    email = ...",
#         "fields": [...],
#         "relations": [...],
#     }
# ]
```

### Migrations

```python
context = await engine.gather(
    query="How has the User model changed?",
    include_migrations=True,
)

print(context.migrations)
# [
#     {
#         "name": "0001_initial",
#         "operations": ["CreateModel(User)"],
#     },
#     {
#         "name": "0003_add_user_phone",
#         "operations": ["AddField(User, phone)"],
#     }
# ]
```

### ViewSets and API

```python
context = await engine.gather(
    query="User API endpoints",
    include_viewsets=True,
)

print(context.viewsets)
# [
#     {
#         "name": "UserViewSet",
#         "file": "viewsets.py",
#         "model": "User",
#         "actions": ["list", "create", "retrieve", "update", "delete"],
#     }
# ]
```

### Tests

```python
context = await engine.gather(
    query="How is User tested?",
    include_tests=True,
)

print(context.tests)
# [
#     {
#         "name": "test_user.py",
#         "test_cases": ["test_create_user", "test_email_validation"],
#     }
# ]
```

---

## Relevance Filtering

### Automatic Relevance

The engine automatically filters to relevant content:

```python
# Query about Post model
context = await engine.gather("Add slug to Post")

# Returns:
# - Post model definition ✓
# - PostSerializer ✓
# - PostViewSet ✓
# - User model ✗ (not directly relevant)
```

### Manual Filtering

```python
context = await engine.gather(
    query="Post model",
    model_names=["Post", "Tag"],  # Only these models
    file_patterns=["**/blog/**"],  # Only blog app
)
```

### Relevance Threshold

```python
engine = ContextEngine(
    relevance_threshold=0.7,  # Higher = stricter filtering
)
```

---

## Token Management

### Token Limits

```python
engine = ContextEngine(
    max_tokens=8000,  # Limit context size
)

context = await engine.gather(query)
print(f"Used {context.token_count} tokens")
```

### Prioritization

When context exceeds limits, items are prioritized:

1. **Directly referenced** models/files
2. **Related** models (FKs, M2M)
3. **Similar** code patterns
4. **Historical** context (migrations)

### Chunking

For large codebases:

```python
context = await engine.gather(
    query="Refactor all models",
    chunked=True,  # Return multiple chunks
)

for chunk in context.chunks:
    # Process each chunk with AI
    result = await ai.process(chunk)
```

---

## Context Format

### For LLMs

```python
# Get LLM-ready format
prompt_context = context.to_prompt()

messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": f"{prompt_context}\n\nUser: {query}"},
]
```

### Structured Format

```python
# Get structured data
data = context.to_dict()

print(data)
# {
#     "models": [...],
#     "viewsets": [...],
#     "migrations": [...],
#     "summary": "...",
#     "token_count": 3500,
# }
```

### Markdown Format

```python
# Get markdown for documentation
markdown = context.to_markdown()
print(markdown)
# ## Models
# 
# ### Post
# ```python
# class Post(Model):
#     ...
# ```
```

---

## Caching

### Enable Caching

```python
engine = ContextEngine(
    cache_enabled=True,
    cache_ttl=300,  # 5 minutes
)
```

### Cache Invalidation

```python
# Clear all cache
engine.clear_cache()

# Clear specific model cache
engine.invalidate_model("Post")
```

### File Watching

```python
engine = ContextEngine(
    watch_files=True,  # Auto-invalidate on file changes
)
```

---

## Integration with AI

### With Query Engine

```python
from aksara.ai import ContextEngine, QueryEngine

context_engine = ContextEngine()
query_engine = QueryEngine()

# Context informs query generation
context = await context_engine.gather("Posts by active users")
result = await query_engine.query(
    "Posts by active users",
    context=context,
)
```

### With Codegen

```python
from aksara.ai import ContextEngine, Codegen

context_engine = ContextEngine()
codegen = Codegen()

# Context ensures generated code matches patterns
context = await context_engine.gather("Create a Comment model")
code = await codegen.model(
    "Comment with text, author FK, post FK",
    context=context,
)
```

### With Agent Runtime

```python
from aksara.ai import AgentRuntime

runtime = AgentRuntime()

# Agent uses context automatically
result = await runtime.execute(
    "Add a tagging system to posts",
    context_options={
        "include_models": True,
        "include_migrations": True,
    }
)
```

---

## Custom Context Sources

### Register Source

```python
from aksara.ai.context import register_source, ContextSource

@register_source
class EnvVarsSource(ContextSource):
    """Include environment variables in context."""
    
    name = "env_vars"
    
    async def gather(self, query: str) -> dict:
        return {
            "env_vars": {
                "DEBUG": os.getenv("DEBUG"),
                "DATABASE_URL": "[MASKED]",
            }
        }
```

### Use Custom Source

```python
context = await engine.gather(
    query="Database configuration",
    include_env_vars=True,  # Include custom source
)
```

---

## Configuration

```python
# settings.py
AKSARA = {
    "AI_CONTEXT": {
        # Default includes
        "include_models": True,
        "include_migrations": True,
        "include_viewsets": True,
        "include_serializers": True,
        "include_tests": False,  # Off by default
        
        # Limits
        "max_tokens": 8000,
        "max_files": 50,
        "relevance_threshold": 0.5,
        
        # Caching
        "cache_enabled": True,
        "cache_ttl": 300,
        
        # Privacy
        "mask_secrets": True,
        "exclude_patterns": ["**/secrets/**"],
    },
}
```

---

## Best Practices

### 1. Be Specific

```python
# Less effective
context = await engine.gather("models")

# More effective
context = await engine.gather("Post model with author relation")
```

### 2. Include Related Context

```python
# For model changes, include migrations
context = await engine.gather(
    "Add field to User",
    include_models=True,
    include_migrations=True,
)
```

### 3. Respect Token Limits

```python
# Start small, expand if needed
context = await engine.gather(query, max_tokens=4000)
if not context.has_relevant_content:
    context = await engine.gather(query, max_tokens=8000)
```

---

## Related Documentation

- [AI Mode Overview](index.md)
- [Query Engine](query-engine.md)
- [Codegen](codegen.md)
- [Configuration](config.md)
