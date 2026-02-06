# Tutorial: Deploying to Production

Deploy your Aksara application so anyone can use it.

---

## What You'll Learn

- How to prepare your app for production
- How to configure environment variables
- How to use Docker for deployment
- How to run database migrations safely
- How to set up monitoring

**Time:** ~20 minutes

**Difficulty:** Beginner

---

## What is Deployment?

**Development** = Running on your computer for testing  
**Production** = Running on a server for real users

When you deploy, you need to:

1. **Turn off debug mode** — Hide error details from users
2. **Secure your secrets** — Keep passwords out of code
3. **Configure the database** — Use a production database
4. **Set up HTTPS** — Encrypt all traffic

---

## Pre-Deployment Checklist

Before deploying, verify:

| Item | Why It Matters |
|------|----------------|
| ☐ `DEBUG = False` | Debug mode shows sensitive info |
| ☐ Secret key is random | Predictable keys can be hacked |
| ☐ Database URL is set | Don't hardcode credentials |
| ☐ Allowed hosts configured | Prevents host header attacks |
| ☐ HTTPS enabled | Encrypts all traffic |

---

## Step 1: Create Production Settings

### Separate Settings File

Create `settings/production.py`:

```python
# settings/production.py
import os

AKSARA = {
    # NEVER set DEBUG = True in production
    "DEBUG": False,
    
    # Get secret key from environment (not hardcoded!)
    "SECRET_KEY": os.environ["SECRET_KEY"],
    
    # Database URL from environment
    "DATABASE_URL": os.environ["DATABASE_URL"],
    
    # Which domains can access your API
    "ALLOWED_HOSTS": os.environ.get("ALLOWED_HOSTS", "").split(","),
    
    # Which origins can make browser requests
    "CORS_ORIGINS": os.environ.get("CORS_ORIGINS", "").split(","),
    
    # Your apps
    "INSTALLED_APPS": ["myapp"],
}
```

**Why environment variables?**

Environment variables keep secrets out of your code:

```bash
# ❌ BAD: Secret in code (gets committed to git!)
SECRET_KEY = "my-super-secret-key"

# ✅ GOOD: Secret from environment
SECRET_KEY = os.environ["SECRET_KEY"]
```

### Generate a Secret Key

```bash
# Generate a secure random key
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

---

## Step 2: Create Environment File

Create `.env.example` (commit this to git as a template):

```bash
# .env.example - Copy to .env and fill in values
# NEVER commit .env to git!

# Required
SECRET_KEY=generate-a-random-key-here
DATABASE_URL=postgresql://user:password@host:5432/dbname

# Security
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CORS_ORIGINS=https://yourdomain.com

# Optional: AI features
AI_MODE=false
AI_API_KEY=
```

Create actual `.env` file (don't commit this!):

```bash
# .env
SECRET_KEY=your-actual-secret-key-here
DATABASE_URL=postgresql://prod_user:prod_password@db.example.com:5432/myapp_prod
ALLOWED_HOSTS=myapp.com,www.myapp.com
CORS_ORIGINS=https://myapp.com
```

Add to `.gitignore`:

```bash
# .gitignore
.env
*.env
.env.local
```

---

## Step 3: Docker Configuration

Docker packages your app so it runs the same everywhere.

### Create Dockerfile

```dockerfile
# Dockerfile

# Use official Python image
FROM python:3.11-slim

# Don't write .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
# Don't buffer output (see logs immediately)
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Start the server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**What this does:**

| Step | Purpose |
|------|---------|
| `FROM python:3.11-slim` | Use a small Python image |
| `WORKDIR /app` | Set where our code lives |
| `COPY requirements.txt` | Install dependencies first (caching) |
| `COPY . .` | Copy our application |
| `USER appuser` | Don't run as root (security) |
| `CMD [...]` | Start the server |

### Create docker-compose.yml

```yaml
# docker-compose.yml
version: '3.8'

services:
  # Your application
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/myapp
      - ALLOWED_HOSTS=localhost,127.0.0.1
    depends_on:
      db:
        condition: service_healthy
    command: >
      sh -c "aksara migrate && 
             uvicorn app.main:app --host 0.0.0.0 --port 8000"

  # PostgreSQL database
  db:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=myapp
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

### Run with Docker

```bash
# Build the image
docker-compose build

# Start the services
docker-compose up

# Or run in background
docker-compose up -d

# View logs
docker-compose logs -f web

# Stop everything
docker-compose down
```

---

## Step 4: Database Migrations

### Run Migrations Safely

**Never** run migrations and the server at the same time on first deploy.

```bash
# Option 1: Separate command
docker-compose run --rm web aksara migrate

# Option 2: In the startup command (shown in docker-compose.yml)
# aksara migrate && uvicorn ...
```

### Backup Before Migrating

```bash
# Backup production database
pg_dump -h db.example.com -U prod_user myapp_prod > backup_$(date +%Y%m%d).sql

# Then run migrations
aksara migrate
```

---

## Step 5: Production Server

### Use Gunicorn + Uvicorn

For production, use Gunicorn with Uvicorn workers:

```bash
# Install gunicorn
pip install gunicorn

# Run with multiple workers
gunicorn app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000
```

Update your Dockerfile:

```dockerfile
# Production CMD
CMD ["gunicorn", "app.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000"]
```

**How many workers?**

Rule of thumb: `(2 × CPU cores) + 1`

| CPU Cores | Workers |
|-----------|---------|
| 1 | 3 |
| 2 | 5 |
| 4 | 9 |

---

## Step 6: HTTPS Setup

### Using a Reverse Proxy (Recommended)

Put nginx or Caddy in front of your app:

```nginx
# nginx.conf
server {
    listen 80;
    server_name myapp.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name myapp.com;
    
    ssl_certificate /etc/ssl/certs/myapp.crt;
    ssl_certificate_key /etc/ssl/private/myapp.key;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Using Caddy (Automatic HTTPS)

```
# Caddyfile
myapp.com {
    reverse_proxy localhost:8000
}
```

Caddy automatically gets and renews SSL certificates!

---

## Step 7: Monitoring

### Health Check Endpoint

Add a health check to your app:

```python
# app/main.py
from aksara import Aksara

app = Aksara(...)

@app.get("/health")
async def health_check():
    """Health check for load balancers."""
    return {"status": "healthy"}
```

### Logging

Configure structured logging:

```python
# settings/production.py
AKSARA = {
    # ... other settings ...
    
    "LOGGING": {
        "level": "INFO",
        "format": "json",  # Structured logs for log aggregators
    }
}
```

---

## Deployment Options

### Platform as a Service (Easy)

| Platform | Pros | Cons |
|----------|------|------|
| **Railway** | Easy, free tier | Less control |
| **Render** | Easy, auto-deploys | Limited free tier |
| **Fly.io** | Fast, global | Learning curve |
| **Heroku** | Established, add-ons | Expensive |

### Virtual Private Server (More Control)

| Provider | Pros | Cons |
|----------|------|------|
| **DigitalOcean** | Simple, good docs | Manual setup |
| **Linode** | Affordable | Manual setup |
| **AWS EC2** | Powerful, scalable | Complex |

### Kubernetes (Scale)

For large applications that need to scale:

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
      - name: web
        image: myapp:latest
        ports:
        - containerPort: 8000
        envFrom:
        - secretRef:
            name: myapp-secrets
```

---

## Quick Deployment Checklist

```bash
# 1. Set environment variables
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(50))")
export DATABASE_URL=postgresql://...
export ALLOWED_HOSTS=myapp.com

# 2. Build and push Docker image
docker build -t myapp:latest .
docker push myregistry.com/myapp:latest

# 3. Run migrations
aksara migrate

# 4. Start the server
docker-compose up -d

# 5. Verify it's running
curl https://myapp.com/health
```

---

## Troubleshooting

### "Connection refused" to database

**Problem:** App can't connect to PostgreSQL.

**Solution:** Check `DATABASE_URL` and ensure PostgreSQL is running and accessible.

### Static files not loading

**Problem:** CSS/JS files return 404.

**Solution:** Collect static files and configure your web server to serve them:

```bash
aksara collectstatic
```

### "Not allowed host" error

**Problem:** Request blocked by ALLOWED_HOSTS.

**Solution:** Add your domain to ALLOWED_HOSTS:

```bash
ALLOWED_HOSTS=myapp.com,www.myapp.com
```

---

## Next Steps

- Set up CI/CD for automatic deployments
- Configure monitoring and alerts
- Set up database backups
- Add rate limiting
- Configure caching

---

## Related Documentation

- [Settings](../getting-started/settings.md) — All configuration options
- [Middleware](../middleware/index.md) — Request processing
- [Security](../advanced/security.md) — Security best practices
