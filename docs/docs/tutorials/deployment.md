# Tutorial: Deployment

Deploy your Aksara application to production.

---

## What You'll Learn

- Docker configuration
- Environment setup
- Database migrations in production
- Security hardening
- Monitoring basics

**Time:** ~20 minutes

---

## Deployment Checklist

Before deploying, ensure:

- [ ] `DEBUG = False`
- [ ] Secret key is secure and from environment
- [ ] Database URL is configured
- [ ] Allowed hosts is set
- [ ] CORS is configured
- [ ] SSL/TLS is enabled
- [ ] Static files are collected

---

## Step 1: Production Settings

### Create Production Settings

```python
# settings/production.py
import os

AKSARA = {
    # Core
    "DEBUG": False,
    "SECRET_KEY": os.environ["SECRET_KEY"],
    
    # Database
    "DATABASE_URL": os.environ["DATABASE_URL"],
    
    # Security
    "ALLOWED_HOSTS": os.environ.get("ALLOWED_HOSTS", "").split(","),
    "CORS_ORIGINS": os.environ.get("CORS_ORIGINS", "").split(","),
    
    # Apps
    "INSTALLED_APPS": ["myapp"],
    
    # AI (optional)
    "AI_MODE": os.environ.get("AI_MODE", "false").lower() == "true",
    "AI_API_KEY": os.environ.get("AI_API_KEY"),
    "AI_SAFETY": {
        "read_only_mode": True,  # Safe in production
        "audit_log": True,
    },
}
```

### Environment Variables

Create a `.env.example`:

```bash
# .env.example
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://user:pass@host:5432/dbname
ALLOWED_HOSTS=example.com,www.example.com
CORS_ORIGINS=https://example.com

# Optional
AI_MODE=true
AI_API_KEY=sk-...
```

---

## Step 2: Docker Configuration

### Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN aksara collectstatic --no-input

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Run with uvicorn
CMD ["uvicorn", "myapp.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/myapp
      - ALLOWED_HOSTS=localhost,127.0.0.1
    depends_on:
      - db
    command: >
      sh -c "aksara migrate && uvicorn myapp.app:app --host 0.0.0.0 --port 8000"

  db:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=myapp
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres

volumes:
  postgres_data:
```

### Production Compose

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  web:
    build: .
    expose:
      - "8000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=${DATABASE_URL}
      - ALLOWED_HOSTS=${ALLOWED_HOSTS}
    command: uvicorn myapp.app:app --host 0.0.0.0 --port 8000 --workers 4
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      - static_files:/app/static:ro
    depends_on:
      - web
    restart: unless-stopped

volumes:
  static_files:
```

---

## Step 3: Nginx Configuration

```nginx
# nginx.conf
events {
    worker_connections 1024;
}

http {
    upstream aksara {
        server web:8000;
    }

    server {
        listen 80;
        server_name example.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name example.com;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;

        location /static/ {
            alias /app/static/;
            expires 30d;
            add_header Cache-Control "public, immutable";
        }

        location / {
            proxy_pass http://aksara;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

---

## Step 4: Database Migrations

### Migrate on Deploy

```bash
# Run migrations before starting the app
aksara migrate --no-input
```

### Migration Script

```bash
#!/bin/bash
# deploy.sh

set -e

echo "Running migrations..."
aksara migrate --no-input

echo "Collecting static files..."
aksara collectstatic --no-input

echo "Starting server..."
exec uvicorn myapp.app:app --host 0.0.0.0 --port 8000 --workers 4
```

### Check Migrations in CI

```yaml
# .github/workflows/deploy.yml
- name: Check migrations
  run: |
    aksara makemigrations --check --dry-run
```

---

## Step 5: Security Hardening

### Security Settings

```python
# settings/production.py
AKSARA = {
    # ... other settings ...
    
    # Security
    "SECURITY": {
        "SECURE_SSL_REDIRECT": True,
        "SECURE_HSTS_SECONDS": 31536000,
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": True,
        "SECURE_CONTENT_TYPE_NOSNIFF": True,
        "SECURE_BROWSER_XSS_FILTER": True,
        "X_FRAME_OPTIONS": "DENY",
    },
    
    # CORS
    "CORS": {
        "ALLOW_ORIGINS": os.environ.get("CORS_ORIGINS", "").split(","),
        "ALLOW_METHODS": ["GET", "POST", "PUT", "DELETE"],
        "ALLOW_HEADERS": ["Authorization", "Content-Type"],
        "ALLOW_CREDENTIALS": True,
    },
}
```

### Generate Secret Key

```python
import secrets
print(secrets.token_urlsafe(50))
```

Or:

```bash
openssl rand -base64 50
```

---

## Step 6: Health Checks

### Health Endpoint

```python
# app/health.py
from aksara.api import ViewSet, action

class HealthViewSet(ViewSet):
    @action(detail=False, methods=["get"])
    async def live(self, request):
        """Liveness probe."""
        return {"status": "ok"}
    
    @action(detail=False, methods=["get"])
    async def ready(self, request):
        """Readiness probe."""
        # Check database connection
        try:
            from myapp.models import User
            await User.objects.count()
            db_status = "ok"
        except Exception as e:
            db_status = f"error: {e}"
        
        return {
            "status": "ok" if db_status == "ok" else "degraded",
            "database": db_status,
        }
```

### Docker Healthcheck

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/live/ || exit 1
```

### Kubernetes Probes

```yaml
# kubernetes/deployment.yaml
livenessProbe:
  httpGet:
    path: /health/live/
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /health/ready/
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

---

## Step 7: Logging

### Configure Logging

```python
# settings/production.py
import logging

AKSARA = {
    # ... other settings ...
    
    "LOGGING": {
        "level": "INFO",
        "format": "json",  # JSON for log aggregation
        "handlers": ["console", "file"],
        "file_path": "/var/log/myapp/app.log",
    },
}

# Python logging config
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
```

### Request Logging

```python
# Add request logging middleware
from aksara.middleware import LoggingMiddleware

app.add_middleware(
    LoggingMiddleware,
    log_request_body=False,  # Don't log sensitive data
    log_response_body=False,
    mask_headers=["Authorization", "Cookie"],
)
```

---

## Step 8: Monitoring

### Metrics Endpoint

```python
# app/metrics.py
from aksara.api import ViewSet, action

class MetricsViewSet(ViewSet):
    @action(detail=False, methods=["get"])
    async def prometheus(self, request):
        """Prometheus metrics."""
        from myapp.models import User, Post
        
        user_count = await User.objects.count()
        post_count = await Post.objects.count()
        
        metrics = f"""
# HELP users_total Total number of users
# TYPE users_total gauge
users_total {user_count}

# HELP posts_total Total number of posts
# TYPE posts_total gauge
posts_total {post_count}
"""
        return Response(metrics, media_type="text/plain")
```

### Sentry Integration

```python
# settings/production.py
import sentry_sdk

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    environment="production",
    traces_sample_rate=0.1,
)
```

---

## Deployment Platforms

### Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

`railway.toml`:
```toml
[build]
builder = "dockerfile"

[deploy]
healthcheckPath = "/health/live/"
healthcheckTimeout = 30
```

### Fly.io

```bash
# Install Fly CLI
curl -L https://fly.io/install.sh | sh

# Launch
fly launch
fly deploy
```

`fly.toml`:
```toml
[build]
  dockerfile = "Dockerfile"

[http_service]
  internal_port = 8000
  force_https = true

[[services.http_checks]]
  interval = "10s"
  timeout = "2s"
  path = "/health/live/"
```

### AWS ECS

See AWS documentation for ECS deployment with Fargate.

### Kubernetes

```yaml
# kubernetes/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aksara-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: aksara
  template:
    metadata:
      labels:
        app: aksara
    spec:
      containers:
      - name: web
        image: myregistry/myapp:latest
        ports:
        - containerPort: 8000
        envFrom:
        - secretRef:
            name: aksara-secrets
        resources:
          requests:
            memory: "256Mi"
            cpu: "200m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

---

## Quick Deploy Script

```bash
#!/bin/bash
# deploy.sh

set -e

echo "🚀 Deploying to production..."

# Build
docker build -t myapp:latest .

# Tag
docker tag myapp:latest myregistry/myapp:$(git rev-parse --short HEAD)
docker push myregistry/myapp:$(git rev-parse --short HEAD)

# Deploy
kubectl set image deployment/aksara-app web=myregistry/myapp:$(git rev-parse --short HEAD)

echo "✅ Deployment complete!"
```

---

## Rollback

```bash
# Docker Compose
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d --build

# Kubernetes
kubectl rollout undo deployment/aksara-app

# Database (if needed)
aksara migrate myapp 0005  # Roll back to migration 0005
```

---

## Related Documentation

- [Settings Reference](../reference/settings-reference.md)
- [Middleware](../middleware/index.md)
- [Security](../ai-mode/safety.md)
