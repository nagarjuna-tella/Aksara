"""
Tests for M2M Batched Expansion Performance

Tests for prefetch_related() and batched M2M loading.
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
        await database.execute("DROP TABLE IF EXISTS m2m_post_tags CASCADE")
        await database.execute("DROP TABLE IF EXISTS m2m_posts CASCADE")
        await database.execute("DROP TABLE IF EXISTS m2m_tags CASCADE")
    except Exception:
        pass
    
    await database.disconnect()
    ModelRegistry.clear()
    RelationRegistry.clear()


@pytest.fixture
def m2m_models():
    """Create models for M2M tests."""
    from vidyut import Model, fields
    from vidyut.registry import ModelRegistry
    from vidyut.relations import RelationRegistry
    
    ModelRegistry.clear()
    RelationRegistry.clear()
    
    class M2MTag(Model):
        __tablename__ = "m2m_tags"
        name = fields.String(max_length=100)
    
    class M2MPost(Model):
        __tablename__ = "m2m_posts"
        title = fields.String(max_length=200)
        tags = fields.ManyToMany(M2MTag, related_name="posts")
    
    return {
        'Post': M2MPost,
        'Tag': M2MTag,
    }


@pytest.fixture
async def setup_m2m_tables(db, m2m_models):
    """Create test tables and seed data."""
    models = m2m_models
    
    # Create tables
    await db.execute(models['Tag'].get_create_table_sql())
    await db.execute(models['Post'].get_create_table_sql())
    
    # Create through table
    through_sql = models['Post']._m2m_fields['tags'].get_join_table_sql()
    await db.execute(through_sql)
    
    # Create test data
    tag1 = await models['Tag'].objects.create(name="Python")
    tag2 = await models['Tag'].objects.create(name="Async")
    tag3 = await models['Tag'].objects.create(name="ORM")
    
    post1 = await models['Post'].objects.create(title="Post 1")
    post2 = await models['Post'].objects.create(title="Post 2")
    post3 = await models['Post'].objects.create(title="Post 3")
    
    # Add tags to posts
    await post1.tags.add(tag1, tag2)  # Python, Async
    await post2.tags.add(tag2, tag3)  # Async, ORM
    await post3.tags.add(tag1, tag3)  # Python, ORM
    
    return models


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
class TestPrefetchRelatedQuerySet:
    """Tests for prefetch_related on QuerySet."""
    
    @pytest.mark.asyncio
    async def test_prefetch_related_returns_queryset(self, db, setup_m2m_tables):
        """Test that prefetch_related returns a QuerySet."""
        models = setup_m2m_tables
        
        queryset = models['Post'].objects.prefetch_related("tags")
        
        from vidyut.manager import QuerySet
        assert isinstance(queryset, QuerySet)
    
    @pytest.mark.asyncio
    async def test_prefetch_related_chaining(self, db, setup_m2m_tables):
        """Test that prefetch_related can be chained with filter."""
        models = setup_m2m_tables
        
        queryset = (
            models['Post'].objects
            .filter(title__icontains="Post")
            .prefetch_related("tags")
        )
        
        posts = await queryset.all()
        assert len(posts) == 3
    
    @pytest.mark.asyncio
    async def test_prefetch_related_loads_m2m(self, db, setup_m2m_tables):
        """Test prefetch_related loads M2M relations."""
        models = setup_m2m_tables
        
        posts = await models['Post'].objects.prefetch_related("tags").all()
        
        # All posts should have prefetched tags
        for post in posts:
            assert post.is_prefetched("tags")
            tags = post.get_prefetched_m2m("tags")
            assert isinstance(tags, list)
            assert len(tags) == 2  # Each post has 2 tags
    
    @pytest.mark.asyncio
    async def test_get_prefetched_m2m_raises_if_not_prefetched(self, db, setup_m2m_tables):
        """Test get_prefetched_m2m raises if not prefetched."""
        models = setup_m2m_tables
        
        posts = await models['Post'].objects.all()  # No prefetch_related
        
        with pytest.raises(ValueError) as exc_info:
            posts[0].get_prefetched_m2m("tags")
        
        assert "not prefetched" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_prefetched_m2m_raises_for_non_m2m_field(self, db, setup_m2m_tables):
        """Test get_prefetched_m2m raises for non-M2M field."""
        models = setup_m2m_tables
        
        posts = await models['Post'].objects.all()
        
        with pytest.raises(ValueError) as exc_info:
            posts[0].get_prefetched_m2m("title")
        
        assert "not a ManyToMany field" in str(exc_info.value)


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
class TestM2MBatchedPerformance:
    """Tests for batched M2M loading performance."""
    
    @pytest.mark.asyncio
    async def test_prefetch_related_batches_queries(self, db, setup_m2m_tables):
        """Test that prefetch_related uses batched queries."""
        models = setup_m2m_tables
        
        async with capture_queries() as log:
            posts = await models['Post'].objects.prefetch_related("tags").all()
            
            # Access all tags
            for post in posts:
                _ = post.get_prefetched_m2m("tags")
        
        # Should have exactly 2 queries:
        # 1. SELECT * FROM m2m_posts
        # 2. SELECT * FROM m2m_post_tags JOIN m2m_tags
        assert log.count == 2
    
    @pytest.mark.asyncio
    async def test_many_posts_still_two_queries(self, db, setup_m2m_tables):
        """Test that even with many posts, only 2 queries are made."""
        models = setup_m2m_tables
        
        # Create more posts with tags
        extra_posts = []
        for i in range(10):
            post = await models['Post'].objects.create(title=f"Bulk Post {i}")
            extra_posts.append(post)
        
        # Add tags to all extra posts
        all_tags = await models['Tag'].objects.all()
        for post in extra_posts:
            await post.tags.add(all_tags[0])  # Add first tag
        
        async with capture_queries() as log:
            posts = await models['Post'].objects.prefetch_related("tags").all()
            
            for post in posts:
                _ = post.get_prefetched_m2m("tags")
        
        # Still just 2 queries!
        assert log.count == 2
        assert len(posts) >= 13  # 3 original + 10 new
    
    @pytest.mark.asyncio
    async def test_prefetch_related_sql_contains_any(self, db, setup_m2m_tables):
        """Test that prefetch_related uses ANY($1) for batching."""
        models = setup_m2m_tables
        
        async with capture_queries() as log:
            posts = await models['Post'].objects.prefetch_related("tags").all()
        
        # Check the second query uses ANY for batching
        assert log.count == 2
        queries = [q.sql for q in log.queries]
        
        # Should have a query that uses ANY for batch loading
        # (Either in the form of "IN ($1, $2, ...)" or "= ANY($1)")
        has_batch = any("ANY" in q or "IN" in q for q in queries)
        assert has_batch, f"Expected batch query with ANY/IN, got: {queries}"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
class TestBatchedM2MVsNPlus1:
    """Compare batched M2M loading vs N+1 pattern."""
    
    @pytest.mark.asyncio
    async def test_n_plus_1_problem_demonstration(self, db, setup_m2m_tables):
        """Demonstrate N+1 problem without prefetch_related."""
        models = setup_m2m_tables
        
        async with capture_queries() as log:
            posts = await models['Post'].objects.all()
            
            # Without prefetch_related, each access triggers a query
            for post in posts:
                # This would cause N+1 if we called post.tags.all() here
                pass
        
        # Just the main query
        assert log.count == 1
    
    @pytest.mark.asyncio
    async def test_batched_avoids_n_plus_1(self, db, setup_m2m_tables):
        """Show that prefetch_related avoids N+1."""
        models = setup_m2m_tables
        
        async with capture_queries() as log:
            posts = await models['Post'].objects.prefetch_related("tags").all()
            
            # Access tags for all posts
            tag_counts = []
            for post in posts:
                tags = post.get_prefetched_m2m("tags")
                tag_counts.append(len(tags))
        
        # Only 2 queries (posts + tags batch) instead of 4 (posts + 3 per-post queries)
        assert log.count == 2
        assert sum(tag_counts) == 6  # Total tags across all posts


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
class TestCombinedSelectAndPrefetch:
    """Tests for using both select_related and prefetch_related."""
    
    @pytest.fixture
    def combined_models(self):
        """Create models with both FK and M2M."""
        from vidyut import Model, fields, CASCADE
        from vidyut.registry import ModelRegistry
        from vidyut.relations import RelationRegistry
        
        ModelRegistry.clear()
        RelationRegistry.clear()
        
        class CombUser(Model):
            __tablename__ = "comb_users"
            name = fields.String(max_length=100)
        
        class CombTag(Model):
            __tablename__ = "comb_tags"
            name = fields.String(max_length=100)
        
        class CombPost(Model):
            __tablename__ = "comb_posts"
            title = fields.String(max_length=200)
            author = fields.ForeignKey(CombUser, on_delete=CASCADE, related_name="posts")
            tags = fields.ManyToMany(CombTag, related_name="posts")
        
        return {
            'User': CombUser,
            'Tag': CombTag,
            'Post': CombPost,
        }
    
    @pytest.fixture
    async def setup_combined_tables(self, db, combined_models):
        """Set up combined test tables."""
        models = combined_models
        
        # Clean up first
        try:
            await db.execute("DROP TABLE IF EXISTS comb_post_tags CASCADE")
            await db.execute("DROP TABLE IF EXISTS comb_posts CASCADE")
            await db.execute("DROP TABLE IF EXISTS comb_tags CASCADE")
            await db.execute("DROP TABLE IF EXISTS comb_users CASCADE")
        except Exception:
            pass
        
        # Create tables
        await db.execute(models['User'].get_create_table_sql())
        await db.execute(models['Tag'].get_create_table_sql())
        await db.execute(models['Post'].get_create_table_sql())
        
        # Create through table
        through_sql = models['Post']._m2m_fields['tags'].get_join_table_sql()
        await db.execute(through_sql)
        
        # Seed data
        user = await models['User'].objects.create(name="Author")
        tag1 = await models['Tag'].objects.create(name="Tag1")
        tag2 = await models['Tag'].objects.create(name="Tag2")
        
        post = await models['Post'].objects.create(title="Post", author_id=user.id)
        await post.tags.add(tag1, tag2)
        
        yield models
        
        # Cleanup
        try:
            await db.execute("DROP TABLE IF EXISTS comb_post_tags CASCADE")
            await db.execute("DROP TABLE IF EXISTS comb_posts CASCADE")
            await db.execute("DROP TABLE IF EXISTS comb_tags CASCADE")
            await db.execute("DROP TABLE IF EXISTS comb_users CASCADE")
        except Exception:
            pass
    
    @pytest.mark.asyncio
    async def test_combined_select_and_prefetch(self, db, setup_combined_tables):
        """Test using both select_related and prefetch_related."""
        models = setup_combined_tables
        
        async with capture_queries() as log:
            posts = await (
                models['Post'].objects
                .select_related("author")
                .prefetch_related("tags")
                .all()
            )
            
            for post in posts:
                author = post.get_related("author")
                tags = post.get_prefetched_m2m("tags")
                
                assert author.name == "Author"
                assert len(tags) == 2
        
        # Should have 3 queries: posts + authors + tags
        assert log.count == 3
