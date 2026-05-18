"""
Tests for aksara.contrib.auth module.

Tests the built-in authentication functionality including:
- Password hashing
- User model
- UserManager
- FastAPI integration helpers
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# Password Hashing Tests
# =============================================================================

class TestPasswordHashing:
    """Tests for password hashing utilities."""
    
    def test_hash_password(self):
        """hash_password should return a bcrypt hash."""
        from aksara.contrib.auth.hashing import hash_password
        
        password = "secret123"
        hashed = hash_password(password)
        
        # Should be a non-empty string
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        
        # Should be a bcrypt hash (starts with $2b$)
        assert hashed.startswith("$2b$")
    
    def test_hash_password_different_each_time(self):
        """hash_password should produce different hashes for same password."""
        from aksara.contrib.auth.hashing import hash_password
        
        password = "secret123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        # Different hashes due to random salt
        assert hash1 != hash2
    
    def test_verify_password_correct(self):
        """verify_password should return True for correct password."""
        from aksara.contrib.auth.hashing import hash_password, verify_password
        
        password = "secret123"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """verify_password should return False for incorrect password."""
        from aksara.contrib.auth.hashing import hash_password, verify_password
        
        password = "secret123"
        wrong_password = "wrong123"
        hashed = hash_password(password)
        
        assert verify_password(wrong_password, hashed) is False
    
    def test_make_random_password(self):
        """make_random_password should generate random password of correct length."""
        from aksara.contrib.auth.hashing import make_random_password
        
        # Default length
        password = make_random_password()
        assert len(password) == 12
        
        # Custom length
        password = make_random_password(20)
        assert len(password) == 20
        
        # Should be different each time
        password1 = make_random_password()
        password2 = make_random_password()
        assert password1 != password2


# =============================================================================
# User Model Tests
# =============================================================================

class TestAbstractUser:
    """Tests for AbstractUser model."""
    
    def test_abstract_user_is_abstract(self):
        """AbstractUser should be marked as abstract."""
        from aksara.contrib.auth.models import AbstractUser
        
        assert AbstractUser.__abstract__ is True
    
    def test_abstract_user_fields(self):
        """AbstractUser should have correct fields."""
        from aksara.contrib.auth.models import AbstractUser
        
        # Check field names
        field_names = set(AbstractUser._fields.keys())
        
        assert "email" in field_names
        assert "hashed_password" in field_names
        assert "is_active" in field_names
        assert "is_staff" in field_names
        assert "is_superuser" in field_names


class TestUser:
    """Tests for User model."""
    
    def test_user_inherits_abstract_user(self):
        """User should inherit from AbstractUser."""
        from aksara.contrib.auth.models import User, AbstractUser
        
        assert issubclass(User, AbstractUser)
    
    def test_user_tablename(self):
        """User should have correct tablename."""
        from aksara.contrib.auth.models import User
        
        assert User.__tablename__ == "aksara_users"
    
    def test_user_has_manager(self):
        """User should have UserManager attached."""
        from aksara.contrib.auth.models import User
        from aksara.contrib.auth.manager import UserManager
        
        assert hasattr(User, "objects")
        assert isinstance(User.objects, UserManager)
    
    def test_user_ai_agent_exposed(self):
        """User model should not be exposed to AI agents by default."""
        from aksara.contrib.auth.models import User
        
        # Check Meta class
        meta = getattr(User, "Meta", None)
        assert meta is not None
        assert getattr(meta, "ai_agent_exposed", True) is False
    
    def test_user_has_fields(self):
        """User should inherit fields from AbstractUser."""
        from aksara.contrib.auth.models import User
        
        # Check field names
        field_names = set(User._fields.keys())
        
        assert "email" in field_names
        assert "hashed_password" in field_names
        assert "is_active" in field_names


# =============================================================================
# UserManager Tests
# =============================================================================

class TestUserManager:
    """Tests for UserManager."""
    
    def test_user_manager_init(self):
        """UserManager should initialize correctly."""
        from aksara.contrib.auth.manager import UserManager
        from aksara.contrib.auth.models import User
        
        manager = UserManager(User)
        assert manager._model == User
    
    @pytest.mark.asyncio
    async def test_create_user_hashes_password(self):
        """create_user should hash the password."""
        from aksara.contrib.auth.manager import UserManager
        from aksara.contrib.auth.models import User
        from aksara.contrib.auth.hashing import verify_password
        
        manager = UserManager(User)
        
        # Mock the create method
        created_user = MagicMock()
        created_user.hashed_password = None
        
        async def mock_create(**kwargs):
            created_user.hashed_password = kwargs.get("hashed_password")
            created_user.email = kwargs.get("email")
            created_user.is_active = kwargs.get("is_active", True)
            created_user.is_staff = kwargs.get("is_staff", False)
            created_user.is_superuser = kwargs.get("is_superuser", False)
            return created_user
        
        manager.create = mock_create
        
        email = "test@example.com"
        password = "secret123"
        
        user = await manager.create_user(email=email, password=password)
        
        # Password should be hashed
        assert user.hashed_password is not None
        assert user.hashed_password != password
        assert verify_password(password, user.hashed_password) is True
    
    @pytest.mark.asyncio
    async def test_create_superuser_sets_flags(self):
        """create_superuser should set is_staff and is_superuser."""
        from aksara.contrib.auth.manager import UserManager
        from aksara.contrib.auth.models import User
        
        manager = UserManager(User)
        
        # Mock the create_user method
        created_user = MagicMock()
        
        async def mock_create_user(email, password, **kwargs):
            created_user.email = email
            created_user.is_staff = kwargs.get("is_staff", False)
            created_user.is_superuser = kwargs.get("is_superuser", False)
            return created_user
        
        manager.create_user = mock_create_user
        
        user = await manager.create_superuser(
            email="admin@example.com",
            password="admin123"
        )
        
        assert user.is_staff is True
        assert user.is_superuser is True


# =============================================================================
# Identity Protocol Tests
# =============================================================================

class TestAksaraUserProtocol:
    """Tests for AksaraUserProtocol."""
    
    def test_user_has_required_fields(self):
        """User model should have fields required by protocol."""
        from aksara.contrib.auth.models import User
        
        # Check that fields exist in _fields
        assert "is_active" in User._fields
        assert "is_staff" in User._fields
        assert "is_superuser" in User._fields
    
    def test_anonymous_user(self):
        """AnonymousUser should represent unauthenticated users."""
        from aksara.identity import AnonymousUser
        
        anon = AnonymousUser()
        
        assert anon.id is None
        assert anon.is_active is False
        assert anon.is_staff is False
        assert anon.is_superuser is False
        assert anon.is_authenticated is False
    
    def test_anonymous_user_is_falsy(self):
        """AnonymousUser should be falsy."""
        from aksara.identity import AnonymousUser
        
        anon = AnonymousUser()
        
        assert not anon
        assert bool(anon) is False
    
    def test_anonymous_user_equality(self):
        """Two AnonymousUser instances should be equal."""
        from aksara.identity import AnonymousUser
        
        anon1 = AnonymousUser()
        anon2 = AnonymousUser()
        
        assert anon1 == anon2


# =============================================================================
# FastAPI Integration Tests
# =============================================================================

class TestFastAPIIntegration:
    """Tests for FastAPI helper functions."""
    
    @pytest.mark.asyncio
    async def test_get_current_user_from_state(self):
        """get_current_user should return user from request.state."""
        from aksara.contrib.auth.fastapi import get_current_user
        
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        
        request = MagicMock()
        request.state = MagicMock()
        request.state.user = mock_user
        
        user = await get_current_user(request)
        
        assert user == mock_user
    
    @pytest.mark.asyncio
    async def test_get_current_user_no_auth(self):
        """get_current_user should return None if not authenticated."""
        from aksara.contrib.auth.fastapi import get_current_user
        
        request = MagicMock()
        request.state = MagicMock()
        request.state.user = None
        request.headers = {}
        
        user = await get_current_user(request)
        
        assert user is None

    @pytest.mark.asyncio
    async def test_get_current_user_ignores_client_user_id_header(self):
        """get_current_user should ignore forged X-User-Id headers."""
        from aksara.contrib.auth.fastapi import get_current_user
        from aksara.contrib.auth.models import User

        request = MagicMock()
        request.state = MagicMock()
        request.state.user = None
        request.headers = {"X-User-Id": "7"}

        with patch.object(User.objects, "get", new=AsyncMock()) as get_user:
            user = await get_current_user(request)

        assert user is None
        get_user.assert_not_awaited()
    
    @pytest.mark.asyncio
    async def test_get_current_active_user_inactive(self):
        """get_current_active_user should return None for inactive users."""
        from aksara.contrib.auth.fastapi import get_current_active_user
        
        mock_user = MagicMock()
        mock_user.is_active = False
        
        request = MagicMock()
        request.state = MagicMock()
        request.state.user = mock_user
        
        user = await get_current_active_user(request)
        
        assert user is None


# =============================================================================
# Session Store Tests
# =============================================================================

class TestSessionStore:
    """Tests for DB-backed auth sessions."""

    @pytest.mark.asyncio
    async def test_ensure_sessions_table_creates_table(self):
        """Session table creation should be idempotent."""
        from aksara.contrib.auth.session import SESSIONS_TABLE, _ensure_sessions_table

        db = MagicMock()
        db.execute = AsyncMock(return_value="CREATE TABLE")

        await _ensure_sessions_table(db)

        db.execute.assert_awaited_once()
        assert SESSIONS_TABLE in db.execute.await_args.args[0]

    @pytest.mark.asyncio
    async def test_create_session_token_persists_to_db(self):
        """Creating a session token should insert a DB row."""
        from aksara.contrib.auth.session import SESSIONS_TABLE, create_session_token

        db = MagicMock()
        db.execute = AsyncMock(return_value="INSERT 0 1")
        user = MagicMock()
        user.id = "user-123"

        with patch("aksara.contrib.auth.session.secrets.token_urlsafe", return_value="session-token"):
            token = await create_session_token(db, user, expires_in=60)

        assert token == "session-token"
        query, stored_token, stored_user_id, expires_at = db.execute.await_args.args
        assert SESSIONS_TABLE in query
        assert stored_token == "session-token"
        assert stored_user_id == "user-123"
        assert isinstance(expires_at, datetime)

    @pytest.mark.asyncio
    async def test_get_user_from_session_token_returns_user(self):
        """Valid session tokens should resolve to active users."""
        from aksara.contrib.auth.models import User
        from aksara.contrib.auth.session import get_user_from_session_token

        db = MagicMock()
        db.fetchrow = AsyncMock(
            return_value={
                "user_id": "user-123",
                "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            }
        )
        db.execute = AsyncMock(return_value="DELETE 0")

        user = MagicMock()
        user.is_active = True

        with patch.object(User.objects, "get", new=AsyncMock(return_value=user)):
            resolved = await get_user_from_session_token(db, "session-token")

        assert resolved is user

    @pytest.mark.asyncio
    async def test_get_user_from_session_token_deletes_expired_row(self):
        """Expired session tokens should be removed and rejected."""
        from aksara.contrib.auth.session import get_user_from_session_token

        db = MagicMock()
        db.fetchrow = AsyncMock(
            return_value={
                "user_id": "user-123",
                "expires_at": datetime.now(timezone.utc) - timedelta(minutes=5),
            }
        )
        db.execute = AsyncMock(return_value="DELETE 1")

        resolved = await get_user_from_session_token(db, "session-token")

        assert resolved is None
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalidate_session_token_deletes_row(self):
        """Invalidating a session token should delete the DB row."""
        from aksara.contrib.auth.session import SESSIONS_TABLE, invalidate_session_token

        db = MagicMock()
        db.execute = AsyncMock(return_value="DELETE 1")

        await invalidate_session_token(db, "session-token")

        query, token = db.execute.await_args.args
        assert SESSIONS_TABLE in query
        assert token == "session-token"

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions_returns_deleted_count(self):
        """Expired session cleanup should return the number of deleted rows."""
        from aksara.contrib.auth.session import cleanup_expired_sessions

        db = MagicMock()
        db.execute = AsyncMock(return_value="DELETE 2")

        deleted = await cleanup_expired_sessions(db)

        assert deleted == 2


# =============================================================================
# Module Exports Tests
# =============================================================================

class TestModuleExports:
    """Tests for module exports."""
    
    def test_auth_module_exports(self):
        """aksara.contrib.auth should export key classes."""
        from aksara.contrib import auth
        
        assert hasattr(auth, "User")
        assert hasattr(auth, "AbstractUser")
        assert hasattr(auth, "UserManager")
        assert hasattr(auth, "hash_password")
        assert hasattr(auth, "verify_password")
        assert hasattr(auth, "make_random_password")
    
    def test_identity_module_exports(self):
        """aksara.identity should export key classes."""
        from aksara import identity
        
        assert hasattr(identity, "AksaraUserProtocol")
        assert hasattr(identity, "AnonymousUser")
    
    def test_main_module_exports_identity(self):
        """aksara main module should export identity components."""
        import aksara
        
        assert hasattr(aksara, "AksaraUserProtocol")
        assert hasattr(aksara, "AnonymousUser")
