"""
Integration Tests for Vidyut

These tests require a real PostgreSQL database.
Set DATABASE_URL environment variable to run.

Example:
    DATABASE_URL=postgresql://postgres:postgres@localhost/vidyut_test pytest tests/test_integration.py
"""

import os
import pytest
from uuid import UUID

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
        await database.execute("DROP TABLE IF EXISTS test_users CASCADE")
        await database.execute("DROP TABLE IF EXISTS test_posts CASCADE")
    except Exception:
        pass
    
    await database.disconnect()
    ModelRegistry.clear()


@pytest.fixture
def user_model():
    """Create a test user model."""
    from vidyut import Model, fields
    
    class TestUser(Model):
        __tablename__ = "test_users"
        email = fields.String(max_length=255, unique=True)
        name = fields.String(max_length=100, nullable=True)
        is_active = fields.Boolean(default=True)
        age = fields.Integer(nullable=True)
        metadata = fields.JSON(nullable=True)
    
    return TestUser


@pytest.fixture
async def setup_table(db, user_model):
    """Create the test table."""
    sql = user_model.get_create_table_sql()
    await db.execute(sql)
    return user_model


class TestDatabaseConnection:
    """Tests for database connectivity."""
    
    @pytest.mark.asyncio
    async def test_database_connect(self, db):
        """Test that database connects successfully."""
        result = await db.fetchval("SELECT 1")
        assert result == 1
    
    @pytest.mark.asyncio
    async def test_database_execute(self, db):
        """Test execute returns status."""
        result = await db.execute("SELECT 1")
        # asyncpg returns None for SELECT
        assert result is None or "SELECT" in str(result)


class TestCRUDOperations:
    """Tests for Create, Read, Update, Delete operations."""
    
    @pytest.mark.asyncio
    async def test_create_model(self, db, setup_table):
        """Test creating a model instance."""
        User = setup_table
        
        user = await User.objects.create(
            email="test@example.com",
            name="Test User"
        )
        
        assert user.email == "test@example.com"
        assert user.name == "Test User"
        assert user.is_active is True
        assert isinstance(user.id, UUID)
        assert user._is_new is False
    
    @pytest.mark.asyncio
    async def test_get_by_id(self, db, setup_table):
        """Test getting a model by ID."""
        User = setup_table
        
        created = await User.objects.create(email="get@example.com")
        
        fetched = await User.objects.get(id=created.id)
        
        assert fetched.id == created.id
        assert fetched.email == "get@example.com"
    
    @pytest.mark.asyncio
    async def test_get_by_field(self, db, setup_table):
        """Test getting a model by field value."""
        User = setup_table
        
        await User.objects.create(email="field@example.com", name="FieldTest")
        
        fetched = await User.objects.get(email="field@example.com")
        
        assert fetched.email == "field@example.com"
        assert fetched.name == "FieldTest"
    
    @pytest.mark.asyncio
    async def test_get_not_found(self, db, setup_table):
        """Test get raises DoesNotExist."""
        from vidyut.manager import DoesNotExist
        
        User = setup_table
        
        with pytest.raises(DoesNotExist):
            await User.objects.get(email="nonexistent@example.com")
    
    @pytest.mark.asyncio
    async def test_filter_all(self, db, setup_table):
        """Test filtering and getting all results."""
        User = setup_table
        
        await User.objects.create(email="active1@example.com", is_active=True)
        await User.objects.create(email="active2@example.com", is_active=True)
        await User.objects.create(email="inactive@example.com", is_active=False)
        
        active_users = await User.objects.filter(is_active=True).all()
        
        assert len(active_users) == 2
        assert all(u.is_active for u in active_users)
    
    @pytest.mark.asyncio
    async def test_filter_first(self, db, setup_table):
        """Test filtering and getting first result."""
        User = setup_table
        
        await User.objects.create(email="first1@example.com", is_active=True)
        await User.objects.create(email="first2@example.com", is_active=True)
        
        user = await User.objects.filter(is_active=True).first()
        
        assert user is not None
        assert user.is_active is True
    
    @pytest.mark.asyncio
    async def test_filter_first_none(self, db, setup_table):
        """Test filter first returns None when no match."""
        User = setup_table
        
        result = await User.objects.filter(email="nonexistent@example.com").first()
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_filter_count(self, db, setup_table):
        """Test counting filtered results."""
        User = setup_table
        
        await User.objects.create(email="count1@example.com", is_active=True)
        await User.objects.create(email="count2@example.com", is_active=True)
        await User.objects.create(email="count3@example.com", is_active=False)
        
        active_count = await User.objects.filter(is_active=True).count()
        
        assert active_count == 2
    
    @pytest.mark.asyncio
    async def test_update_model(self, db, setup_table):
        """Test updating a model instance."""
        User = setup_table
        
        user = await User.objects.create(email="update@example.com", name="Original")
        
        user.name = "Updated"
        await user.save()
        
        fetched = await User.objects.get(id=user.id)
        assert fetched.name == "Updated"
    
    @pytest.mark.asyncio
    async def test_delete_model(self, db, setup_table):
        """Test deleting a model instance."""
        from vidyut.manager import DoesNotExist
        
        User = setup_table
        
        user = await User.objects.create(email="delete@example.com")
        user_id = user.id
        
        await user.delete()
        
        with pytest.raises(DoesNotExist):
            await User.objects.get(id=user_id)
    
    @pytest.mark.asyncio
    async def test_json_field(self, db, setup_table):
        """Test JSON field storage and retrieval."""
        User = setup_table
        
        metadata = {"role": "admin", "permissions": ["read", "write"]}
        user = await User.objects.create(
            email="json@example.com",
            metadata=metadata
        )
        
        fetched = await User.objects.get(id=user.id)
        
        assert fetched.metadata == metadata
        assert fetched.metadata["role"] == "admin"
    
    @pytest.mark.asyncio
    async def test_integer_field(self, db, setup_table):
        """Test Integer field storage and retrieval."""
        User = setup_table
        
        user = await User.objects.create(
            email="integer@example.com",
            age=25
        )
        
        fetched = await User.objects.get(id=user.id)
        
        assert fetched.age == 25
    
    @pytest.mark.asyncio
    async def test_all_returns_all_records(self, db, setup_table):
        """Test all() returns all records."""
        User = setup_table
        
        await User.objects.create(email="all1@example.com")
        await User.objects.create(email="all2@example.com")
        await User.objects.create(email="all3@example.com")
        
        all_users = await User.objects.all()
        
        assert len(all_users) == 3
    
    @pytest.mark.asyncio
    async def test_timestamps_created(self, db, setup_table):
        """Test created_at is set on creation."""
        User = setup_table
        
        user = await User.objects.create(email="timestamp@example.com")
        
        assert user.created_at is not None
    
    @pytest.mark.asyncio
    async def test_timestamps_updated(self, db, setup_table):
        """Test updated_at changes on update."""
        User = setup_table
        
        user = await User.objects.create(email="updated@example.com")
        original_updated = user.updated_at
        
        # Small delay to ensure timestamp difference
        import asyncio
        await asyncio.sleep(0.1)
        
        user.name = "Updated"
        await user.save()
        
        assert user.updated_at >= original_updated


class TestGetOrCreate:
    """Tests for get_or_create method."""
    
    @pytest.mark.asyncio
    async def test_get_or_create_creates(self, db, setup_table):
        """Test get_or_create creates new record."""
        User = setup_table
        
        user, created = await User.objects.get_or_create(
            email="goc@example.com",
            defaults={"name": "New User"}
        )
        
        assert created is True
        assert user.email == "goc@example.com"
        assert user.name == "New User"
    
    @pytest.mark.asyncio
    async def test_get_or_create_gets(self, db, setup_table):
        """Test get_or_create gets existing record."""
        User = setup_table
        
        await User.objects.create(email="existing@example.com", name="Existing")
        
        user, created = await User.objects.get_or_create(
            email="existing@example.com",
            defaults={"name": "Should Not Be Used"}
        )
        
        assert created is False
        assert user.name == "Existing"


class TestGetOrNone:
    """Tests for get_or_none method."""
    
    @pytest.mark.asyncio
    async def test_get_or_none_found(self, db, setup_table):
        """Test get_or_none returns record when found."""
        User = setup_table
        
        await User.objects.create(email="found@example.com")
        
        user = await User.objects.get_or_none(email="found@example.com")
        
        assert user is not None
        assert user.email == "found@example.com"
    
    @pytest.mark.asyncio
    async def test_get_or_none_not_found(self, db, setup_table):
        """Test get_or_none returns None when not found."""
        User = setup_table
        
        user = await User.objects.get_or_none(email="notfound@example.com")
        
        assert user is None
