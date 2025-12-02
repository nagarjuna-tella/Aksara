"""
Tests for vidyut.contrib.auth module.

Tests the built-in authentication functionality including:
- Password hashing
- User model
- UserManager
- FastAPI integration helpers
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# =============================================================================
# Password Hashing Tests
# =============================================================================

class TestPasswordHashing:
    """Tests for password hashing utilities."""
    
    def test_hash_password(self):
        """hash_password should return a bcrypt hash."""
        from vidyut.contrib.auth.hashing import hash_password
        
        password = "secret123"
        hashed = hash_password(password)
        
        # Should be a non-empty string
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        
        # Should be a bcrypt hash (starts with $2b$)
        assert hashed.startswith("$2b$")
    
    def test_hash_password_different_each_time(self):
        """hash_password should produce different hashes for same password."""
        from vidyut.contrib.auth.hashing import hash_password
        
        password = "secret123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        # Different hashes due to random salt
        assert hash1 != hash2
    
    def test_verify_password_correct(self):
        """verify_password should return True for correct password."""
        from vidyut.contrib.auth.hashing import hash_password, verify_password
        
        password = "secret123"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """verify_password should return False for incorrect password."""
        from vidyut.contrib.auth.hashing import hash_password, verify_password
        
        password = "secret123"
        wrong_password = "wrong123"
        hashed = hash_password(password)
        
        assert verify_password(wrong_password, hashed) is False
    
    def test_make_random_password(self):
        """make_random_password should generate random password of correct length."""
        from vidyut.contrib.auth.hashing import make_random_password
        
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
        from vidyut.contrib.auth.models import AbstractUser
        
        assert AbstractUser.__abstract__ is True
    
    def test_abstract_user_fields(self):
        """AbstractUser should have correct fields."""
        from vidyut.contrib.auth.models import AbstractUser
        
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
        from vidyut.contrib.auth.models import User, AbstractUser
        
        assert issubclass(User, AbstractUser)
    
    def test_user_tablename(self):
        """User should have correct tablename."""
        from vidyut.contrib.auth.models import User
        
        assert User.__tablename__ == "vidyut_users"
    
    def test_user_has_manager(self):
        """User should have UserManager attached."""
        from vidyut.contrib.auth.models import User
        from vidyut.contrib.auth.manager import UserManager
        
        assert hasattr(User, "objects")
        assert isinstance(User.objects, UserManager)
    
    def test_user_ai_agent_exposed(self):
        """User model should not be exposed to AI agents by default."""
        from vidyut.contrib.auth.models import User
        
        # Check Meta class
        meta = getattr(User, "Meta", None)
        assert meta is not None
        assert getattr(meta, "ai_agent_exposed", True) is False
    
    def test_user_has_fields(self):
        """User should inherit fields from AbstractUser."""
        from vidyut.contrib.auth.models import User
        
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
        from vidyut.contrib.auth.manager import UserManager
        from vidyut.contrib.auth.models import User
        
        manager = UserManager(User)
        assert manager._model == User
    
    @pytest.mark.asyncio
    async def test_create_user_hashes_password(self):
        """create_user should hash the password."""
        from vidyut.contrib.auth.manager import UserManager
        from vidyut.contrib.auth.models import User
        from vidyut.contrib.auth.hashing import verify_password
        
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
        from vidyut.contrib.auth.manager import UserManager
        from vidyut.contrib.auth.models import User
        
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

class TestVidyutUserProtocol:
    """Tests for VidyutUserProtocol."""
    
    def test_user_has_required_fields(self):
        """User model should have fields required by protocol."""
        from vidyut.contrib.auth.models import User
        
        # Check that fields exist in _fields
        assert "is_active" in User._fields
        assert "is_staff" in User._fields
        assert "is_superuser" in User._fields
    
    def test_anonymous_user(self):
        """AnonymousUser should represent unauthenticated users."""
        from vidyut.identity import AnonymousUser
        
        anon = AnonymousUser()
        
        assert anon.id is None
        assert anon.is_active is False
        assert anon.is_staff is False
        assert anon.is_superuser is False
        assert anon.is_authenticated is False
    
    def test_anonymous_user_is_falsy(self):
        """AnonymousUser should be falsy."""
        from vidyut.identity import AnonymousUser
        
        anon = AnonymousUser()
        
        assert not anon
        assert bool(anon) is False
    
    def test_anonymous_user_equality(self):
        """Two AnonymousUser instances should be equal."""
        from vidyut.identity import AnonymousUser
        
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
        from vidyut.contrib.auth.fastapi import get_current_user
        
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
        from vidyut.contrib.auth.fastapi import get_current_user
        
        request = MagicMock()
        request.state = MagicMock()
        request.state.user = None
        request.headers = {}
        
        user = await get_current_user(request)
        
        assert user is None
    
    @pytest.mark.asyncio
    async def test_get_current_active_user_inactive(self):
        """get_current_active_user should return None for inactive users."""
        from vidyut.contrib.auth.fastapi import get_current_active_user
        
        mock_user = MagicMock()
        mock_user.is_active = False
        
        request = MagicMock()
        request.state = MagicMock()
        request.state.user = mock_user
        
        user = await get_current_active_user(request)
        
        assert user is None


# =============================================================================
# Module Exports Tests
# =============================================================================

class TestModuleExports:
    """Tests for module exports."""
    
    def test_auth_module_exports(self):
        """vidyut.contrib.auth should export key classes."""
        from vidyut.contrib import auth
        
        assert hasattr(auth, "User")
        assert hasattr(auth, "AbstractUser")
        assert hasattr(auth, "UserManager")
        assert hasattr(auth, "hash_password")
        assert hasattr(auth, "verify_password")
        assert hasattr(auth, "make_random_password")
    
    def test_identity_module_exports(self):
        """vidyut.identity should export key classes."""
        from vidyut import identity
        
        assert hasattr(identity, "VidyutUserProtocol")
        assert hasattr(identity, "AnonymousUser")
    
    def test_main_module_exports_identity(self):
        """vidyut main module should export identity components."""
        import vidyut
        
        assert hasattr(vidyut, "VidyutUserProtocol")
        assert hasattr(vidyut, "AnonymousUser")
