# AI Mode Configuration

Settings and options for AI Mode features.

---

## Overview

AI Mode is configured through your `settings.py` file under the `AKSARA` dictionary.

```python
# settings.py
AKSARA = {
    "AI_MODE": True,
    "AI_PROVIDER": "openai",
    # ... more settings
}
```

---

## Core Settings

### Enable AI Mode

```python
AKSARA = {
    "AI_MODE": True,  # Enable AI features
}
```

### Provider Settings

```python
AKSARA = {
    # Provider selection
    "AI_PROVIDER": "openai",  # "openai", "anthropic", "local"
    
    # API credentials
    "AI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "AI_API_BASE": None,  # Custom API endpoint
    
    # Model selection
    "AI_MODEL": "gpt-4",  # or "gpt-3.5-turbo", "claude-3-opus", etc.
    
    # Generation parameters
    "AI_TEMPERATURE": 0.1,  # Lower = more deterministic
    "AI_MAX_TOKENS": 4000,
}
```

---

## Provider Configuration

### OpenAI

```python
AKSARA = {
    "AI_PROVIDER": "openai",
    "AI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "AI_MODEL": "gpt-4",
    
    # Optional
    "AI_ORGANIZATION": os.getenv("OPENAI_ORG"),
}
```

### Anthropic

```python
AKSARA = {
    "AI_PROVIDER": "anthropic",
    "AI_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
    "AI_MODEL": "claude-3-opus-20240229",
}
```

### Azure OpenAI

```python
AKSARA = {
    "AI_PROVIDER": "azure",
    "AI_API_KEY": os.getenv("AZURE_OPENAI_KEY"),
    "AI_API_BASE": "https://your-resource.openai.azure.com/",
    "AI_DEPLOYMENT": "your-deployment-name",
    "AI_API_VERSION": "2024-02-01",
}
```

### Local LLM (Ollama)

```python
AKSARA = {
    "AI_PROVIDER": "local",
    "AI_API_BASE": "http://localhost:11434",
    "AI_MODEL": "codellama",
}
```

### Custom Provider

```python
AKSARA = {
    "AI_PROVIDER": "custom",
    "AI_PROVIDER_CLASS": "myapp.ai.MyCustomProvider",
}
```

---

## Feature-Specific Settings

### Context Engine

```python
AKSARA = {
    "AI_CONTEXT": {
        # What to include
        "include_models": True,
        "include_migrations": True,
        "include_viewsets": True,
        "include_serializers": True,
        "include_tests": False,
        
        # Limits
        "max_tokens": 8000,
        "max_files": 50,
        "relevance_threshold": 0.5,
        
        # Caching
        "cache_enabled": True,
        "cache_ttl": 300,  # seconds
        
        # Privacy
        "mask_secrets": True,
        "exclude_patterns": ["**/secrets/**", "**/.env"],
    },
}
```

### Query Engine

```python
AKSARA = {
    "AI_QUERY_ENGINE": {
        # Safety
        "read_only": True,
        "allow_destructive": False,
        "require_confirmation_for_updates": True,
        
        # Limits
        "default_limit": 100,
        "max_limit": 1000,
        "timeout_seconds": 30,
        
        # Logging
        "log_queries": True,
        "log_sql": True,
    },
}
```

### Codegen

```python
AKSARA = {
    "AI_CODEGEN": {
        # Style
        "docstring_style": "google",  # "google", "numpy", "sphinx"
        "import_style": "absolute",   # "absolute", "relative"
        
        # Defaults
        "default_field_null": False,
        "include_timestamps": True,
        "include_uuid_pk": True,
        
        # Output locations
        "models_file": "models.py",
        "viewsets_file": "viewsets.py",
        "serializers_file": "serializers.py",
        "tests_dir": "tests/",
    },
}
```

### Patch Engine

```python
AKSARA = {
    "AI_PATCH_ENGINE": {
        # Validation
        "validate_syntax": True,
        "validate_imports": True,
        "run_tests_after": False,
        
        # Backups
        "create_backups": True,
        "backup_dir": ".aksara/backups",
        "max_backup_age_days": 30,
        
        # Conflicts
        "default_merge_strategy": "manual",  # "manual", "ours", "theirs"
        
        # Safety
        "require_dry_run_first": False,
        "max_changes_per_patch": 100,
    },
}
```

### Planner

```python
AKSARA = {
    "AI_PLANNER": {
        # Execution
        "rollback_on_failure": True,
        "max_steps": 20,
        "step_timeout_seconds": 60,
        
        # Validation
        "validate_each_step": True,
        "run_tests_after": False,
        
        # Interactive
        "default_interactive": False,
        "confirm_destructive": True,
    },
}
```

### Agent Runtime

```python
AKSARA = {
    "AI_AGENT_RUNTIME": {
        # Model
        "model": "gpt-4",  # e.g. "gpt-4o", "claude-3-5-sonnet-20241022", "llama3"
        "temperature": 0.1,
        
        # Tools
        "default_tools": ["query_records", "list_models", "describe_model"],
        "allow_write_tools": True,
        "allow_system_tools": False,
        
        # Limits
        "max_iterations": 20,
        "max_tool_calls": 50,
        "timeout_seconds": 300,
        "max_total_tokens": 100000,
        
        # Safety
        "require_approval_for": ["delete_record", "run_command"],
        "sandbox_mode": False,
        
        # Logging
        "log_actions": True,
        "log_reasoning": False,
    },
}
```

### Schema Doctor

```python
AKSARA = {
    "AI_DOCTOR": {
        # Analysis
        "include_models": None,  # None = all
        "exclude_models": ["LegacyModel"],
        "min_severity": "low",
        
        # Rules
        "disabled_rules": [],
        "custom_rules_module": "myapp.doctor_rules",
        
        # Conventions
        "table_naming": "snake_case",
        "require_timestamps": True,
        "require_uuid_pk": False,
        "max_string_length": 100,
        
        # Output
        "output_format": "console",
    },
}
```

### Tools

```python
AKSARA = {
    "AI_TOOLS": {
        # Enable/disable categories
        "data_tools": True,
        "schema_tools": True,
        "code_tools": True,
        "system_tools": True,
        
        # Tool-specific
        "query_records_max_limit": 100,
        "delete_record_require_confirmation": True,
        "run_migration_allowed": False,
    },
}
```

---

## Safety Settings

### Global Safety

```python
AKSARA = {
    "AI_SAFETY": {
        # Confirmations
        "require_confirmation": True,
        "confirmation_for": ["delete", "update", "migrate"],
        
        # Read-only mode
        "read_only_mode": False,
        
        # Audit logging
        "audit_log": True,
        "audit_log_file": "logs/ai_audit.log",
        
        # Rate limiting
        "rate_limit_requests": 100,
        "rate_limit_window": 3600,  # seconds
    },
}
```

### Per-Environment

```python
# settings/development.py
AKSARA = {
    "AI_MODE": True,
    "AI_SAFETY": {
        "require_confirmation": False,
        "read_only_mode": False,
    },
}

# settings/production.py
AKSARA = {
    "AI_MODE": True,
    "AI_SAFETY": {
        "require_confirmation": True,
        "read_only_mode": True,  # No writes in production
        "audit_log": True,
    },
}
```

---

## Environment Variables

All settings can be overridden via environment variables:

```bash
# Provider
export AKSARA_AI_PROVIDER=openai
export AKSARA_AI_API_KEY=<API_KEY>
export AKSARA_AI_MODEL=gpt-4

# Safety
export AKSARA_AI_READ_ONLY=true
export AKSARA_AI_REQUIRE_CONFIRMATION=true

# Limits
export AKSARA_AI_MAX_TOKENS=4000
export AKSARA_AI_TIMEOUT=30
```

Naming convention: `AKSARA_AI_` + setting name in SCREAMING_SNAKE_CASE.

---

## Configuration Validation

### Check Configuration

```bash
aksara ai config --check

✓ AI_PROVIDER: openai
✓ AI_API_KEY: configured (sk-****)
✓ AI_MODEL: gpt-4
⚠ AI_SAFETY.audit_log: disabled (recommended for production)
```

### Show Current Config

```bash
aksara ai config --show

AI Mode Configuration:
  Provider: openai
  Model: gpt-4
  Temperature: 0.1
  
Context Engine:
  Max Tokens: 8000
  Cache: enabled
  ...
```

---

## Programmatic Access

```python
from aksara.ai import get_ai_config

config = get_ai_config()

print(config.provider)
print(config.model)
print(config.context.max_tokens)
print(config.safety.require_confirmation)
```

### Override at Runtime

```python
from aksara.ai import QueryEngine

# Override settings for specific instance
engine = QueryEngine(
    model="gpt-3.5-turbo",  # Use cheaper model
    timeout=10,              # Shorter timeout
)
```

---

## Full Configuration Example

```python
# settings.py
import os

AKSARA = {
    # Core
    "DEBUG": os.getenv("DEBUG", "false").lower() == "true",
    "DATABASE_URL": os.getenv("DATABASE_URL"),
    
    # AI Mode
    "AI_MODE": True,
    "AI_PROVIDER": "openai",
    "AI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "AI_MODEL": "gpt-4",  # e.g. "gpt-4o", "claude-3-5-sonnet-20241022", "llama3"
    "AI_TEMPERATURE": 0.1,
    
    # Context Engine
    "AI_CONTEXT": {
        "include_models": True,
        "include_migrations": True,
        "max_tokens": 8000,
        "cache_enabled": True,
        "mask_secrets": True,
    },
    
    # Query Engine
    "AI_QUERY_ENGINE": {
        "read_only": True,
        "default_limit": 100,
        "timeout_seconds": 30,
    },
    
    # Codegen
    "AI_CODEGEN": {
        "docstring_style": "google",
        "include_timestamps": True,
    },
    
    # Patch Engine
    "AI_PATCH_ENGINE": {
        "create_backups": True,
        "validate_syntax": True,
    },
    
    # Agent Runtime
    "AI_AGENT_RUNTIME": {
        "max_iterations": 20,
        "require_approval_for": ["delete_record"],
    },
    
    # Safety
    "AI_SAFETY": {
        "require_confirmation": not os.getenv("DEBUG"),
        "audit_log": True,
    },
}
```

---

## Related Documentation

- [AI Mode Overview](index.md)
- [Safety](safety.md)
- [Settings Reference](../reference/settings-reference.md)
