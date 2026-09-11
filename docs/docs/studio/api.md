# Studio API Reference

!!! warning "Experimental development surface"
    This analysis, provider or Studio surface is outside the stable backend
    contract. Review its outputs and application integration before use. It is
    not required for REST, synchronous MCP or Durable Operations. See
    [stability labels](../concepts/stability.md).

This page documents the HTTP API endpoints for Aksara Studio integration.

## Endpoints Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/studio/handshake` | GET | Complete project handshake |
| `/studio/context/summary` | GET | Lightweight schema summary |
| `/studio/health` | GET | Health check with DB status |
| `/studio/migrations/summary` | GET | Per-app migration statistics (v0.5.1) |
| `/studio/schema/handshake` | GET | JSON Schema for handshake model (v0.5.1) |

---

## Security (v0.5.1)

All Studio endpoints validate the incoming `Origin` header against `studio_allowed_origins` setting.

- **Allowed origin**: Request proceeds normally
- **No origin header**: Request allowed (same-origin, CLI, server-to-server)
- **Disallowed origin**: 403 Forbidden response

```python
# In aksara.conf
settings.studio_allowed_origins = [
    "https://studio.aksara.dev",
    "http://localhost:3000",
]
# Use ["*"] to allow all origins (development only!)
```

---

## GET /studio/handshake

Complete handshake endpoint for Studio IDE. Returns everything Studio needs to understand your project.

### Response

```json
{
  "protocol_version": "1.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "project": {
    "name": "My App",
    "version": "1.0.0",
    "aksara_version": "0.7.0",
    "python_version": "3.11.5",
    "debug_mode": true,
    "environment": "development"
  },
  "database": {
    "connected": true,
    "dialect": "postgresql",
    "pool_size": 10,
    "pool_available": 8,
    "latency_ms": null,
    "last_error": null
  },
  "capabilities": [
    "read_schema",
    "read_data",
    "write_data",
    "read_migrations",
    "apply_migrations",
    "ai_tools",
    "ai_query",
    "ai_codegen",
    "ai_patch",
    "ai_planner",
    "admin_access",
    "debug_panels"
  ],
  "checksums": {
    "schema_checksum": "abc123def456789",
    "migrations_checksum": "def456abc123789",
    "settings_checksum": "789abc123def456",
    "routes_checksum": "123def456abc789"
  },
  "endpoints": {
    "context_full": "/ai/context/full",
    "context_summary": "/studio/context/summary",
    "health": "/studio/health",
    "tools": "/ai/tools",
    "tools_mcp": "/ai/tools/mcp",
    "query_execute": "/ai/query/execute",
    "codegen_preview": "/ai/codegen/preview",
    "patch_preview": "/ai/patch/preview",
    "patch_apply": "/ai/patch/apply",
    "plan_preview": "/ai/plan/preview",
    "plan_apply": "/ai/plan/apply",
    "schema_health": "/ai/schema/health"
  },
  "metadata": {}
}
```

### Response Fields

#### project

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Project/app name |
| `version` | string | Project version |
| `aksara_version` | string | Aksara framework version |
| `python_version` | string | Python runtime version |
| `debug_mode` | boolean | Whether app is in debug mode |
| `environment` | string | Environment (development, staging, production) |

#### database

| Field | Type | Description |
|-------|------|-------------|
| `connected` | boolean | Whether database is connected |
| `dialect` | string | Database dialect (postgresql) |
| `pool_size` | integer | Current pool size |
| `pool_available` | integer | Available connections |
| `latency_ms` | float | Last query latency (if measured) |
| `last_error` | string | Last error message (if any) |

#### capabilities

Available capabilities that Studio can use:

| Capability | Description |
|------------|-------------|
| `read_schema` | Can read model schema |
| `read_data` | Can read database records |
| `write_data` | Can write database records |
| `read_migrations` | Can read migration files |
| `apply_migrations` | Can apply migrations |
| `ai_tools` | AI tools endpoint available |
| `ai_query` | AI query execution available |
| `ai_codegen` | AI code generation available |
| `ai_patch` | AI patch operations available |
| `ai_planner` | AI planner available |
| `admin_access` | Admin interface available |
| `debug_panels` | Debug panels available |

#### checksums

Checksums are used for cache invalidation. Studio compares these with cached values to determine if it needs to refresh data.

| Field | Type | Description |
|-------|------|-------------|
| `schema_checksum` | string | SHA-256 of model schema |
| `migrations_checksum` | string | SHA-256 of migration files |
| `settings_checksum` | string | SHA-256 of settings |
| `routes_checksum` | string | SHA-256 of routes |

---

## GET /studio/context/summary

Lightweight context summary without full schema. Use this for quick status checks.

### Response

```json
{
  "app_count": 3,
  "model_count": 5,
  "viewset_count": 3,
  "route_count": 25,
  "ai_tool_count": 15,
  "migration_count": 10,
  "pending_migrations": 0,
  "database_status": {
    "connected": true,
    "dialect": "postgresql",
    "pool_size": 10,
    "pool_available": 8,
    "latency_ms": null,
    "last_error": null
  },
  "migration_status": {
    "total": 10,
    "applied": 10,
    "pending": 0,
    "has_conflicts": false,
    "last_applied": "0010_add_tags"
  },
  "models": [
    {
      "name": "User",
      "table_name": "users",
      "field_count": 6,
      "has_relations": true
    },
    {
      "name": "Post",
      "table_name": "posts",
      "field_count": 4,
      "has_relations": true
    }
  ],
  "checksums": {
    "schema_checksum": "abc123def456789",
    "migrations_checksum": "def456abc123789",
    "settings_checksum": "789abc123def456",
    "routes_checksum": "123def456abc789"
  }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `app_count` | integer | Number of installed apps (v0.5.1) |
| `model_count` | integer | Total registered models |
| `viewset_count` | integer | Total registered viewsets |
| `route_count` | integer | Total API routes |
| `ai_tool_count` | integer | Total AI tools |
| `migration_count` | integer | Total migrations |
| `pending_migrations` | integer | Unapplied migrations |
| `database_status` | object | Live database status (v0.5.1) |
| `migration_status` | object | Migration health overview (v0.5.1) |
| `models` | array | List of model summaries |
| `checksums` | object | Checksums for caching |

---

## GET /studio/health

Simple health check endpoint.

### Response

```json
{
  "status": "healthy",
  "aksara_version": "0.7.0",
  "database": {
    "connected": true,
    "dialect": "postgresql",
    "pool_size": 10,
    "pool_available": 8,
    "latency_ms": null,
    "last_error": null
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Status Values

| Status | Description |
|--------|-------------|
| `healthy` | Database connected, all systems go |
| `degraded` | Database not connected or other issues |

---

## GET /studio/migrations/summary (v0.5.1)

Detailed migration statistics with per-app breakdown and conflict detection.

### Response

```json
{
  "total_migrations": 15,
  "applied_migrations": 12,
  "pending_migrations": 3,
  "apps": [
    {
      "app_label": "auth",
      "total": 5,
      "applied": 5,
      "pending": 0,
      "has_conflicts": false,
      "head_migrations": ["0005_add_last_login"]
    },
    {
      "app_label": "blog",
      "total": 10,
      "applied": 7,
      "pending": 3,
      "has_conflicts": false,
      "head_migrations": ["0010_add_tags"]
    }
  ],
  "conflicts": [],
  "migrations_checksum": "abc123def456789",
  "last_applied": "0005_add_last_login"
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `total_migrations` | integer | Total migrations across all apps |
| `applied_migrations` | integer | Number of applied migrations |
| `pending_migrations` | integer | Number of pending migrations |
| `apps` | array | Per-app migration summaries |
| `conflicts` | array | Detected migration conflicts |
| `migrations_checksum` | string | Checksum for caching |
| `last_applied` | string | Name of last applied migration |

### Conflict Detection

When migrations have branched (e.g., two developers created separate migrations from the same parent), the `conflicts` array will contain details:

```json
{
  "conflicts": [
    {
      "app_label": "blog",
      "heads": ["0008_feature_a", "0008_feature_b"],
      "message": "App 'blog' has 2 conflicting head migrations that need to be merged."
    }
  ]
}
```

---

## GET /studio/schema/handshake (v0.5.1)

Returns the JSON Schema for the `StudioHandshake` model. Useful for:

- TypeScript type generation
- API documentation
- Client-side validation

### Response

```json
{
  "$defs": {
    "StudioDatabaseStatus": {
      "properties": {
        "connected": { "type": "boolean" },
        "dialect": { "type": "string" }
      }
    }
  },
  "properties": {
    "protocol_version": {
      "default": "1.0",
      "description": "Studio protocol version",
      "type": "string"
    },
    "project": { "$ref": "#/$defs/StudioProjectInfo" },
    "database": { "$ref": "#/$defs/StudioDatabaseStatus" }
  },
  "required": ["project", "database", "capabilities", "checksums"],
  "title": "StudioHandshake",
  "type": "object"
}
```

### Usage Example (TypeScript)

```typescript
// Generate types from JSON Schema
import { compile } from 'json-schema-to-typescript';

const response = await fetch('/studio/schema/handshake');
const schema = await response.json();
const types = await compile(schema, 'StudioHandshake');
```

---

## Using with curl

### Test Handshake

```bash
curl http://localhost:8000/studio/handshake | jq
```

### Check Health

```bash
curl http://localhost:8000/studio/health | jq
```

### Get Summary

```bash
curl http://localhost:8000/studio/context/summary | jq
```

### Get Migration Summary (v0.5.1)

```bash
curl http://localhost:8000/studio/migrations/summary | jq
```

### Get JSON Schema (v0.5.1)

```bash
curl http://localhost:8000/studio/schema/handshake | jq
```

---

## Full Context

For the complete application context including full schema, use the AI context endpoint:

```bash
curl http://localhost:8000/ai/context/full | jq
```

This returns the full `AiFullContext` which includes:

- Complete model definitions with all fields
- ViewSet definitions with all actions
- Route information
- Migration history
- Admin configuration
- AI tool registry

See [AI Context Documentation](../ai-mode/context-engine.md) for details.
