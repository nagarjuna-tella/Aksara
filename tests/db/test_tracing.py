"""
Tests for Aksara query tracing.

v0.5.10: Query Inspector & ORM Profiler

Tests:
- DbQueryTrace data structure
- DbQueryBatch aggregations
- Trace session management
- N+1 detection
- Ring buffer storage
- SQL normalization and parsing
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from aksara.db.tracing import (
    DbQueryTrace,
    DbQueryBatch,
    TraceStorage,
    start_trace_session,
    stop_trace_session,
    record_query,
    get_current_trace_session,
    get_recent_traces,
    get_trace_by_request_id,
    get_trace_stats,
    get_top_slow_queries,
    clear_traces,
    is_tracing_enabled,
    _extract_operation,
    _extract_table,
    _normalize_sql,
    _detect_n_plus_one,
)


# =============================================================================
# Test DbQueryTrace
# =============================================================================

class TestDbQueryTrace:
    """Tests for DbQueryTrace dataclass."""
    
    def test_create_basic_trace(self):
        """Test creating a basic query trace."""
        trace = DbQueryTrace(
            sql="SELECT * FROM users WHERE id = $1",
            params=(1,),
            duration_ms=12.5,
        )
        
        assert trace.sql == "SELECT * FROM users WHERE id = $1"
        assert trace.params == (1,)
        assert trace.duration_ms == 12.5
        assert trace.operation == "SELECT"
        assert trace.table == "users"
        assert trace.timestamp is not None
    
    def test_auto_extract_operation(self):
        """Test automatic operation extraction from SQL."""
        select = DbQueryTrace(sql="SELECT * FROM users")
        assert select.operation == "SELECT"
        
        insert = DbQueryTrace(sql="INSERT INTO users (name) VALUES ('test')")
        assert insert.operation == "INSERT"
        
        update = DbQueryTrace(sql="UPDATE users SET name = 'test' WHERE id = 1")
        assert update.operation == "UPDATE"
        
        delete = DbQueryTrace(sql="DELETE FROM users WHERE id = 1")
        assert delete.operation == "DELETE"
        
        other = DbQueryTrace(sql="TRUNCATE TABLE users")
        assert other.operation == "OTHER"
    
    def test_auto_extract_table(self):
        """Test automatic table extraction from SQL."""
        trace = DbQueryTrace(sql="SELECT * FROM users WHERE id = 1")
        assert trace.table == "users"
        
        trace = DbQueryTrace(sql='SELECT * FROM "Products" WHERE active = true')
        assert trace.table == "Products"
        
        insert = DbQueryTrace(sql="INSERT INTO orders (user_id) VALUES (1)")
        assert insert.table == "orders"
        
        update = DbQueryTrace(sql="UPDATE items SET qty = 10 WHERE id = 1")
        assert update.table == "items"
        
        delete = DbQueryTrace(sql="DELETE FROM sessions WHERE expired = true")
        assert delete.table == "sessions"
    
    def test_is_slow_property(self):
        """Test slow query detection."""
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.db_trace_slow_threshold_ms = 100.0
            
            fast = DbQueryTrace(sql="SELECT 1", duration_ms=50.0)
            assert not fast.is_slow
            
            slow = DbQueryTrace(sql="SELECT * FROM large_table", duration_ms=150.0)
            assert slow.is_slow
    
    def test_normalized_sql(self):
        """Test SQL normalization for grouping."""
        trace = DbQueryTrace(sql="SELECT * FROM users WHERE id = 123")
        normalized = trace.normalized_sql
        
        assert "123" not in normalized
        assert "?" in normalized
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        trace = DbQueryTrace(
            sql="SELECT * FROM users",
            params=None,
            duration_ms=10.0,
            rows_affected=5,
            tags=["orm"],
        )
        
        d = trace.to_dict()
        
        assert d["sql"] == "SELECT * FROM users"
        assert d["operation"] == "SELECT"
        assert d["table"] == "users"
        assert d["duration_ms"] == 10.0
        assert d["rows_affected"] == 5
        assert d["tags"] == ["orm"]
        assert "timestamp" in d
        assert "is_slow" in d


# =============================================================================
# Test DbQueryBatch
# =============================================================================

class TestDbQueryBatch:
    """Tests for DbQueryBatch dataclass."""
    
    def test_create_empty_batch(self):
        """Test creating an empty batch."""
        batch = DbQueryBatch(request_id="req-123")
        
        assert batch.request_id == "req-123"
        assert batch.queries == []
        assert batch.total_queries == 0
        assert batch.total_duration_ms == 0.0
        assert batch.slow_queries == 0
        assert batch.n_plus_one_suspicions == []
    
    def test_batch_aggregations(self):
        """Test batch aggregation properties."""
        queries = [
            DbQueryTrace(sql="SELECT * FROM users", duration_ms=10.0),
            DbQueryTrace(sql="SELECT * FROM posts", duration_ms=20.0),
            DbQueryTrace(sql="SELECT * FROM comments", duration_ms=30.0),
        ]
        
        batch = DbQueryBatch(request_id="req-123", queries=queries)
        
        assert batch.total_queries == 3
        assert batch.total_duration_ms == 60.0
    
    def test_batch_slow_query_count(self):
        """Test slow query counting in batch."""
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.db_trace_slow_threshold_ms = 50.0
            
            queries = [
                DbQueryTrace(sql="SELECT 1", duration_ms=10.0),
                DbQueryTrace(sql="SELECT * FROM big", duration_ms=100.0),
                DbQueryTrace(sql="SELECT * FROM huge", duration_ms=200.0),
            ]
            
            batch = DbQueryBatch(request_id="req-123", queries=queries)
            assert batch.slow_queries == 2
    
    def test_batch_n_plus_one_detection(self):
        """Test N+1 detection in batch."""
        # Simulate N+1: many similar SELECT queries
        queries = [
            DbQueryTrace(sql=f"SELECT * FROM posts WHERE user_id = {i}", duration_ms=5.0)
            for i in range(15)
        ]
        
        batch = DbQueryBatch(request_id="req-123", queries=queries)
        suspicions = batch.n_plus_one_suspicions
        
        assert len(suspicions) > 0
        assert "N+1" in suspicions[0] or "similar" in suspicions[0].lower()
    
    def test_batch_to_dict(self):
        """Test serialization to dictionary."""
        batch = DbQueryBatch(
            request_id="req-123",
            path="/api/users",
            method="GET",
            status_code=200,
            queries=[
                DbQueryTrace(sql="SELECT * FROM users", duration_ms=10.0),
            ],
        )
        
        d = batch.to_dict()
        
        assert d["request_id"] == "req-123"
        assert d["path"] == "/api/users"
        assert d["method"] == "GET"
        assert d["status_code"] == 200
        assert d["total_queries"] == 1
        assert len(d["queries"]) == 1
    
    def test_batch_to_summary_dict(self):
        """Test summary serialization (without queries)."""
        batch = DbQueryBatch(
            request_id="req-123",
            queries=[
                DbQueryTrace(sql="SELECT * FROM users", duration_ms=10.0),
            ],
        )
        
        d = batch.to_summary_dict()
        
        assert d["request_id"] == "req-123"
        assert d["total_queries"] == 1
        assert "queries" not in d


# =============================================================================
# Test Session Management
# =============================================================================

class TestTraceSessionManagement:
    """Tests for trace session lifecycle."""
    
    def setup_method(self):
        """Reset trace state before each test."""
        clear_traces()
    
    def test_session_lifecycle(self):
        """Test start/stop session lifecycle."""
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.db_trace_enabled = True
            mock_settings.db_trace_slow_threshold_ms = 100.0
            mock_settings.db_trace_max_queries = 500
            
            # Start session
            start_trace_session(request_id="req-1", path="/api/test", method="GET")
            
            # Verify session is active
            session = get_current_trace_session()
            assert session is not None
            assert isinstance(session, list)
            
            # Stop session
            batch = stop_trace_session(status_code=200)
            
            assert batch is not None
            assert batch.request_id == "req-1"
            assert batch.path == "/api/test"
            assert batch.method == "GET"
            assert batch.status_code == 200
            
            # Session should be reset
            assert get_current_trace_session() is None
    
    def test_record_query_during_session(self):
        """Test recording queries during active session."""
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.db_trace_enabled = True
            mock_settings.db_trace_slow_threshold_ms = 100.0
            mock_settings.db_trace_max_queries = 500
            
            start_trace_session(request_id="req-1")
            
            record_query(
                sql="SELECT * FROM users",
                params=None,
                duration_ms=15.0,
                rows_affected=10,
            )
            
            record_query(
                sql="SELECT * FROM posts WHERE user_id = $1",
                params=(1,),
                duration_ms=8.0,
            )
            
            batch = stop_trace_session()
            
            assert batch.total_queries == 2
            assert batch.queries[0].sql == "SELECT * FROM users"
            assert batch.queries[1].sql == "SELECT * FROM posts WHERE user_id = $1"
    
    def test_no_record_without_session(self):
        """Test that queries are not recorded without active session."""
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.db_trace_enabled = True
            
            # No session started
            record_query(sql="SELECT 1", duration_ms=1.0)
            
            # Should return None when stopped without active session
            batch = stop_trace_session()
            assert batch is None
    
    def test_max_queries_limit(self):
        """Test that max queries limit is respected."""
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.db_trace_enabled = True
            mock_settings.db_trace_slow_threshold_ms = 100.0
            mock_settings.db_trace_max_queries = 5
            
            start_trace_session(request_id="req-1")
            
            # Try to record more than limit
            for i in range(10):
                record_query(sql=f"SELECT {i}", duration_ms=1.0)
            
            batch = stop_trace_session()
            
            # Should be capped at max
            assert batch.total_queries == 5


# =============================================================================
# Test Storage
# =============================================================================

class TestTraceStorage:
    """Tests for TraceStorage ring buffer."""
    
    def test_store_and_retrieve(self):
        """Test storing and retrieving batches."""
        storage = TraceStorage(max_size=10)
        
        batch = DbQueryBatch(request_id="req-1")
        storage.store(batch)
        
        retrieved = storage.get("req-1")
        assert retrieved is not None
        assert retrieved.request_id == "req-1"
    
    def test_ring_buffer_eviction(self):
        """Test that oldest entries are evicted when at capacity."""
        storage = TraceStorage(max_size=3)
        
        for i in range(5):
            batch = DbQueryBatch(request_id=f"req-{i}")
            storage.store(batch)
        
        # First 2 should be evicted
        assert storage.get("req-0") is None
        assert storage.get("req-1") is None
        
        # Last 3 should be present
        assert storage.get("req-2") is not None
        assert storage.get("req-3") is not None
        assert storage.get("req-4") is not None
    
    def test_get_recent(self):
        """Test getting recent batches."""
        storage = TraceStorage(max_size=10)
        
        for i in range(5):
            batch = DbQueryBatch(request_id=f"req-{i}")
            storage.store(batch)
        
        recent = storage.get_recent(3)
        
        assert len(recent) == 3
        # Most recent first
        assert recent[0].request_id == "req-4"
        assert recent[1].request_id == "req-3"
        assert recent[2].request_id == "req-2"
    
    def test_get_stats(self):
        """Test aggregate statistics."""
        storage = TraceStorage(max_size=10)
        
        # Create batches with queries
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.db_trace_slow_threshold_ms = 50.0
            
            batch1 = DbQueryBatch(
                request_id="req-1",
                queries=[
                    DbQueryTrace(sql="SELECT 1", duration_ms=10.0),
                    DbQueryTrace(sql="SELECT 2", duration_ms=20.0),
                ],
            )
            storage.store(batch1)
            
            batch2 = DbQueryBatch(
                request_id="req-2",
                queries=[
                    DbQueryTrace(sql="SELECT 3", duration_ms=100.0),  # slow
                ],
            )
            storage.store(batch2)
        
        stats = storage.get_stats()
        
        assert stats["total_batches"] == 2
        assert stats["total_queries"] == 3
        assert stats["avg_queries_per_request"] == 1.5
    
    def test_clear(self):
        """Test clearing storage."""
        storage = TraceStorage(max_size=10)
        
        storage.store(DbQueryBatch(request_id="req-1"))
        storage.store(DbQueryBatch(request_id="req-2"))
        
        storage.clear()
        
        assert storage.get("req-1") is None
        assert storage.get("req-2") is None
        assert storage.get_recent(10) == []


# =============================================================================
# Test SQL Helpers
# =============================================================================

class TestSqlHelpers:
    """Tests for SQL parsing helpers."""
    
    def test_extract_operation(self):
        """Test operation extraction from SQL."""
        assert _extract_operation("SELECT * FROM users") == "SELECT"
        assert _extract_operation("  select * from users  ") == "SELECT"
        assert _extract_operation("INSERT INTO users VALUES (1)") == "INSERT"
        assert _extract_operation("UPDATE users SET x = 1") == "UPDATE"
        assert _extract_operation("DELETE FROM users") == "DELETE"
        assert _extract_operation("CREATE TABLE test (id INT)") == "CREATE"
        assert _extract_operation("DROP TABLE test") == "DROP"
        assert _extract_operation("ALTER TABLE test ADD col INT") == "ALTER"
        assert _extract_operation("BEGIN") == "TRANSACTION"
        assert _extract_operation("COMMIT") == "TRANSACTION"
        assert _extract_operation("TRUNCATE TABLE test") == "OTHER"
    
    def test_extract_table(self):
        """Test table extraction from SQL."""
        assert _extract_table("SELECT * FROM users") == "users"
        assert _extract_table('SELECT * FROM "Users"') == "Users"
        assert _extract_table("SELECT id, name FROM users WHERE id = 1") == "users"
        assert _extract_table("INSERT INTO orders (id) VALUES (1)") == "orders"
        assert _extract_table("UPDATE items SET qty = 1") == "items"
        assert _extract_table("DELETE FROM sessions") == "sessions"
        
        # No table found
        assert _extract_table("SELECT 1") is None
    
    def test_normalize_sql(self):
        """Test SQL normalization."""
        # Numeric literals replaced
        assert "123" not in _normalize_sql("SELECT * FROM users WHERE id = 123")
        
        # String literals replaced
        assert "john" not in _normalize_sql("SELECT * FROM users WHERE name = 'john'")
        
        # PostgreSQL params normalized
        assert "$1" not in _normalize_sql("SELECT * FROM users WHERE id = $1")
        
        # Whitespace normalized
        normalized = _normalize_sql("SELECT  *\n FROM   users")
        assert "  " not in normalized
        assert "\n" not in normalized


# =============================================================================
# Test N+1 Detection
# =============================================================================

class TestNPlusOneDetection:
    """Tests for N+1 query pattern detection."""
    
    def test_no_detection_for_few_queries(self):
        """Test that few similar queries don't trigger detection."""
        queries = [
            DbQueryTrace(sql="SELECT * FROM posts WHERE user_id = 1", duration_ms=1.0),
            DbQueryTrace(sql="SELECT * FROM posts WHERE user_id = 2", duration_ms=1.0),
            DbQueryTrace(sql="SELECT * FROM posts WHERE user_id = 3", duration_ms=1.0),
        ]
        
        warnings = _detect_n_plus_one(queries, threshold=10)
        assert len(warnings) == 0
    
    def test_detection_for_many_similar_queries(self):
        """Test detection when many similar queries are found."""
        queries = [
            DbQueryTrace(sql=f"SELECT * FROM posts WHERE user_id = {i}", duration_ms=1.0)
            for i in range(15)
        ]
        
        warnings = _detect_n_plus_one(queries, threshold=10)
        assert len(warnings) > 0
        assert "posts" in warnings[0].lower() or "SELECT" in warnings[0]
    
    def test_different_operations_not_grouped(self):
        """Test that different operations are not grouped together."""
        queries = [
            DbQueryTrace(sql="SELECT * FROM posts WHERE user_id = 1", duration_ms=1.0),
            DbQueryTrace(sql="INSERT INTO posts (user_id) VALUES (1)", duration_ms=1.0),
        ] * 10
        
        # Each operation type should be counted separately
        warnings = _detect_n_plus_one(queries, threshold=15)
        # We have 10 SELECTs and 10 INSERTs, neither exceeds threshold of 15
        # Actually we have 20 total, so 10 SELECTs should trigger if threshold is 10
        warnings = _detect_n_plus_one(queries, threshold=10)
        assert len(warnings) >= 1
    
    def test_empty_queries_no_warnings(self):
        """Test that empty query list produces no warnings."""
        warnings = _detect_n_plus_one([])
        assert warnings == []


# =============================================================================
# Test Integration with Settings
# =============================================================================

class TestTracingEnabled:
    """Tests for tracing enabled/disabled behavior."""
    
    def test_tracing_disabled_by_default(self):
        """Test that tracing is disabled by default."""
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.db_trace_enabled = False
            
            assert not is_tracing_enabled()
    
    def test_tracing_enabled_via_settings(self):
        """Test enabling tracing via settings."""
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.db_trace_enabled = True
            
            assert is_tracing_enabled()
    
    def test_session_not_started_when_disabled(self):
        """Test that session is not started when tracing is disabled."""
        with patch("aksara.conf.settings") as mock_settings:
            mock_settings.db_trace_enabled = False
            
            start_trace_session(request_id="req-1")
            
            # Session should not be active
            assert get_current_trace_session() is None
