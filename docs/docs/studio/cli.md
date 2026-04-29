# Studio CLI Commands

Command-line tools for testing and managing Aksara Studio integration.

## Commands Overview

| Command | Description |
|---------|-------------|
| `aksara studio handshake` | Test handshake locally |
| `aksara studio url` | Show Studio endpoint URLs |

---

## aksara studio handshake

Test the Studio handshake locally without starting a server.

### Usage

```bash
aksara studio handshake [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--app, -a` | `main:app` | App path (module:variable) |
| `--format, -f` | `pretty` | Output format: `json` or `pretty` |

### Examples

```bash
# Test with default app (main:app)
aksara studio handshake

# Test with custom app path
aksara studio handshake --app myapp:application

# Output as JSON for scripting
aksara studio handshake --format json

# Pipe to jq for processing
aksara studio handshake --format json | jq '.checksums'
```

### Sample Output (pretty)

```
  ⚡ Aksara Studio - Handshake Test

  ✓ Handshake successful!

  Project:
    Name:           My API
    Version:        1.0.0
    Aksara:         0.5.0
    Python:         3.11.5
    Environment:    development
    Debug:          True

  Database:
    Connected:      True
    Pool Size:      10
    Available:      8

  Capabilities:
    • read_schema
    • read_data
    • ai_tools
    • admin_access
    • debug_panels

  Checksums:
    Schema:         abc123def456789
    Migrations:     def456abc123789
    Settings:       789abc123def456
    Routes:         123def456abc789
```

### Sample Output (json)

```json
{
  "protocol_version": "1.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "project": {
    "name": "My API",
    "version": "1.0.0",
    "aksara_version": "0.5.0",
    "python_version": "3.11.5",
    "debug_mode": true,
    "environment": "development"
  },
  ...
}
```

---

## aksara studio url

Display the URLs for Studio integration endpoints.

### Usage

```bash
aksara studio url [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--host, -h` | `localhost` | Server host |
| `--port, -p` | `8000` | Server port |
| `--https/--no-https` | `--no-https` | Use HTTPS |

### Examples

```bash
# Show URLs for default localhost:8000
aksara studio url

# Custom port
aksara studio url --port 8080

# HTTPS URLs
aksara studio url --https

# Custom host and port
aksara studio url --host api.myapp.com --port 443 --https
```

### Sample Output

```
  ⚡ Aksara Studio - Endpoint URLs

  Studio Endpoints:
    Handshake:       http://localhost:8000/studio/handshake
    Context Summary: http://localhost:8000/studio/context/summary
    Health:          http://localhost:8000/studio/health

  AI Endpoints (full context):
    Full Context:    http://localhost:8000/ai/context/full
    Tools:           http://localhost:8000/ai/tools
    MCP Tools:       http://localhost:8000/ai/tools/mcp

  Tip: Use --https for production URLs
```

---

## Troubleshooting

### "Failed to load app"

```
✗ Failed to load app 'main:app': No module named 'main'
```

**Solution**: Make sure you're in your project directory and the app path is correct:

```bash
cd /path/to/your/project
aksara studio handshake --app myapp:app
```

### "Handshake failed"

If handshake fails, check:

1. **Import errors** - Your models may have import issues
2. **Configuration errors** - Check your Settings configuration
3. **Database issues** - Database URL may be invalid

Use `--format json` to see the full error:

```bash
aksara studio handshake --format json 2>&1
```

### Database Shows "Not Connected"

This is normal - the CLI handshake doesn't start the database connection pool. Use the HTTP endpoint for full database status:

```bash
# Start your app
aksara dev

# Test via HTTP
curl http://localhost:8000/studio/health | jq
```
