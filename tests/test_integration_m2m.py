"""
Integration Tests for ManyToMany Relationships

These tests require a real PostgreSQL database.
Set DATABASE_URL environment variable to run.

Example:
    DATABASE_URL=postgresql://postgres:postgres@localhost/aksara_test pytest tests/test_integration_m2m.py -v
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
    from aksara.db import Database
    from aksara.registry import ModelRegistry
    
    ModelRegistry.clear()
    
    database_url = os.getenv("DATABASE_URL")
    database = Database(database_url)
    await database.connect()
    
    yield database
    
    # Clean up - drop test tables in reverse order of dependencies
    try:
        await database.execute("DROP TABLE IF EXISTS articles_tags CASCADE")
        await database.execute("DROP TABLE IF EXISTS test_articles CASCADE")
        await database.execute("DROP TABLE IF EXISTS test_tags CASCADE")
        await database.execute("DROP TABLE IF EXISTS test_profiles CASCADE")
        await database.execute("DROP TABLE IF EXISTS test_m2m_users CASCADE")
    except Exception:
        pass
    
    await database.disconnect()
    ModelRegistry.clear()


@pytest.fixture
def models():
    """Create test models with relationships."""
    from aksara import Model, fields
    
    class TestTag(Model):
        __tablename__ = "test_tags"
        name = fields.String(max_length=50, unique=True)
    
    class TestArticle(Model):
        __tablename__ = "test_articles"
        title = fields.String(max_length=200)
        content = fields.Text(nullable=True)
        tags = fields.ManyToMany(TestTag, related_name="articles")
    
    class TestM2MUser(Model):
        __tablename__ = "test_m2m_users"
        email = fields.Email(unique=True)
        name = fields.String(max_length=100)
    
    class TestProfile(Model):
        __tablename__ = "test_profiles"
        bio = fields.Text(nullable=True)
        website = fields.URL(nullable=True)
        user = fields.OneToOne(TestM2MUser, related_name="profile")
    
    return {
        'Tag': TestTag,
        'Article': TestArticle,
        'User': TestM2MUser,
        'Profile': TestProfile,
    }


@pytest.fixture
async def setup_tables(db, models):
    """Create the test tables."""
    # Create tag table
    tag_sql = models['Tag'].get_create_table_sql()
    await db.execute(tag_sql)
    
    # Create article table
    article_sql = models['Article'].get_create_table_sql()
    await db.execute(article_sql)
    
    # Create M2M join table
    article_tags_field = models['Article']._m2m_fields['tags']
    join_sql = article_tags_field.get_join_table_sql()
    await db.execute(join_sql)
    
    # Create user table
    user_sql = models['User'].get_create_table_sql()
    await db.execute(user_sql)
    
    # Create profile table (with OneToOne to user)
    profile_sql = models['Profile'].get_create_table_sql()
    await db.execute(profile_sql)
    
    return models


class TestManyToManyBasics:
    """Basic ManyToMany operations."""
    
    @pytest.mark.asyncio
    async def test_create_article_without_tags(self, db, setup_tables):
        """Test creating an article without any tags."""
        models = setup_tables
        Article = models['Article']
        
        article = await Article.objects.create(
            title="First Article",
            content="Some content"
        )
        
        assert article.id is not None
        assert article.title == "First Article"
    
    @pytest.mark.asyncio
    async def test_add_single_tag(self, db, setup_tables):
        """Test adding a single tag to an article."""
        models = setup_tables
        Article = models['Article']
        Tag = models['Tag']
        
        # Create article and tag
        article = await Article.objects.create(title="Tagged Article")
        tag = await Tag.objects.create(name="python")
        
        # Add tag to article
        await article.tags.add(tag)
        
        # Verify
        tag_count = await article.tags.count()
        assert tag_count == 1
        
        all_tags = await article.tags.all()
        assert len(all_tags) == 1
        assert all_tags[0].name == "python"
    
    @pytest.mark.asyncio
    async def test_add_multiple_tags(self, db, setup_tables):
        """Test adding multiple tags at once."""
        models = setup_tables
        Article = models['Article']
        Tag = models['Tag']
        
        article = await Article.objects.create(title="Multi-tagged Article")
        tag1 = await Tag.objects.create(name="django")
        tag2 = await Tag.objects.create(name="fastapi")
        tag3 = await Tag.objects.create(name="async")
        
        # Add multiple tags
        await article.tags.add(tag1, tag2, tag3)
        
        tag_count = await article.tags.count()
        assert tag_count == 3
        
        tag_names = {t.name for t in await article.tags.all()}
        assert tag_names == {"django", "fastapi", "async"}
    
    @pytest.mark.asyncio
    async def test_remove_tag(self, db, setup_tables):
        """Test removing a tag from an article."""
        models = setup_tables
        Article = models['Article']
        Tag = models['Tag']
        
        article = await Article.objects.create(title="Article to untag")
        tag1 = await Tag.objects.create(name="keep")
        tag2 = await Tag.objects.create(name="remove")
        
        await article.tags.add(tag1, tag2)
        assert await article.tags.count() == 2
        
        # Remove one tag
        await article.tags.remove(tag2)
        
        assert await article.tags.count() == 1
        remaining = await article.tags.all()
        assert remaining[0].name == "keep"
    
    @pytest.mark.asyncio
    async def test_clear_tags(self, db, setup_tables):
        """Test clearing all tags from an article."""
        models = setup_tables
        Article = models['Article']
        Tag = models['Tag']
        
        article = await Article.objects.create(title="Article to clear")
        tag1 = await Tag.objects.create(name="tag1")
        tag2 = await Tag.objects.create(name="tag2")
        
        await article.tags.add(tag1, tag2)
        assert await article.tags.count() == 2
        
        # Clear all tags
        await article.tags.clear()
        
        assert await article.tags.count() == 0
    
    @pytest.mark.asyncio
    async def test_set_tags(self, db, setup_tables):
        """Test replacing all tags with a new set."""
        models = setup_tables
        Article = models['Article']
        Tag = models['Tag']
        
        article = await Article.objects.create(title="Article for set test")
        tag1 = await Tag.objects.create(name="old1")
        tag2 = await Tag.objects.create(name="old2")
        tag3 = await Tag.objects.create(name="new1")
        tag4 = await Tag.objects.create(name="new2")
        
        # Initial tags
        await article.tags.add(tag1, tag2)
        assert await article.tags.count() == 2
        
        # Replace with new tags
        await article.tags.set([tag3, tag4])
        
        assert await article.tags.count() == 2
        tag_names = {t.name for t in await article.tags.all()}
        assert tag_names == {"new1", "new2"}
    
    @pytest.mark.asyncio
    async def test_ids_method(self, db, setup_tables):
        """Test getting only IDs of related objects."""
        models = setup_tables
        Article = models['Article']
        Tag = models['Tag']
        
        article = await Article.objects.create(title="Article for IDs")
        tag1 = await Tag.objects.create(name="id-tag1")
        tag2 = await Tag.objects.create(name="id-tag2")
        
        await article.tags.add(tag1, tag2)
        
        tag_ids = await article.tags.ids()
        assert len(tag_ids) == 2
        assert tag1.id in tag_ids
        assert tag2.id in tag_ids


class TestManyToManyEdgeCases:
    """Edge cases for ManyToMany operations."""
    
    @pytest.mark.asyncio
    async def test_add_same_tag_twice(self, db, setup_tables):
        """Test that adding the same tag twice doesn't duplicate."""
        models = setup_tables
        Article = models['Article']
        Tag = models['Tag']
        
        article = await Article.objects.create(title="No duplicates")
        tag = await Tag.objects.create(name="unique-tag")
        
        await article.tags.add(tag)
        await article.tags.add(tag)  # Add again
        
        # Should still only be 1
        assert await article.tags.count() == 1
    
    @pytest.mark.asyncio
    async def test_remove_nonexistent_tag(self, db, setup_tables):
        """Test removing a tag that wasn't added."""
        models = setup_tables
        Article = models['Article']
        Tag = models['Tag']
        
        article = await Article.objects.create(title="Remove test")
        tag1 = await Tag.objects.create(name="added")
        tag2 = await Tag.objects.create(name="not-added")
        
        await article.tags.add(tag1)
        
        # Remove a tag that wasn't added - should not error
        await article.tags.remove(tag2)
        
        # Original tag should still be there
        assert await article.tags.count() == 1
    
    @pytest.mark.asyncio
    async def test_set_empty_list(self, db, setup_tables):
        """Test setting to empty list clears all tags."""
        models = setup_tables
        Article = models['Article']
        Tag = models['Tag']
        
        article = await Article.objects.create(title="Clear via set")
        tag = await Tag.objects.create(name="to-clear")
        
        await article.tags.add(tag)
        assert await article.tags.count() == 1
        
        # Set to empty list
        await article.tags.set([])
        
        assert await article.tags.count() == 0


class TestOneToOneRelationship:
    """Tests for OneToOne field."""
    
    @pytest.mark.asyncio
    async def test_create_profile_for_user(self, db, setup_tables):
        """Test creating a profile linked to a user."""
        models = setup_tables
        User = models['User']
        Profile = models['Profile']
        
        user = await User.objects.create(
            email="test@example.com",
            name="Test User"
        )
        
        profile = await Profile.objects.create(
            bio="A test bio",
            website="https://example.com",
            user_id=user.id
        )
        
        assert profile.id is not None
        assert profile.user_id == user.id
    
    @pytest.mark.asyncio
    async def test_one_to_one_is_unique(self, db, setup_tables):
        """Test that OneToOne enforces uniqueness."""
        models = setup_tables
        User = models['User']
        Profile = models['Profile']
        
        user = await User.objects.create(
            email="unique@example.com",
            name="Unique User"
        )
        
        # First profile - should succeed
        await Profile.objects.create(
            bio="First profile",
            user_id=user.id
        )
        
        # Second profile for same user - should fail
        with pytest.raises(Exception):  # Should be UniqueConstraintError
            await Profile.objects.create(
                bio="Second profile",
                user_id=user.id
            )


class TestNewFieldTypesIntegration:
    """Integration tests for new field types."""
    
    @pytest.mark.asyncio
    async def test_email_field_stores_lowercase(self, db, setup_tables):
        """Test Email field normalizes to lowercase."""
        models = setup_tables
        User = models['User']
        
        user = await User.objects.create(
            email="Test.User@EXAMPLE.COM",
            name="Test"
        )
        
        # Fetch it back
        fetched = await User.objects.get(id=user.id)
        assert fetched.email == "test.user@example.com"
    
    @pytest.mark.asyncio
    async def test_url_field_storage(self, db, setup_tables):
        """Test URL field stores and retrieves correctly."""
        models = setup_tables
        User = models['User']
        Profile = models['Profile']
        
        user = await User.objects.create(
            email="url.test@example.com",
            name="URL Tester"
        )
        
        profile = await Profile.objects.create(
            bio="Test bio",
            website="https://github.com/user",
            user_id=user.id
        )
        
        fetched = await Profile.objects.get(id=profile.id)
        assert fetched.website == "https://github.com/user"
    
    @pytest.mark.asyncio
    async def test_text_field_stores_long_content(self, db, setup_tables):
        """Test Text field can store long content."""
        models = setup_tables
        Article = models['Article']
        
        long_content = "Lorem ipsum " * 1000  # ~12000 characters
        
        article = await Article.objects.create(
            title="Long Article",
            content=long_content
        )
        
        fetched = await Article.objects.get(id=article.id)
        assert fetched.content == long_content
