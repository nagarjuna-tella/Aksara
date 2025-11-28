# Vidyut Basic Example

This is a simple FastAPI application demonstrating Vidyut ORM usage.

## Setup

1. Make sure you have PostgreSQL running locally
2. Create a database:
   ```bash
   createdb vidyut_example
   ```

3. Install dependencies:
   ```bash
   cd /path/to/vidyut
   pip install -e ".[dev]"
   ```

4. Set database URL (optional, defaults to localhost):
   ```bash
   export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/vidyut_example"
   ```

## Running the App

```bash
cd examples/basic_app
uvicorn main:app --reload
```

The API will be available at http://localhost:8000

## API Endpoints

### Users

- `POST /users` - Create a user
- `GET /users` - List all users (filter with `?is_active=true`)
- `GET /users/{id}` - Get a user
- `PUT /users/{id}` - Update a user
- `DELETE /users/{id}` - Delete a user

### Posts

- `POST /posts` - Create a post
- `GET /posts` - List all posts (filter with `?is_published=true`)
- `GET /posts/{id}` - Get a post (increments view count)

### Health

- `GET /health` - Check database connection

## Example Usage

```bash
# Create a user
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "name": "Test User"}'

# List active users
curl http://localhost:8000/users?is_active=true

# Create a post
curl -X POST http://localhost:8000/posts \
  -H "Content-Type: application/json" \
  -d '{"title": "Hello World", "content": "This is my first post!"}'

# Get published posts
curl http://localhost:8000/posts?is_published=true
```

## Interactive Docs

Visit http://localhost:8000/docs for Swagger UI documentation.
