"""
Tests for select_related Performance

Tests for QuerySet.select_related() and batched FK/O2O preloading.
"""

import os
import pytest

from vidyut.db.debug import capture_queries


# Integration tests require DATABASE_URL
pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set"
)


@pytest.fixture
async def db():
    """Create database connection."""
    from vidyut.db import Database
    from vidyut.registry import ModelRegistry
    from vidyut.relations import RelationRegistry
    
    ModelRegistry.clear()
    RelationRegistry.clear()
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set")
    
    database = Database(database_url)
    await database.connect()
    
    yield database
    
    # Clean up
    try:
        await database.execute("DROP TABLE IF EXISTS sr_posts CASCADE")
        await database.execute("DROP TABLE IF EXISTS sr_users CASCADE")
        await database.execute("DROP TABLE IF EXISTS sr_categories CASCADE")
    except Exception:
        pass
    
    await database.disconnect()
    ModelRegistry.clear()
    RelationRegistry.clear()


@pytest.fixture
def select_related_models():
    """Create models for select_related tests."""
    from vidyut import Model, fields, CASCADE
    from vidyut.registry import ModelRegistry
    from vidyut.relations import RelationRegistry
    
    ModelRegistry.clear()
    RelationRegistry.clear()
    
    class SRUser(Model):
        __tablename__ = "sr_users"
        name = fields.String(max_length=100)
        email = fields.Email(unique=True)
    
    class SRCategory(Model):
        __tablename__ = "sr_categories"
        name = fields.String(max_length=100)
    
    class SRPost(Model):
        __tablename__ = "sr_posts"
        title = fields.String(max_length=200)
        author = fields.ForeignKey(SRUser, on_delete=CASCADE, related_name="posts")
        category = fields.ForeignKey(SRCategory, on_delete=CASCADE, related_name="posts", nullable=True)
    
    return {
        'User': SRUser,
        'Category': SRCategory,
        'Post': SRPost,
    }


@pytest.fixture
async def setup_select_related_tables(db, select_related_models):
    """Create test tables and seed data."""
    models = select_related_models
    
    # Create tables
    await db.execute(models['User'].get_create_table_sql())
    await db.execute(models['Category'].get_create_table_sql())
    await db.execute(models['Post'].get_create_table_sql())
    
    # Create test data
    user1 = await models['User'].objects.create(name="Alice", email="alice@example.com")
    user2 = await models['User'].objects.create(name="Bob", email="bob@example.com")
    
    cat1 = await models['Category'].objects.create(name="Tech")
    cat2 = await models['Category'].objects.create(name="Science")
    
    # Create posts
    await models['Post'].objects.create(title="Post 1", author_id=user1.id, category_id=cat1.id)
    await models['Post'].objects.create(title="Post 2", author_id=user1.id, category_id=cat2.id)
    await models['Post'].objects.create(title="Post 3", author_id=user2.id, category_id=cat1.id)
    await models['Post'].objects.create(title="Post 4", author_id=user2.id, category_id=None)
    
    return models


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
class TestSelectRelatedQuerySet:
    """Tests for select_related on QuerySet."""
    
    @pytest.mark.asyncio
    async def test_select_related_returns_queryset(self, db, setup_select_related_tables):
        """Test that select_related returns a QuerySet."""
        models = setup_select_related_tables
        
        queryset = models['Post'].objects.select_related("author")
        
        # Should return a QuerySet
        from vidyut.manager import QuerySet
        assert isinstance(queryset, QuerySet)
    
    @pytest.mark.asyncio
    async def test_select_related_chaining(self, db, setup_select_related_tables):
        """Test that select_related can be chained."""
        models = setup_select_related_tables
        
        queryset = (
            models['Post'].objects
            .select_related("author")
            .select_related("category")
            .filter(title__icontains="Post")
        )
        
        posts = await queryset.all()
        assert len(posts) == 4
    
    @pytest.mark.asyncio
    async def test_select_related_single_field(self, db, setup_select_related_tables):
        """Test select_related with single FK field."""
        models = setup_select_related_tables
        
        async with capture_queries() as log:
            posts = await models['Post'].objects.select_related("author").all()
            
            # Access authors - should NOT trigger additional queries
            for post in posts:
                author = post.get_related("author")
                assert author is not None
                assert author.name in ["Alice", "Bob"]
        
        # Should have exactly 2 queries: posts + authors batch
        assert log.count == 2
    
    @pytest.mark.asyncio
    async def test_select_related_multiple_fields(self, db, setup_select_related_tables):
        """Test select_related with multiple FK fields."""
        models = setup_select_related_tables
        
        async with capture_queries() as log:
            posts = await (
                models['Post'].objects
                .select_related("author", "category")
                .all()
            )
            
            # Access both relations
            for post in posts:
                author = post.get_related("author")
                category = post.get_related("category")
                assert author is not None
        
        # Should have 3 queries: posts + authors + categories
        assert log.count == 3
    
    @pytest.mark.asyncio
    async def test_select_related_handles_null_fk(self, db, setup_select_related_tables):
        """Test select_related handles NULL FK values."""
        models = setup_select_related_tables
        
        posts = await models['Post'].objects.select_related("category").all()
        
        # Find the post with NULL category
        for post in posts:
            category = post.get_related("category")
            if post.title == "Post 4":
                assert category is None
            else:
                assert category is not None
    
    @pytest.mark.asyncio
    async def test_select_related_with_filter(self, db, setup_select_related_tables):
        """Test select_related combined with filter."""
        models = setup_select_related_tables
        
        async with capture_queries() as log:
            posts = await (
                models['Post'].objects
                .filter(title__icontains="Post 1")
                .select_related("author")
                .all()
            )
            
            assert len(posts) == 1
            author = posts[0].get_related("author")
            assert author.name == "Alice"
        
        # Should have 2 queries
        assert log.count == 2
    
    @pytest.mark.asyncio
    async def test_is_prefetched(self, db, setup_select_related_tables):
        """Test is_prefetched method."""
        models = setup_select_related_tables
        
        posts = await models['Post'].objects.select_related("author").all()
        
        for post in posts:
            assert post.is_prefetched("author") is True
            assert post.is_prefetched("category") is False
    
    @pytest.mark.asyncio
    async def test_get_related_raises_if_not_prefetched(self, db, setup_select_related_tables):
        """Test get_related raises if field wasn't prefetched."""
        models = setup_select_related_tables
        
        posts = await models['Post'].objects.all()  # No select_related
        
        with pytest.raises(ValueError) as exc_info:
            posts[0].get_related("author")
        
        assert "not prefetched" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_related_raises_for_non_fk_field(self, db, setup_select_related_tables):
        """Test get_related raises for non-FK field."""
        models = setup_select_related_tables
        
        posts = await models['Post'].objects.all()
        
        with pytest.raises(ValueError) as exc_info:
            posts[0].get_related("title")
        
        assert "not a ForeignKey" in str(exc_info.value)


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
class TestSelectRelatedPerformance:
    """Performance comparison tests."""
    
    @pytest.mark.asyncio
    async def test_query_count_without_select_related(self, db, setup_select_related_tables):
        """Baseline: query count without select_related."""
        models = setup_select_related_tables
        
        async with capture_queries() as log:
            posts = await models['Post'].objects.all()
        
        # Just the main query
        assert log.count == 1
    
    @pytest.mark.asyncio
    async def test_query_count_with_select_related(self, db, setup_select_related_tables):
        """Test that select_related uses batched queries."""
        models = setup_select_related_tables
        
        async with capture_queries() as log:
            posts = await models['Post'].objects.select_related("author").all()
            
            # Access all authors
            for post in posts:
                _ = post.get_related("author")
        
        # Should be exactly 2 queries regardless of post count
        assert log.count == 2
    
    @pytest.mark.asyncio
    async def test_many_posts_still_two_queries(self, db, setup_select_related_tables):
        """Test that even with many posts, only 2 queries are made."""
        models = setup_select_related_tables
        
        # Create more posts
        user = await models['User'].objects.create(name="Many", email="many@example.com")
        for i in range(10):
            await models['Post'].objects.create(
                title=f"Bulk Post {i}",
                author_id=user.id
            )
        
        async with capture_queries() as log:
            posts = await models['Post'].objects.select_related("author").all()
            
            for post in posts:
                _ = post.get_related("author")
        
        # Still just 2 queries!
        assert log.count == 2
        assert len(posts) >= 14  # 4 original + 10 new
