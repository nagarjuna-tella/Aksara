# Database Setup

Configure PostgreSQL for your Aksara application.

---

## Overview

Aksara is designed exclusively for PostgreSQL. This design choice enables:

- **UUID primary keys** with `gen_random_uuid()`
- **JSONB columns** for efficient JSON storage
- **Advanced indexing** including GiST, GIN, and BRIN
- **Async performance** via the `asyncpg` driver
- **Reliable transactions** with proper ACID compliance

---

## PostgreSQL Installation

### macOS

=== "Homebrew"

    ```bash
    # Install PostgreSQL 15
    brew install postgresql@15
    
    # Start the service
    brew services start postgresql@15
    
    # Verify installation
    psql --version
    ```

=== "Postgres.app"

    Download from [postgresapp.com](https://postgresapp.com/) and follow the installation wizard.

### Linux

=== "Ubuntu/Debian"

    ```bash
    # Install PostgreSQL
    sudo apt update
    sudo apt install postgresql postgresql-contrib
    
    # Start the service
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
    
    # Verify installation
    psql --version
    ```

=== "Fedora/RHEL"

    ```bash
    sudo dnf install postgresql-server postgresql-contrib
    sudo postgresql-setup --initdb
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
    ```

### Windows

=== "Installer"

    1. Download from [postgresql.org](https://www.postgresql.org/download/windows/)
    2. Run the installer
    3. Follow the setup wizard
    4. Remember the password you set for the `postgres` user

=== "WSL2"

    Use the Linux instructions inside WSL2 for better compatibility.

### Docker

The fastest way to get started:

```bash
docker run -d \
  --name aksara-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=myapp \
  -p 5432:5432 \
  -v aksara_pgdata:/var/lib/postgresql/data \
  postgres:15
```

---

## Create a Database

### Using `aksara dbsetup` (Recommended)

The fastest way to set up your database:

```bash
aksara dbsetup
```

This interactively checks PostgreSQL, prompts for credentials, creates the database, and writes `DATABASE_URL` to `.env`. See the [Quickstart](../quickstart.md) for the full output.

### Using psql

```bash
# Connect as postgres user
psql -U postgres

# Create a database
CREATE DATABASE myapp;

# Create a user (optional)
CREATE USER myappuser WITH PASSWORD 'secret';
GRANT ALL PRIVILEGES ON DATABASE myapp TO myappuser;

# Exit
\q
```

### Using `createdb` (Manual Alternative)

If you prefer manual database creation instead of `aksara dbsetup`:

```bash
createdb myapp
```

### Verify Connection

```bash
psql -U postgres -d myapp -c "SELECT version();"
```

---

## Connection String Format

Aksara uses standard PostgreSQL connection strings (also called DSNs):

```
postgresql://[user[:password]@][host][:port][/database]
```

### Examples

| Scenario | Connection String |
|----------|------------------|
| Local default | `postgresql://localhost/myapp` |
| With password | `postgresql://postgres:secret@localhost:5432/myapp` |
| Remote server | `postgresql://user:pass@db.example.com:5432/production` |
| Docker | `postgresql://postgres:password@localhost:5432/myapp` |
| SSL required | `postgresql://user:pass@host:5432/db?sslmode=require` |

### URL Parameters

| Parameter | Description | Values |
|-----------|-------------|--------|
| `sslmode` | SSL/TLS mode | `disable`, `allow`, `prefer`, `require`, `verify-ca`, `verify-full` |
| `connect_timeout` | Connection timeout in seconds | Integer |
| `application_name` | Application name for logging | String |

Example with parameters:
```
postgresql://user:pass@host:5432/db?sslmode=require&connect_timeout=10&application_name=aksara
```

---

## Configure Aksara

### Using Environment Variables

Create a `.env` file in your project root:

```bash
# .env
DATABASE_URL=postgresql://postgres:password@localhost:5432/myapp
```

### Using configure()

```python
from aksara import configure

configure(
    database_url="postgresql://postgres:password@localhost:5432/myapp",
    pool_min_size=5,
    pool_max_size=20,
)
```

### Using Aksara Constructor

```python
from aksara import Aksara

app = Aksara(
    database_url="postgresql://postgres:password@localhost:5432/myapp",
    min_pool_size=5,
    max_pool_size=20,
)
```

---

## Connection Pooling

Aksara uses connection pooling via `asyncpg` for optimal performance.

### Pool Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `pool_min_size` / `min_pool_size` | 5 | Minimum connections maintained |
| `pool_max_size` / `max_pool_size` | 20 | Maximum connections allowed |

### Recommendations

| Workload | Min Size | Max Size |
|----------|----------|----------|
| Development | 2 | 5 |
| Small production | 5 | 20 |
| Medium production | 10 | 50 |
| High traffic | 20 | 100 |

!!! warning "Don't Over-Provision"
    Each PostgreSQL connection consumes server memory. Set `max_size` based on your PostgreSQL `max_connections` setting (typically 100 by default).

### Example Configuration

```python
import os
from aksara import configure

# Production settings
configure(
    database_url=os.environ["DATABASE_URL"],
    pool_min_size=10,
    pool_max_size=50,
)
```

---

## Database Lifecycle

Aksara automatically manages database connections:

1. **Startup**: Connection pool is created when the app starts
2. **Request**: Connections are borrowed from the pool
3. **Completion**: Connections are returned to the pool
4. **Shutdown**: Pool is closed gracefully

### Manual Control (Advanced)

```python
from aksara.db import Database

# Get the database instance
db = Database.get_instance()

# Execute raw queries
result = await db.fetch("SELECT * FROM users WHERE email = $1", email)

# Execute single-value queries
count = await db.fetchval("SELECT COUNT(*) FROM users")

# Execute without return
await db.execute("UPDATE users SET active = false WHERE id = $1", user_id)
```

---

## Multiple Databases

For read replicas or multi-tenant setups:

```python
from aksara.db import Database

# Primary database (configured via Aksara)
primary = Database.get_instance()

# Create additional connections
replica = Database(
    database_url="postgresql://replica.example.com/myapp",
    pool_min_size=2,
    pool_max_size=10,
)
await replica.connect()

# Use replica for reads
users = await replica.fetch("SELECT * FROM users")
```

---

## Database Migrations

After configuring your database, create and apply migrations:

```bash
# Generate migrations from models
aksara makemigrations --app app.models

# Apply migrations
aksara migrate

# Check migration status
aksara migrate --check
```

See [Migrations](../orm/migrations.md) for detailed documentation.

---

## Troubleshooting

### Connection Refused

```
asyncpg.exceptions.ConnectionRefusedError: connection refused
```

**Solutions:**

1. Verify PostgreSQL is running:
   ```bash
   pg_isready -h localhost -p 5432
   ```

2. Check the connection string format

3. Ensure the database exists:
   ```bash
   psql -U postgres -c "\l"
   ```

### Authentication Failed

```
asyncpg.exceptions.InvalidPasswordError: password authentication failed
```

**Solutions:**

1. Verify username and password
2. Check `pg_hba.conf` for authentication settings
3. Reset password if needed:
   ```sql
   ALTER USER postgres PASSWORD 'newpassword';
   ```

### Database Does Not Exist

```
asyncpg.exceptions.InvalidCatalogNameError: database "myapp" does not exist
```

**Solution:**
```bash
# Recommended:
aksara dbsetup

# Or manually:
createdb myapp
```

### SSL Required

```
asyncpg.exceptions.ConnectionDoesNotExistError: SSL required
```

**Solution:**
Add `?sslmode=require` to your connection string.

### Too Many Connections

```
asyncpg.exceptions.TooManyConnectionsError: too many connections
```

**Solutions:**

1. Reduce `pool_max_size`
2. Increase PostgreSQL `max_connections`:
   ```sql
   ALTER SYSTEM SET max_connections = 200;
   ```
3. Restart PostgreSQL

---

## Production Recommendations

### Use Environment Variables

Never hardcode credentials:

```python
import os
from aksara import configure

configure(
    database_url=os.environ["DATABASE_URL"],  # Required in production
)
```

### Enable SSL

For remote databases:

```bash
DATABASE_URL=postgresql://user:pass@remote-host:5432/db?sslmode=require
```

### Connection Limits

Calculate based on your infrastructure:

```
max_pool_size <= (PostgreSQL max_connections - reserved) / number_of_app_instances
```

### Health Checks

Add a health check endpoint:

```python
from aksara.db import Database

@app.get("/health")
async def health_check():
    db = Database.get_instance()
    try:
        await db.fetchval("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": str(e)}
```

---

## Related Documentation

- [Settings](settings.md) — All configuration options
- [Migrations](../orm/migrations.md) — Database schema management
- [Running Your App](running-your-app.md) — Development and production
