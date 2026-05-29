"""
Tests for Aksara v0.3.8 Relationships & Delete Semantics

Tests for:
- Reverse FK relations (user.posts.all())
- Reverse M2M relations (tag.posts.all())
- Reverse O2O relations (user.profile())
- on_delete policies (CASCADE, RESTRICT, SET_NULL)
- RestrictedError handling
"""

import os
import pytest
from uuid import UUID

from aksara.relations import (
    OnDelete,
    RelationMeta,
    RelationRegistry,
    ReverseFKManager,
    ReverseM2MManager,
    ReverseFKDescriptor,
    ReverseM2MDescriptor,
    ReverseO2ODescriptor,
    ReverseO2OAccessor,
    get_default_related_name,
    register_relation,
)
from aksara.exceptions import RestrictedError


class TestOnDeleteEnum:
    """Tests for OnDelete enum."""
    
    def test_cascade_value(self):
        assert OnDelete.CASCADE.value == "CASCADE"
    
    def test_set_null_value(self):
        assert OnDelete.SET_NULL.value == "SET NULL"
    
    def test_restrict_value(self):
        assert OnDelete.RESTRICT.value == "RESTRICT"
    
    def test_protect_is_alias(self):
        assert OnDelete.PROTECT.value == OnDelete.RESTRICT.value
    
    def test_str_representation(self):
        assert str(OnDelete.CASCADE) == "CASCADE"
        assert str(OnDelete.SET_NULL) == "SET NULL"


class TestRelationMeta:
    """Tests for RelationMeta class."""
    
    @pytest.fixture
    def mock_models(self):
        """Create mock models for testing."""
        from aksara import Model, fields
        
        class MockUser(Model):
            __tablename__ = "mock_users"
            name = fields.String(max_length=100)
        
        class MockPost(Model):
            __tablename__ = "mock_posts"
            title = fields.String(max_length=200)
            author = fields.ForeignKey(MockUser)
        
        return {'User': MockUser, 'Post': MockPost}
    
    def test_fk_relation_meta(self, mock_models):
        meta = RelationMeta(
            relation_type="fk",
            source_model=mock_models['Post'],
            target_model=mock_models['User'],
            field_name="author",
            related_name="posts",
            on_delete="CASCADE",
        )
        
        assert meta.relation_type == "fk"
        assert meta.source_model == mock_models['Post']
        assert meta.target_model == mock_models['User']
        assert meta.field_name == "author"
        assert meta.related_name == "posts"
        assert meta.on_delete == "CASCADE"
    
    def test_source_table_property(self, mock_models):
        meta = RelationMeta(
            relation_type="fk",
            source_model=mock_models['Post'],
            target_model=mock_models['User'],
            field_name="author",
            related_name="posts",
        )
        
        assert meta.source_table == "mock_posts"
    
    def test_target_table_property(self, mock_models):
        meta = RelationMeta(
            relation_type="fk",
            source_model=mock_models['Post'],
            target_model=mock_models['User'],
            field_name="author",
            related_name="posts",
        )
        
        assert meta.target_table == "mock_users"
    
    def test_to_dict(self, mock_models):
        meta = RelationMeta(
            relation_type="m2m",
            source_model=mock_models['Post'],
            target_model=mock_models['User'],
            field_name="tags",
            related_name="posts",
            through_table="posts_tags",
        )
        
        result = meta.to_dict()
        
        assert result["type"] == "m2m"
        assert result["source_model"] == "MockPost"
        assert result["target_model"] == "MockUser"
        assert result["field_name"] == "tags"
        assert result["related_name"] == "posts"
        assert result["through_table"] == "posts_tags"


class TestRelationRegistry:
    """Tests for RelationRegistry class."""
    
    def setup_method(self):
        """Clear registry before each test."""
        RelationRegistry.clear()
    
    def teardown_method(self):
        """Clear registry after each test."""
        RelationRegistry.clear()
    
    @pytest.fixture
    def mock_models(self):
        from aksara import Model, fields
        from aksara.registry import ModelRegistry
        
        ModelRegistry.clear()
        
        class RegistryUser(Model):
            __tablename__ = "registry_users"
            name = fields.String(max_length=100)
        
        class RegistryPost(Model):
            __tablename__ = "registry_posts"
            title = fields.String(max_length=200)
        
        return {'User': RegistryUser, 'Post': RegistryPost}
    
    def test_register_relation(self, mock_models):
        meta = RelationMeta(
            relation_type="fk",
            source_model=mock_models['Post'],
            target_model=mock_models['User'],
            field_name="author",
            related_name="posts",
        )
        
        RelationRegistry.register(meta)
        
        assert len(RelationRegistry.all()) == 1
        assert RelationRegistry.all()[0] == meta
    
    def test_get_relations_to(self, mock_models):
        meta = RelationMeta(
            relation_type="fk",
            source_model=mock_models['Post'],
            target_model=mock_models['User'],
            field_name="author",
            related_name="posts",
        )
        
        RelationRegistry.register(meta)
        
        relations = RelationRegistry.get_relations_to(mock_models['User'])
        
        assert len(relations) == 1
        assert relations[0].source_model == mock_models['Post']
    
    def test_get_relations_from(self, mock_models):
        meta = RelationMeta(
            relation_type="fk",
            source_model=mock_models['Post'],
            target_model=mock_models['User'],
            field_name="author",
            related_name="posts",
        )
        
        RelationRegistry.register(meta)
        
        relations = RelationRegistry.get_relations_from(mock_models['Post'])
        
        assert len(relations) == 1
        assert relations[0].target_model == mock_models['User']
    
    def test_clear(self, mock_models):
        meta = RelationMeta(
            relation_type="fk",
            source_model=mock_models['Post'],
            target_model=mock_models['User'],
            field_name="author",
            related_name="posts",
        )
        
        RelationRegistry.register(meta)
        RelationRegistry.clear()
        
        assert len(RelationRegistry.all()) == 0


class TestDefaultRelatedName:
    """Tests for related name generation."""
    
    @pytest.fixture
    def mock_models(self):
        from aksara import Model, fields
        from aksara.registry import ModelRegistry
        
        ModelRegistry.clear()
        
        class RelatedNameUser(Model):
            __tablename__ = "related_users"
            name = fields.String(max_length=100)
        
        class RelatedNamePost(Model):
            __tablename__ = "related_posts"
            title = fields.String(max_length=200)
        
        class RelatedNameProfile(Model):
            __tablename__ = "related_profiles"
            bio = fields.Text(nullable=True)
        
        return {
            'User': RelatedNameUser,
            'Post': RelatedNamePost,
            'Profile': RelatedNameProfile,
        }
    
    def test_fk_default_related_name(self, mock_models):
        name = get_default_related_name(mock_models['Post'], "fk")
        assert name == "relatednamepost_set"
    
    def test_m2m_default_related_name(self, mock_models):
        name = get_default_related_name(mock_models['Post'], "m2m")
        assert name == "relatednamepost_set"
    
    def test_o2o_default_related_name(self, mock_models):
        # O2O uses singular
        name = get_default_related_name(mock_models['Profile'], "o2o")
        assert name == "relatednameprofile"


class TestRestrictedError:
    """Tests for RestrictedError exception."""
    
    def test_creation(self):
        error = RestrictedError(model_name="User", related_model="Post", related_count=5)
        
        assert error.model_name == "User"
        assert error.related_model == "Post"
        assert error.related_count == 5
    
    def test_message(self):
        error = RestrictedError(model_name="User", related_model="Post", related_count=5)
        
        message = str(error)
        assert "User" in message or "Post" in message


class TestDescriptors:
    """Tests for reverse relation descriptors."""
    
    @pytest.fixture
    def mock_models_and_relation(self):
        from aksara import Model, fields
        from aksara.registry import ModelRegistry
        
        ModelRegistry.clear()
        RelationRegistry.clear()
        
        class DescUser(Model):
            __tablename__ = "desc_users"
            name = fields.String(max_length=100)
        
        class DescPost(Model):
            __tablename__ = "desc_posts"
            title = fields.String(max_length=200)
        
        meta = RelationMeta(
            relation_type="fk",
            source_model=DescPost,
            target_model=DescUser,
            field_name="author",
            related_name="posts",
            on_delete="CASCADE",
        )
        
        return {
            'User': DescUser,
            'Post': DescPost,
            'relation': meta,
        }
    
    def test_reverse_fk_descriptor_returns_self_on_class(self, mock_models_and_relation):
        descriptor = ReverseFKDescriptor(mock_models_and_relation['relation'])
        
        result = descriptor.__get__(None, mock_models_and_relation['User'])
        
        assert result is descriptor
    
    def test_reverse_fk_descriptor_returns_manager_on_instance(self, mock_models_and_relation):
        descriptor = ReverseFKDescriptor(mock_models_and_relation['relation'])
        
        # Create mock instance
        from uuid import uuid4
        instance = mock_models_and_relation['User']()
        instance._data = {'id': uuid4()}
        instance._is_new = False
        
        result = descriptor.__get__(instance, mock_models_and_relation['User'])
        
        assert isinstance(result, ReverseFKManager)


class TestReverseO2OAccessor:
    """Tests for ReverseO2OAccessor."""
    
    @pytest.fixture
    def mock_models_and_relation(self):
        from aksara import Model, fields
        from aksara.registry import ModelRegistry
        
        ModelRegistry.clear()
        RelationRegistry.clear()
        
        class O2OUser(Model):
            __tablename__ = "o2o_users"
            name = fields.String(max_length=100)
        
        class O2OProfile(Model):
            __tablename__ = "o2o_profiles"
            bio = fields.Text(nullable=True)
            user = fields.OneToOne(O2OUser)
        
        meta = RelationMeta(
            relation_type="o2o",
            source_model=O2OProfile,
            target_model=O2OUser,
            field_name="user",
            related_name="profile",
            on_delete="CASCADE",
        )
        
        return {
            'User': O2OUser,
            'Profile': O2OProfile,
            'relation': meta,
        }
    
    def test_accessor_repr(self, mock_models_and_relation):
        from uuid import uuid4
        
        instance = mock_models_and_relation['User']()
        instance._data = {'id': uuid4()}
        instance._is_new = False
        
        accessor = ReverseO2OAccessor(mock_models_and_relation['relation'], instance)
        
        repr_str = repr(accessor)
        assert "O2OProfile" in repr_str
        assert "user" in repr_str


# Integration tests (require DATABASE_URL)
pytestmark_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set"
)


@pytest.fixture
async def db():
    """Create database connection and clean up tables."""
    from aksara.db import Database
    from aksara.registry import ModelRegistry
    
    ModelRegistry.clear()
    RelationRegistry.clear()
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set")
    
    database = Database(database_url)
    await database.connect()
    
    yield database
    
    # Clean up tables
    try:
        await database.execute("DROP TABLE IF EXISTS v038_posts CASCADE")
        await database.execute("DROP TABLE IF EXISTS v038_users CASCADE")
        await database.execute("DROP TABLE IF EXISTS v038_profiles CASCADE")
        await database.execute("DROP TABLE IF EXISTS v038_articles_tags CASCADE")
        await database.execute("DROP TABLE IF EXISTS v038_articles CASCADE")
        await database.execute("DROP TABLE IF EXISTS v038_tags CASCADE")
    except Exception:
        pass
    
    await database.disconnect()
    ModelRegistry.clear()
    RelationRegistry.clear()


@pytest.fixture
def relation_models():
    """Create models for relation tests."""
    from aksara import Model, fields
    from aksara.registry import ModelRegistry
    
    ModelRegistry.clear()
    RelationRegistry.clear()
    
    class V038User(Model):
        __tablename__ = "v038_users"
        name = fields.String(max_length=100)
        email = fields.Email(unique=True)
    
    class V038Post(Model):
        __tablename__ = "v038_posts"
        title = fields.String(max_length=200)
        content = fields.Text(nullable=True)
        author = fields.ForeignKey(V038User, related_name="posts")
    
    class V038Profile(Model):
        __tablename__ = "v038_profiles"
        bio = fields.Text(nullable=True)
        website = fields.URL(nullable=True)
        user = fields.OneToOne(V038User, related_name="profile")
    
    class V038Tag(Model):
        __tablename__ = "v038_tags"
        name = fields.String(max_length=50, unique=True)
    
    class V038Article(Model):
        __tablename__ = "v038_articles"
        title = fields.String(max_length=200)
        tags = fields.ManyToMany(V038Tag, related_name="articles")
    
    return {
        'User': V038User,
        'Post': V038Post,
        'Profile': V038Profile,
        'Tag': V038Tag,
        'Article': V038Article,
    }


@pytest.fixture
async def setup_relation_tables(db, relation_models):
    """Create the test tables."""
    from aksara.model.base import finalize_relations
    
    # Create tables
    await db.execute(relation_models['User'].get_create_table_sql())
    await db.execute(relation_models['Post'].get_create_table_sql())
    await db.execute(relation_models['Profile'].get_create_table_sql())
    await db.execute(relation_models['Tag'].get_create_table_sql())
    await db.execute(relation_models['Article'].get_create_table_sql())
    
    # Create M2M join table
    m2m_field = relation_models['Article']._m2m_fields['tags']
    await db.execute(m2m_field.get_join_table_sql())
    
    # Finalize relations to attach descriptors
    finalize_relations()
    
    return relation_models


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
class TestReverseFKIntegration:
    """Integration tests for reverse FK relations."""
    
    @pytest.mark.asyncio
    async def test_reverse_fk_all(self, db, setup_relation_tables):
        """Test user.posts.all() returns related posts."""
        models = setup_relation_tables
        
        # Create user
        user = models['User'](name="John Doe", email="john@example.com")
        await user.save()
        
        # Create posts for the user
        post1 = models['Post'](title="First Post", author_id=user.id)
        await post1.save()
        
        post2 = models['Post'](title="Second Post", author_id=user.id)
        await post2.save()
        
        # Get posts via reverse relation
        posts = await user.posts.all()
        
        assert len(posts) == 2
        assert all(isinstance(p, models['Post']) for p in posts)
        titles = {p.title for p in posts}
        assert "First Post" in titles
        assert "Second Post" in titles
    
    @pytest.mark.asyncio
    async def test_reverse_fk_count(self, db, setup_relation_tables):
        """Test user.posts.count() returns correct count."""
        models = setup_relation_tables
        
        # Create user
        user = models['User'](name="Jane Doe", email="jane@example.com")
        await user.save()
        
        # Create 3 posts
        for i in range(3):
            post = models['Post'](title=f"Post {i}", author_id=user.id)
            await post.save()
        
        count = await user.posts.count()
        
        assert count == 3

    @pytest.mark.asyncio
    async def test_reverse_fk_filter(self, db, setup_relation_tables):
        """Test user.posts.filter() applies the parent FK and extra filters."""
        models = setup_relation_tables

        user = models['User'](name="Filter User", email="filter@example.com")
        await user.save()
        other_user = models['User'](name="Other User", email="other@example.com")
        await other_user.save()

        first = models['Post'](title="Match", author_id=user.id)
        await first.save()
        second = models['Post'](title="Skip", author_id=user.id)
        await second.save()
        other = models['Post'](title="Match", author_id=other_user.id)
        await other.save()

        posts = await user.posts.filter(title="Match")

        assert [post.id for post in posts] == [first.id]
    
    @pytest.mark.asyncio
    async def test_reverse_fk_empty(self, db, setup_relation_tables):
        """Test user.posts.all() returns empty list for user with no posts."""
        models = setup_relation_tables
        
        user = models['User'](name="No Posts User", email="noposts@example.com")
        await user.save()
        
        posts = await user.posts.all()
        
        assert posts == []
        
        count = await user.posts.count()
        assert count == 0


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
class TestReverseO2OIntegration:
    """Integration tests for reverse OneToOne relations."""
    
    @pytest.mark.asyncio
    async def test_reverse_o2o_call(self, db, setup_relation_tables):
        """Test user.profile() returns related profile."""
        models = setup_relation_tables
        
        # Create user
        user = models['User'](name="Profile User", email="profile@example.com")
        await user.save()
        
        # Create profile
        profile = models['Profile'](
            bio="Test bio",
            website="https://example.com",
            user_id=user.id
        )
        await profile.save()
        
        # Get profile via reverse relation
        result = await user.profile()
        
        assert result is not None
        assert isinstance(result, models['Profile'])
        assert result.bio == "Test bio"
    
    @pytest.mark.asyncio
    async def test_reverse_o2o_none(self, db, setup_relation_tables):
        """Test user.profile() returns None when no profile exists."""
        models = setup_relation_tables
        
        user = models['User'](name="No Profile User", email="noprofile@example.com")
        await user.save()
        
        result = await user.profile()
        
        assert result is None


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
class TestReverseM2MIntegration:
    """Integration tests for reverse ManyToMany relations."""
    
    @pytest.mark.asyncio
    async def test_reverse_m2m_all(self, db, setup_relation_tables):
        """Test tag.articles.all() returns related articles."""
        models = setup_relation_tables
        
        # Create tag
        tag = models['Tag'](name="Python")
        await tag.save()
        
        # Create articles and add tag
        article1 = models['Article'](title="Python Basics")
        await article1.save()
        await article1.tags.add(tag)
        
        article2 = models['Article'](title="Advanced Python")
        await article2.save()
        await article2.tags.add(tag)
        
        # Get articles via reverse relation
        articles = await tag.articles.all()
        
        assert len(articles) == 2
        assert all(isinstance(a, models['Article']) for a in articles)
        titles = {a.title for a in articles}
        assert "Python Basics" in titles
        assert "Advanced Python" in titles
    
    @pytest.mark.asyncio
    async def test_reverse_m2m_count(self, db, setup_relation_tables):
        """Test tag.articles.count() returns correct count."""
        models = setup_relation_tables
        
        tag = models['Tag'](name="JavaScript")
        await tag.save()
        
        for i in range(4):
            article = models['Article'](title=f"JS Article {i}")
            await article.save()
            await article.tags.add(tag)
        
        count = await tag.articles.count()
        
        assert count == 4


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
class TestOnDeletePoliciesIntegration:
    """Integration tests for on_delete policies."""
    
    @pytest.fixture
    def on_delete_models(self):
        """Create models with different on_delete policies."""
        from aksara import Model, fields
        from aksara.registry import ModelRegistry
        
        ModelRegistry.clear()
        RelationRegistry.clear()
        
        class OnDeleteAuthor(Model):
            __tablename__ = "v038_od_authors"
            name = fields.String(max_length=100)
        
        class OnDeletePostCascade(Model):
            __tablename__ = "v038_od_posts_cascade"
            title = fields.String(max_length=200)
            author = fields.ForeignKey(
                OnDeleteAuthor, 
                on_delete="CASCADE",
                related_name="cascade_posts"
            )
        
        class OnDeletePostRestrict(Model):
            __tablename__ = "v038_od_posts_restrict"
            title = fields.String(max_length=200)
            author = fields.ForeignKey(
                OnDeleteAuthor, 
                on_delete="RESTRICT",
                related_name="restrict_posts"
            )
        
        class OnDeletePostSetNull(Model):
            __tablename__ = "v038_od_posts_setnull"
            title = fields.String(max_length=200)
            author = fields.ForeignKey(
                OnDeleteAuthor, 
                on_delete="SET NULL",
                nullable=True,
                related_name="setnull_posts"
            )
        
        return {
            'Author': OnDeleteAuthor,
            'CascadePost': OnDeletePostCascade,
            'RestrictPost': OnDeletePostRestrict,
            'SetNullPost': OnDeletePostSetNull,
        }
    
    @pytest.fixture
    async def setup_on_delete_tables(self, db, on_delete_models):
        """Create on_delete test tables."""
        from aksara.model.base import finalize_relations
        
        # Clean up first
        try:
            await db.execute("DROP TABLE IF EXISTS v038_od_posts_setnull CASCADE")
            await db.execute("DROP TABLE IF EXISTS v038_od_posts_restrict CASCADE")
            await db.execute("DROP TABLE IF EXISTS v038_od_posts_cascade CASCADE")
            await db.execute("DROP TABLE IF EXISTS v038_od_authors CASCADE")
        except Exception:
            pass
        
        await db.execute(on_delete_models['Author'].get_create_table_sql())
        await db.execute(on_delete_models['CascadePost'].get_create_table_sql())
        await db.execute(on_delete_models['RestrictPost'].get_create_table_sql())
        await db.execute(on_delete_models['SetNullPost'].get_create_table_sql())
        
        finalize_relations()
        
        return on_delete_models
    
    @pytest.mark.asyncio
    async def test_restrict_prevents_delete(self, db, setup_on_delete_tables):
        """Test RESTRICT on_delete prevents deletion with dependencies."""
        models = setup_on_delete_tables
        
        # Create author
        author = models['Author'](name="Author to Restrict")
        await author.save()
        
        # Create post with RESTRICT
        post = models['RestrictPost'](title="Restrict Post", author_id=author.id)
        await post.save()
        
        # Attempting to delete author should raise RestrictedError
        with pytest.raises(RestrictedError) as exc_info:
            await author.delete()
        
        assert exc_info.value.model_name == "OnDeleteAuthor"
        assert exc_info.value.related_model == "OnDeletePostRestrict"
        assert exc_info.value.related_count == 1
    
    @pytest.mark.asyncio
    async def test_set_null_clears_fk(self, db, setup_on_delete_tables):
        """Test SET_NULL on_delete sets FK to NULL."""
        models = setup_on_delete_tables
        
        # Create author
        author = models['Author'](name="Author for SetNull")
        await author.save()
        author_id = author.id
        
        # Create post with SET_NULL
        post = models['SetNullPost'](title="SetNull Post", author_id=author.id)
        await post.save()
        post_id = post.id
        
        # Delete author - should set FK to NULL
        await author.delete()
        
        # Verify post still exists but FK is NULL
        updated_post = await models['SetNullPost'].objects.get(id=post_id)
        assert updated_post.author_id is None
    
    @pytest.mark.asyncio
    async def test_delete_without_dependencies(self, db, setup_on_delete_tables):
        """Test delete succeeds when no dependencies exist."""
        models = setup_on_delete_tables
        
        # Create author without any posts
        author = models['Author'](name="Author without Posts")
        await author.save()
        author_id = author.id
        
        # Delete should succeed
        await author.delete()
        
        # Verify author is deleted
        with pytest.raises(Exception):  # DoesNotExist
            await models['Author'].objects.get(id=author_id)
