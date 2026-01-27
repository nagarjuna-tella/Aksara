"""
Tests for Query Capture Utility

Tests for the capture_queries() context manager and QueryLog class.
"""

import os
import pytest

from aksara.db.debug import (
    QueryEvent,
    QueryLog,
    capture_queries,
    get_active_query_log,
    log_query,
)


class TestQueryEvent:
    """Tests for QueryEvent dataclass."""
    
    def test_creation(self):
        event = QueryEvent(sql="SELECT * FROM users", params=("value",))
        
        assert event.sql == "SELECT * FROM users"
        assert event.params == ("value",)
        assert event.duration_ms is None
    
    def test_repr_short_sql(self):
        event = QueryEvent(sql="SELECT * FROM users")
        
        repr_str = repr(event)
        assert "SELECT * FROM users" in repr_str
    
    def test_repr_long_sql_truncates(self):
        long_sql = "SELECT " + "x," * 50 + "y FROM users"
        event = QueryEvent(sql=long_sql)
        
        repr_str = repr(event)
        assert "..." in repr_str
        assert len(repr_str) < len(long_sql) + 50


class TestQueryLog:
    """Tests for QueryLog class."""
    
    def test_empty_log(self):
        log = QueryLog()
        
        assert log.count == 0
        assert log.queries == []
    
    def test_add_query(self):
        log = QueryLog()
        log.add("SELECT * FROM users", ("param1",))
        
        assert log.count == 1
        assert log.queries[0].sql == "SELECT * FROM users"
        assert log.queries[0].params == ("param1",)
    
    def test_multiple_queries(self):
        log = QueryLog()
        log.add("SELECT * FROM users")
        log.add("SELECT * FROM posts")
        log.add("INSERT INTO logs VALUES ($1)")
        
        assert log.count == 3
    
    def test_clear(self):
        log = QueryLog()
        log.add("SELECT 1")
        log.add("SELECT 2")
        log.clear()
        
        assert log.count == 0
    
    def test_filter_selects(self):
        log = QueryLog()
        log.add("SELECT * FROM users")
        log.add("INSERT INTO users VALUES ($1)")
        log.add("SELECT * FROM posts")
        log.add("UPDATE users SET name = $1")
        
        selects = log.filter_selects()
        
        assert len(selects) == 2
        assert all("SELECT" in q.sql.upper() for q in selects)
    
    def test_filter_inserts(self):
        log = QueryLog()
        log.add("SELECT * FROM users")
        log.add("INSERT INTO users VALUES ($1)")
        log.add("INSERT INTO posts VALUES ($1)")
        
        inserts = log.filter_inserts()
        
        assert len(inserts) == 2
    
    def test_filter_by_table(self):
        log = QueryLog()
        log.add("SELECT * FROM users")
        log.add("SELECT * FROM posts")
        log.add("SELECT * FROM users WHERE id = $1")
        
        user_queries = log.filter_by_table("users")
        
        assert len(user_queries) == 2
    
    def test_repr(self):
        log = QueryLog()
        log.add("SELECT 1")
        log.add("SELECT 2")
        
        assert "2 queries" in repr(log)


class TestLogQuery:
    """Tests for log_query function."""
    
    def test_log_query_when_no_active_log(self):
        # Should not raise when no log is active
        log_query("SELECT 1")
    
    def test_log_query_adds_to_active_log(self):
        log = QueryLog()
        
        # Manually set active log
        import aksara.db.debug as debug_module
        debug_module._active_query_log = log
        
        try:
            log_query("SELECT * FROM test", ("param",))
            
            assert log.count == 1
            assert log.queries[0].sql == "SELECT * FROM test"
        finally:
            debug_module._active_query_log = None


class TestGetActiveQueryLog:
    """Tests for get_active_query_log function."""
    
    def test_returns_none_when_no_active_log(self):
        import aksara.db.debug as debug_module
        debug_module._active_query_log = None
        
        assert get_active_query_log() is None


# Integration tests require DATABASE_URL
pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set"
)


@pytest.fixture
async def db():
    """Create database connection."""
    from aksara.db import Database
    from aksara.registry import ModelRegistry
    
    ModelRegistry.clear()
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set")
    
    database = Database(database_url)
    await database.connect()
    
    yield database
    
    # Clean up
    try:
        await database.execute("DROP TABLE IF EXISTS perf_users CASCADE")
    except Exception:
        pass
    
    await database.disconnect()
    ModelRegistry.clear()


@pytest.fixture
def perf_models():
    """Create models for perf tests."""
    from aksara import Model, fields
    from aksara.registry import ModelRegistry
    
    ModelRegistry.clear()
    
    class PerfUser(Model):
        __tablename__ = "perf_users"
        name = fields.String(max_length=100)
        email = fields.Email(unique=True)
    
    return {'User': PerfUser}


@pytest.fixture
async def setup_perf_tables(db, perf_models):
    """Create test tables."""
    await db.execute(perf_models['User'].get_create_table_sql())
    return perf_models


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
class TestCaptureQueriesIntegration:
    """Integration tests for capture_queries with real DB."""
    
    @pytest.mark.asyncio
    async def test_capture_create_query(self, db, setup_perf_tables):
        """Test that create operations are captured."""
        models = setup_perf_tables
        
        async with capture_queries() as log:
            user = await models['User'].objects.create(
                name="Test User",
                email="test@example.com"
            )
        
        assert log.count >= 1
        # Should have at least one INSERT
        inserts = log.filter_inserts()
        assert len(inserts) >= 1
    
    @pytest.mark.asyncio
    async def test_capture_filter_query(self, db, setup_perf_tables):
        """Test that filter operations are captured."""
        models = setup_perf_tables
        
        # Create a user first
        await models['User'].objects.create(
            name="Filter User",
            email="filter@example.com"
        )
        
        async with capture_queries() as log:
            users = await models['User'].objects.filter(name="Filter User").all()
        
        assert log.count >= 1
        selects = log.filter_selects()
        assert len(selects) >= 1
        assert "perf_users" in selects[0].sql.lower()
    
    @pytest.mark.asyncio
    async def test_capture_multiple_operations(self, db, setup_perf_tables):
        """Test capturing multiple operations."""
        models = setup_perf_tables
        
        async with capture_queries() as log:
            # Create
            user = await models['User'].objects.create(
                name="Multi User",
                email="multi@example.com"
            )
            # Filter
            users = await models['User'].objects.filter().all()
            # Count
            count = await models['User'].objects.count()
        
        # Should have captured multiple queries
        assert log.count >= 3
    
    @pytest.mark.asyncio
    async def test_nested_capture_queries(self, db, setup_perf_tables):
        """Test nested capture_queries contexts."""
        models = setup_perf_tables
        
        async with capture_queries() as outer_log:
            await models['User'].objects.create(
                name="Outer User",
                email="outer@example.com"
            )
            
            async with capture_queries() as inner_log:
                await models['User'].objects.filter().all()
            
            # Inner should only have the filter
            assert inner_log.count >= 1
            
            await models['User'].objects.count()
        
        # Outer should have create and count, but not the inner filter
        # (because inner context was active during filter)
        assert outer_log.count >= 2
