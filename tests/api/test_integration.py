"""
Integration Tests for Vidyut API Layer

These tests require a real PostgreSQL database.
Set DATABASE_URL environment variable to run.

Example:
    DATABASE_URL=postgresql://postgres:postgres@localhost/vidyut_test pytest tests/api/test_integration.py -v
"""

import os
import pytest
from uuid import UUID
from httpx import AsyncClient, ASGITransport

# Skip all tests if DATABASE_URL is not set
pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set"
)


@pytest.fixture
async def db():
    """Create database connection and clean up tables."""
    from vidyut.db import Database
    from vidyut.registry import ModelRegistry
    
    ModelRegistry.clear()
    
    database_url = os.getenv("DATABASE_URL")
    database = Database(database_url)
    await database.connect()
    
    yield database
    
    # Clean up - drop test tables
    try:
        await database.execute("DROP TABLE IF EXISTS api_test_posts CASCADE")
        await database.execute("DROP TABLE IF EXISTS api_test_users CASCADE")
    except Exception:
        pass
    
    await database.disconnect()
    ModelRegistry.clear()


@pytest.fixture
def user_model(db):
    """Create a test user model."""
    from vidyut import Model, fields
    
    class ApiTestUser(Model):
        email = fields.String(max_length=255, unique=True)
        name = fields.String(max_length=100, nullable=True)
        is_active = fields.Boolean(default=True)
        
        class Meta:
            table_name = "api_test_users"
    
    return ApiTestUser


@pytest.fixture
def post_model(db, user_model):
    """Create a test post model with FK to user."""
    from vidyut import Model, fields
    
    class ApiTestPost(Model):
        title = fields.String(max_length=200)
        content = fields.String(max_length=10000, nullable=True)
        is_published = fields.Boolean(default=False)
        author = fields.ForeignKey(user_model, on_delete="CASCADE", nullable=True)
        
        class Meta:
            table_name = "api_test_posts"
    
    return ApiTestPost


@pytest.fixture
async def tables_created(db, user_model, post_model):
    """Create tables in the database."""
    # Clean up any existing data first
    try:
        await db.execute("DELETE FROM api_test_posts")
        await db.execute("DELETE FROM api_test_users")
    except Exception:
        pass
    
    # Create user table first (referenced by post)
    user_sql = user_model.get_create_table_sql()
    try:
        await db.execute(user_sql)
    except Exception:
        pass  # Table may already exist
    
    post_sql = post_model.get_create_table_sql()
    try:
        await db.execute(post_sql)
    except Exception:
        pass  # Table may already exist
    
    # Clean up data again (in case tables existed)
    try:
        await db.execute("DELETE FROM api_test_posts")
        await db.execute("DELETE FROM api_test_users")
    except Exception:
        pass
    
    yield
    
    # Tables will be cleaned up by the db fixture


@pytest.fixture
def user_viewset(user_model):
    """Create a ViewSet for the user model."""
    from vidyut.api import ModelViewSet
    
    class UserViewSet(ModelViewSet):
        model = user_model
        prefix = "/users"
        tags = ["Users"]
        default_limit = 10
        max_limit = 50
    
    return UserViewSet


@pytest.fixture
def post_viewset(post_model):
    """Create a ViewSet for the post model."""
    from vidyut.api import ModelViewSet
    
    class PostViewSet(ModelViewSet):
        model = post_model
        prefix = "/posts"
        tags = ["Posts"]
    
    return PostViewSet


@pytest.fixture
async def app(db, tables_created, user_viewset, post_viewset):
    """Create a FastAPI app with ViewSets registered."""
    from fastapi import FastAPI
    from vidyut.api import include_viewset
    
    app = FastAPI()
    include_viewset(app, user_viewset)
    include_viewset(app, post_viewset)
    
    yield app


@pytest.fixture
async def client(app):
    """Create an async HTTP client for the app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# =============================================================================
# User CRUD Integration Tests
# =============================================================================

class TestUserCRUD:
    """Test full CRUD operations on User model via API."""
    
    async def test_create_user(self, client):
        """Test creating a user via POST."""
        response = await client.post("/users/", json={
            "email": "test@example.com",
            "name": "Test User",
            "is_active": True,
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["name"] == "Test User"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
        
        # Verify it's a valid UUID
        UUID(data["id"])
    
    async def test_create_user_minimal(self, client):
        """Test creating a user with only required fields."""
        response = await client.post("/users/", json={
            "email": "minimal@example.com",
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "minimal@example.com"
        assert data["name"] is None  # Optional field
        assert data["is_active"] is True  # Default value
    
    async def test_create_user_duplicate_email(self, client):
        """Test that duplicate email returns 409."""
        await client.post("/users/", json={"email": "dupe@example.com"})
        
        response = await client.post("/users/", json={"email": "dupe@example.com"})
        
        assert response.status_code == 409
        assert "unique constraint" in response.json()["detail"].lower()
    
    async def test_list_users_empty(self, client):
        """Test listing users when none exist."""
        response = await client.get("/users/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["results"] == []
        assert data["limit"] == 10  # default_limit from viewset
        assert data["offset"] == 0
    
    async def test_list_users_with_data(self, client):
        """Test listing users after creating some."""
        # Create 3 users
        for i in range(3):
            await client.post("/users/", json={"email": f"user{i}@example.com", "name": f"User {i}"})
        
        response = await client.get("/users/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3
        assert len(data["results"]) == 3
    
    async def test_list_users_pagination(self, client):
        """Test pagination with limit and offset."""
        # Create 5 users
        for i in range(5):
            await client.post("/users/", json={"email": f"page{i}@example.com"})
        
        # Get first page (2 items)
        response = await client.get("/users/?limit=2&offset=0")
        data = response.json()
        assert data["count"] == 5
        assert len(data["results"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 0
        
        # Get second page
        response = await client.get("/users/?limit=2&offset=2")
        data = response.json()
        assert data["count"] == 5
        assert len(data["results"]) == 2
        assert data["offset"] == 2
        
        # Get last page (only 1 item)
        response = await client.get("/users/?limit=2&offset=4")
        data = response.json()
        assert len(data["results"]) == 1
    
    async def test_retrieve_user(self, client):
        """Test getting a single user by ID."""
        # Create a user
        create_resp = await client.post("/users/", json={
            "email": "retrieve@example.com",
            "name": "Retrieve Me",
        })
        user_id = create_resp.json()["id"]
        
        # Retrieve it
        response = await client.get(f"/users/{user_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        assert data["email"] == "retrieve@example.com"
        assert data["name"] == "Retrieve Me"
    
    async def test_retrieve_user_not_found(self, client):
        """Test that non-existent user returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(f"/users/{fake_id}")
        
        assert response.status_code == 404
    
    async def test_update_user(self, client):
        """Test updating a user via PATCH."""
        # Create a user
        create_resp = await client.post("/users/", json={
            "email": "update@example.com",
            "name": "Original Name",
            "is_active": True,
        })
        user_id = create_resp.json()["id"]
        
        # Update it
        response = await client.patch(f"/users/{user_id}", json={
            "name": "Updated Name",
            "is_active": False,
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["is_active"] is False
        assert data["email"] == "update@example.com"  # Unchanged
    
    async def test_update_user_partial(self, client):
        """Test that PATCH only updates provided fields."""
        # Create a user
        create_resp = await client.post("/users/", json={
            "email": "partial@example.com",
            "name": "Original",
            "is_active": True,
        })
        user_id = create_resp.json()["id"]
        
        # Update only name
        response = await client.patch(f"/users/{user_id}", json={
            "name": "Changed",
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Changed"
        assert data["is_active"] is True  # Unchanged
    
    async def test_update_user_not_found(self, client):
        """Test that updating non-existent user returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.patch(f"/users/{fake_id}", json={"name": "X"})
        
        assert response.status_code == 404
    
    async def test_delete_user(self, client):
        """Test deleting a user."""
        # Create a user
        create_resp = await client.post("/users/", json={"email": "delete@example.com"})
        user_id = create_resp.json()["id"]
        
        # Delete it
        response = await client.delete(f"/users/{user_id}")
        
        assert response.status_code == 200
        assert response.json()["deleted"] is True
        
        # Verify it's gone
        get_resp = await client.get(f"/users/{user_id}")
        assert get_resp.status_code == 404
    
    async def test_delete_user_not_found(self, client):
        """Test that deleting non-existent user returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.delete(f"/users/{fake_id}")
        
        assert response.status_code == 404


# =============================================================================
# Post CRUD Integration Tests (with ForeignKey)
# =============================================================================

class TestPostCRUD:
    """Test CRUD operations on Post model with FK relationship."""
    
    async def test_create_post_without_author(self, client):
        """Test creating a post without an author."""
        response = await client.post("/posts/", json={
            "title": "My First Post",
            "content": "Hello world!",
            "is_published": True,
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "My First Post"
        assert data["content"] == "Hello world!"
        assert data["is_published"] is True
        assert data["author_id"] is None
    
    async def test_create_post_with_author(self, client):
        """Test creating a post with a valid author FK."""
        # Create an author
        user_resp = await client.post("/users/", json={"email": "author@example.com"})
        author_id = user_resp.json()["id"]
        
        # Create a post with that author
        response = await client.post("/posts/", json={
            "title": "Authored Post",
            "author_id": author_id,
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Authored Post"
        assert data["author_id"] == author_id
    
    async def test_list_posts_with_filter(self, client):
        """Test filtering posts by is_published."""
        # Create some posts
        await client.post("/posts/", json={"title": "Draft 1", "is_published": False})
        await client.post("/posts/", json={"title": "Draft 2", "is_published": False})
        await client.post("/posts/", json={"title": "Published", "is_published": True})
        
        # Filter by is_published
        response = await client.get("/posts/?is_published=true")
        data = response.json()
        
        assert data["count"] == 1
        assert data["results"][0]["title"] == "Published"
    
    async def test_list_posts_filter_by_author(self, client):
        """Test filtering posts by author (ForeignKey field)."""
        # Create two authors
        user1 = await client.post("/users/", json={"email": "author1@example.com"})
        user2 = await client.post("/users/", json={"email": "author2@example.com"})
        author1_id = user1.json()["id"]
        author2_id = user2.json()["id"]
        
        # Create posts
        await client.post("/posts/", json={"title": "Post by Author 1", "author_id": author1_id})
        await client.post("/posts/", json={"title": "Another by Author 1", "author_id": author1_id})
        await client.post("/posts/", json={"title": "Post by Author 2", "author_id": author2_id})
        
        # Filter by author field (FK field uses author, not author_id in filter)
        response = await client.get(f"/posts/?author={author1_id}")
        data = response.json()
        
        assert data["count"] == 2
        for post in data["results"]:
            assert post["author_id"] == author1_id
    
    async def test_update_post(self, client):
        """Test updating a post."""
        # Create a post
        create_resp = await client.post("/posts/", json={
            "title": "Original Title",
            "is_published": False,
        })
        post_id = create_resp.json()["id"]
        
        # Update it
        response = await client.patch(f"/posts/{post_id}", json={
            "title": "Updated Title",
            "is_published": True,
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["is_published"] is True
    
    async def test_delete_post(self, client):
        """Test deleting a post."""
        # Create a post
        create_resp = await client.post("/posts/", json={"title": "To Delete"})
        post_id = create_resp.json()["id"]
        
        # Delete it
        response = await client.delete(f"/posts/{post_id}")
        
        assert response.status_code == 200
        
        # Verify it's gone
        get_resp = await client.get(f"/posts/{post_id}")
        assert get_resp.status_code == 404


# =============================================================================
# Schema Auto-Generation Tests
# =============================================================================

class TestSchemaGeneration:
    """Test that schemas are correctly auto-generated from models."""
    
    async def test_create_validates_required_fields(self, client):
        """Test that create endpoint validates required fields."""
        # Missing required 'email' field
        response = await client.post("/users/", json={
            "name": "No Email",
        })
        
        assert response.status_code == 422  # Validation error
    
    async def test_create_validates_field_types(self, client):
        """Test that create endpoint validates field types."""
        # is_active should be boolean
        response = await client.post("/users/", json={
            "email": "types@example.com",
            "is_active": "not a boolean",
        })
        
        assert response.status_code == 422
    
    async def test_update_allows_partial(self, client):
        """Test that update schema allows partial updates."""
        # Create a user
        create_resp = await client.post("/users/", json={"email": "partial@example.com"})
        user_id = create_resp.json()["id"]
        
        # Update with empty body should work (no changes)
        response = await client.patch(f"/users/{user_id}", json={})
        
        assert response.status_code == 200


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""
    
    async def test_invalid_uuid_format(self, client):
        """Test that invalid UUID format returns proper error."""
        response = await client.get("/users/not-a-uuid")
        
        # Should return 404, 422, or 500 (depends on validation layer)
        # Invalid UUIDs will cause an error during lookup
        assert response.status_code in (400, 404, 422, 500)
    
    async def test_pagination_limits(self, client):
        """Test that pagination respects max_limit."""
        # Try to request more than max_limit (50 for users)
        response = await client.get("/users/?limit=100")
        
        # Should be capped or return error
        assert response.status_code in (200, 422)
        if response.status_code == 200:
            data = response.json()
            assert data["limit"] <= 50
    
    async def test_concurrent_creates(self, client):
        """Test handling of concurrent creates."""
        import asyncio
        
        async def create_user(i):
            return await client.post("/users/", json={"email": f"concurrent{i}@example.com"})
        
        # Create 5 users concurrently
        responses = await asyncio.gather(*[create_user(i) for i in range(5)])
        
        # All should succeed
        for resp in responses:
            assert resp.status_code == 201
        
        # Verify all exist
        list_resp = await client.get("/users/?limit=50")
        assert list_resp.json()["count"] >= 5
    
    async def test_empty_update(self, client):
        """Test that empty update doesn't break anything."""
        # Create a user
        create_resp = await client.post("/users/", json={"email": "empty@example.com", "name": "Original"})
        user_id = create_resp.json()["id"]
        
        # Update with empty JSON
        response = await client.patch(f"/users/{user_id}", json={})
        
        assert response.status_code == 200
        # Name should be unchanged
        assert response.json()["name"] == "Original"
    
    async def test_null_optional_fields(self, client):
        """Test that nullable fields work correctly."""
        # Create user without name (null by default)
        create_resp = await client.post("/users/", json={
            "email": "nulltest@example.com",
        })
        user_id = create_resp.json()["id"]
        
        # Verify name is null
        assert create_resp.json()["name"] is None
        
        # Update to add a name
        response = await client.patch(f"/users/{user_id}", json={"name": "Added Name"})
        assert response.status_code == 200
        assert response.json()["name"] == "Added Name"
