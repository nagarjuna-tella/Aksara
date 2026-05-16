# Running Your App

Start, debug, and deploy your Aksara application.

---

## Development Server

### Using the CLI

The recommended way to run your app during development:

```bash
aksara dev
```

`aksara dev` defaults to `main:app`, enables auto-reload, and shows a rich startup banner with the app, admin, Studio, and docs URLs. `aksara run dev` is an equivalent alias if you prefer to stay on the `run` command family.

Representative output:

```
         ████╗   █████╗  ██╗    ██╗ ███████╗  █████╗  ██████╗   █████╗ 
        ████╔╝  ██╔══██╗ ██║   ██╔╝ ██╔════╝ ██╔══██╗ ██╔══██╗ ██╔══██╗
       ████╔╝   ██║  ██║ ██║  ██╔╝  ██║      ██║  ██║ ██║  ██║ ██║  ██║
      ████╔╝    ██║  ██║ ██║ ██╔╝   ██║      ██║  ██║ ██║  ██║ ██║  ██║
     ████████╗  ███████║ █████╔╝    ███████╗ ███████║ ██████╔╝ ███████║
     ╚══████╔╝  ██╔══██║ ██╔═██╗    ╚════██║ ██╔══██║ ██╔══██╗ ██╔══██║
       ████╔╝   ██║  ██║ ██║  ██╗        ██║ ██║  ██║ ██║  ██║ ██║  ██║
      ████╔╝    ██║  ██║ ██║   ██╗       ██║ ██║  ██║ ██║  ██║ ██║  ██║
     ████╔╝     ██║  ██║ ██║    ██╗ ███████║ ██║  ██║ ██║  ██║ ██║  ██║
     ╚═══╝      ╚═╝  ╚═╝ ╚═╝    ╚═╝ ╚══════╝ ╚═╝  ╚═╝ ╚═╝  ╚═╝ ╚═╝  ╚═╝

    AI-native async backend  ·  Dev Server  ·  v0.5.46

    ● App       http://127.0.0.1:8000/
    ● Admin     http://127.0.0.1:8000/admin/
    ● Studio    http://127.0.0.1:8000/studio/ui
    ● Docs      http://127.0.0.1:8000/docs

    Env dev  ·  Reload enabled  ·  Log info
```

Options:

| Option | Description | Default |
|--------|-------------|---------|
| `--reload` / `--no-reload` | Auto-reload on code changes | On |
| `--host` | Bind address | `127.0.0.1` |
| `--port` | Port number | `8000` |
| `--log-level` | Log level | `info` |

Examples:

```bash
# Development (auto-reload enabled by default)
aksara dev

# Alias for the same development workflow
aksara run dev

# Custom port
aksara dev --port 3000

# Bind to all interfaces
aksara dev --host 0.0.0.0 --port 8000

# Custom app path (if not main:app)
aksara dev myproject.main:app
```

### Global Output Controls

All output-control flags are global, so they go before the command name:

```bash
aksara --quiet dev
aksara --plain dev
aksara --no-color dev
aksara --force-color dev
```

`--quiet` suppresses non-error Aksara UI output such as the banner, progress lines, and success summaries. It does not suppress Uvicorn's own logs. `--plain` disables Rich rendering and animation. `--no-color` keeps the same content without ANSI color, and `--force-color` is useful when a supported terminal is not detected automatically.

!!! note "Multi-worker testing"
    `aksara dev` always runs with a single worker. For production-like multi-worker testing, use `aksara run main:app --workers 4`.

### Using Uvicorn Directly

You can also use Uvicorn directly:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Using Python

```bash
python -m uvicorn main:app --reload
```

---

## Interactive Shell

Access the interactive Python shell with your app context:

```bash
aksara shell
```

The shell automatically:

- Imports your models
- Connects to the database
- Provides an async-ready environment

Example session:

```python
>>> # Models are auto-imported
>>> users = await User.objects.all()
>>> len(users)
5

>>> # Create new records
>>> task = await Task.objects.create(
...     title="Review code",
...     priority=2
... )
>>> task.id
UUID('...')

>>> # Query with filters
>>> pending = await Task.objects.filter(status="pending")
>>> for t in pending:
...     print(f"{t.title}: {t.priority}")
```

---

## Debug Mode

Enable debug mode for development:

### Via Environment

```bash
AKSARA_DEBUG=true aksara dev
```

### Via Settings

```python
from aksara import configure

configure(debug=True)
```

### Via Constructor

```python
app = Aksara(
    database_url="...",
    debug=True,
)
```

Debug mode enables:

- **Detailed error pages** with stack traces
- **AI debugging suggestions** for common errors
- **Request/response logging**
- **Auto-reload** (when using `--reload`)

!!! danger "Never Use Debug Mode in Production"
    Debug mode exposes sensitive information. Always set `AKSARA_DEBUG=false` in production.

---

## Production Deployment

### Using Gunicorn + Uvicorn Workers

The recommended production setup:

```bash
pip install gunicorn uvicorn[standard]
```

```bash
gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

### Using Docker

Create a `Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run with Gunicorn
CMD ["gunicorn", "main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000"]
```

Create a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/myapp
      - AKSARA_DEBUG=false
      - AKSARA_LOG_JSON=true
    depends_on:
      - db
  
  db:
    image: postgres:15
    environment:
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=myapp
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

Run with:

```bash
docker-compose up -d
```

### Worker Count

Calculate workers based on CPU cores:

```
workers = (2 × CPU cores) + 1
```

| CPU Cores | Recommended Workers |
|-----------|---------------------|
| 1 | 2-3 |
| 2 | 4-5 |
| 4 | 8-9 |
| 8 | 16-17 |

### Environment Variables for Production

```bash
# Required
DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require

# Recommended
AKSARA_DEBUG=false
AKSARA_LOG_LEVEL=INFO
AKSARA_LOG_JSON=true
AKSARA_POOL_MIN_SIZE=10
AKSARA_POOL_MAX_SIZE=50
```

---

## Health Checks

Add health check endpoints for container orchestration:

```python
from aksara.db import Database

@app.get("/health")
async def health():
    """Basic health check."""
    return {"status": "ok"}

@app.get("/health/ready")
async def readiness():
    """Readiness check with database verification."""
    try:
        db = Database.get_instance()
        await db.fetchval("SELECT 1")
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}, 503
```

---

## Process Management

### Using systemd

Create `/etc/systemd/system/aksara-app.service`:

```ini
[Unit]
Description=Aksara Application
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/myapp
Environment="DATABASE_URL=postgresql://..."
Environment="AKSARA_DEBUG=false"
ExecStart=/opt/myapp/venv/bin/gunicorn main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind unix:/run/aksara/app.sock
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable aksara-app
sudo systemctl start aksara-app
```

### Using Supervisor

Create `/etc/supervisor/conf.d/aksara.conf`:

```ini
[program:aksara]
command=/opt/myapp/venv/bin/gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
directory=/opt/myapp
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/aksara/app.log
environment=DATABASE_URL="postgresql://...",AKSARA_DEBUG="false"
```

---

## Reverse Proxy

### Nginx Configuration

```nginx
upstream aksara {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name example.com;
    
    location / {
        proxy_pass http://aksara;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;
    }
    
    location /static {
        alias /opt/myapp/static;
        expires 30d;
    }
}
```

### Caddy Configuration

```
example.com {
    reverse_proxy localhost:8000
}
```

---

## Logging

### Development Logging

```python
configure(
    log_level="DEBUG",
    log_requests=True,
    log_json=False,  # Human-readable
)
```

### Production Logging

```python
configure(
    log_level="INFO",
    log_requests=True,
    log_json=True,  # Machine-readable for log aggregation
)
```

### Log Output

Development:
```
INFO:     127.0.0.1:52340 - "GET /api/tasks HTTP/1.1" 200
DEBUG:    Query: SELECT * FROM tasks WHERE status = $1
```

Production (JSON):
```json
{"timestamp":"2026-01-26T10:00:00Z","level":"INFO","method":"GET","path":"/api/tasks","status":200,"duration_ms":15,"request_id":"abc-123"}
```

---

## Performance Tuning

### Connection Pool

```python
configure(
    pool_min_size=10,   # Keep connections ready
    pool_max_size=50,   # Limit maximum connections
)
```

### Database Indexes

Ensure your frequently-queried fields are indexed:

```python
class Task(Model):
    status = fields.String(max_length=20, db_index=True)
    created_at = fields.DateTime(auto_now_add=True, db_index=True)
```

### Query Optimization

Use `select_related` for foreign keys:

```python
# Efficient: single query with join
posts = await Post.objects.select_related("author").all()

# Inefficient: N+1 queries
posts = await Post.objects.all()
for post in posts:
    author = await post.author  # Separate query each time
```

---

## Monitoring

### Prometheus Metrics (Optional)

```python
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)
```

### OpenTelemetry (Optional)

```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

FastAPIInstrumentor.instrument_app(app)
```

---

## Related Documentation

- [Settings](settings.md) — Configuration options
- [Middleware](../middleware/index.md) — Request processing
- [Debugging](../debugging/index.md) — Runtime inspection and troubleshooting
