"""
Tests for aksara.permissions module.

Tests the DRF-inspired permission system including:
- BasePermission
- Built-in permissions (AllowAny, IsAuthenticated, etc.)
- Permission composition (AND, OR)
- check_permissions utility
"""

import pytest
from unittest.mock import MagicMock, PropertyMock


# =============================================================================
# BasePermission Tests
# =============================================================================

class TestBasePermission:
    """Tests for BasePermission base class."""
    
    def test_base_permission_defaults(self):
        """BasePermission should have correct defaults."""
        from aksara.permissions import BasePermission
        
        # Create a concrete subclass
        class TestPermission(BasePermission):
            def has_permission(self, request, view=None):
                return True
        
        perm = TestPermission()
        
        assert perm.message == "Permission denied."
        assert perm.ai_allow is True
    
    def test_get_user_from_state(self):
        """get_user should extract user from request.state.user."""
        from aksara.permissions import AllowAny
        
        perm = AllowAny()
        
        mock_user = MagicMock()
        request = MagicMock()
        request.state.user = mock_user
        
        assert perm.get_user(request) == mock_user
    
    def test_get_user_from_request_user(self):
        """get_user should extract user from request.user (Django-style)."""
        from aksara.permissions import AllowAny
        
        perm = AllowAny()
        
        mock_user = MagicMock()
        request = MagicMock(spec=["user"])
        request.user = mock_user
        
        assert perm.get_user(request) == mock_user
    
    def test_get_user_none(self):
        """get_user should return None if no user found."""
        from aksara.permissions import AllowAny
        
        perm = AllowAny()
        
        request = MagicMock(spec=[])
        
        assert perm.get_user(request) is None
    
    def test_is_safe_method(self):
        """is_safe_method should identify read-only methods."""
        from aksara.permissions import AllowAny
        
        perm = AllowAny()
        
        # Safe methods
        for method in ["GET", "HEAD", "OPTIONS", "get", "Get"]:
            request = MagicMock()
            request.method = method
            assert perm.is_safe_method(request) is True
        
        # Unsafe methods
        for method in ["POST", "PUT", "PATCH", "DELETE", "post"]:
            request = MagicMock()
            request.method = method
            assert perm.is_safe_method(request) is False


# =============================================================================
# Built-in Permission Tests
# =============================================================================

class TestAllowAny:
    """Tests for AllowAny permission."""
    
    def test_allows_everything(self):
        """AllowAny should always return True."""
        from aksara.permissions import AllowAny
        
        perm = AllowAny()
        request = MagicMock()
        
        assert perm.has_permission(request) is True
        assert perm.has_permission(request, view=MagicMock()) is True


class TestIsAuthenticated:
    """Tests for IsAuthenticated permission."""
    
    def test_allows_authenticated_user(self):
        """IsAuthenticated should allow authenticated users."""
        from aksara.permissions import IsAuthenticated
        
        perm = IsAuthenticated()
        
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        
        request = MagicMock()
        request.state.user = mock_user
        
        assert perm.has_permission(request) is True
    
    def test_denies_unauthenticated(self):
        """IsAuthenticated should deny unauthenticated requests."""
        from aksara.permissions import IsAuthenticated
        
        perm = IsAuthenticated()
        
        request = MagicMock(spec=[])
        
        assert perm.has_permission(request) is False
    
    def test_denies_anonymous_user(self):
        """IsAuthenticated should deny anonymous users."""
        from aksara.permissions import IsAuthenticated
        
        perm = IsAuthenticated()
        
        mock_user = MagicMock()
        mock_user.is_authenticated = False
        
        request = MagicMock()
        request.state.user = mock_user
        
        assert perm.has_permission(request) is False


class TestIsAdminUser:
    """Tests for IsAdminUser permission."""
    
    def test_allows_staff(self):
        """IsAdminUser should allow staff users."""
        from aksara.permissions import IsAdminUser
        
        perm = IsAdminUser()
        
        mock_user = MagicMock()
        mock_user.is_staff = True
        mock_user.is_superuser = False
        
        request = MagicMock()
        request.state.user = mock_user
        
        assert perm.has_permission(request) is True
    
    def test_allows_superuser(self):
        """IsAdminUser should allow superusers."""
        from aksara.permissions import IsAdminUser
        
        perm = IsAdminUser()
        
        mock_user = MagicMock()
        mock_user.is_staff = False
        mock_user.is_superuser = True
        
        request = MagicMock()
        request.state.user = mock_user
        
        assert perm.has_permission(request) is True
    
    def test_denies_regular_user(self):
        """IsAdminUser should deny regular users."""
        from aksara.permissions import IsAdminUser
        
        perm = IsAdminUser()
        
        mock_user = MagicMock()
        mock_user.is_staff = False
        mock_user.is_superuser = False
        
        request = MagicMock()
        request.state.user = mock_user
        
        assert perm.has_permission(request) is False


class TestIsActiveUser:
    """Tests for IsActiveUser permission."""
    
    def test_allows_active_authenticated(self):
        """IsActiveUser should allow active authenticated users."""
        from aksara.permissions import IsActiveUser
        
        perm = IsActiveUser()
        
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        mock_user.is_active = True
        
        request = MagicMock()
        request.state.user = mock_user
        
        assert perm.has_permission(request) is True
    
    def test_denies_inactive(self):
        """IsActiveUser should deny inactive users."""
        from aksara.permissions import IsActiveUser
        
        perm = IsActiveUser()
        
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        mock_user.is_active = False
        
        request = MagicMock()
        request.state.user = mock_user
        
        assert perm.has_permission(request) is False


class TestIsOwnerOrReadOnly:
    """Tests for IsOwnerOrReadOnly permission."""
    
    def test_allows_read_for_anyone(self):
        """IsOwnerOrReadOnly should allow read access for anyone."""
        from aksara.permissions import IsOwnerOrReadOnly
        
        perm = IsOwnerOrReadOnly()
        
        request = MagicMock()
        request.method = "GET"
        
        obj = MagicMock()
        obj.user_id = 1
        
        assert perm.has_object_permission(request, None, obj) is True
    
    def test_allows_owner_write(self):
        """IsOwnerOrReadOnly should allow owners to write."""
        from aksara.permissions import IsOwnerOrReadOnly
        
        perm = IsOwnerOrReadOnly()
        
        mock_user = MagicMock()
        mock_user.id = 1
        
        request = MagicMock()
        request.method = "POST"
        request.state.user = mock_user
        
        obj = MagicMock()
        obj.user_id = 1
        
        assert perm.has_object_permission(request, None, obj) is True
    
    def test_denies_non_owner_write(self):
        """IsOwnerOrReadOnly should deny non-owners from writing."""
        from aksara.permissions import IsOwnerOrReadOnly
        
        perm = IsOwnerOrReadOnly()
        
        mock_user = MagicMock()
        mock_user.id = 1
        
        request = MagicMock()
        request.method = "POST"
        request.state.user = mock_user
        
        obj = MagicMock()
        obj.user_id = 2  # Different user
        
        assert perm.has_object_permission(request, None, obj) is False


class TestDenyAI:
    """Tests for DenyAI permission."""
    
    def test_allows_regular_request(self):
        """DenyAI should allow regular (non-AI) requests."""
        from aksara.permissions import DenyAI
        
        perm = DenyAI()
        
        request = MagicMock()
        request.headers = {}
        # Create state without is_ai_agent attribute
        class MockState:
            pass
        request.state = MockState()
        
        # Also ensure is_ai_agent is not on request
        del request.is_ai_agent
        
        assert perm.has_permission(request) is True
    
    def test_denies_ai_header(self):
        """DenyAI should ignore client-controlled AI headers."""
        from aksara.permissions import DenyAI
        
        perm = DenyAI()
        
        request = MagicMock()
        request.headers = {"X-AI-Agent": "true"}
        
        assert perm.has_permission(request) is True
    
    def test_denies_ai_state(self):
        """DenyAI should deny requests with is_ai_agent state."""
        from aksara.permissions import DenyAI
        
        perm = DenyAI()
        
        request = MagicMock()
        request.headers = {}
        request.state.is_ai_agent = True
        
        assert perm.has_permission(request) is False

    def test_ignores_request_is_ai_agent_attribute(self):
        """DenyAI should ignore non-standard request attributes."""
        from aksara.permissions import DenyAI

        perm = DenyAI()

        request = MagicMock()
        request.headers = {}
        request.is_ai_agent = True

        assert perm.has_permission(request) is True
    
    def test_ai_allow_is_false(self):
        """DenyAI should have ai_allow=False."""
        from aksara.permissions import DenyAI
        
        perm = DenyAI()
        
        assert perm.ai_allow is False


class TestOperationPermission:
    """Tests for OperationPermission."""
    
    def test_allows_specified_operations(self):
        """OperationPermission should allow specified operations."""
        from aksara.permissions import OperationPermission
        
        perm = OperationPermission(allow=["read", "create"])
        
        for method in ["GET", "HEAD", "OPTIONS"]:
            request = MagicMock()
            request.method = method
            assert perm.has_permission(request) is True
        
        request = MagicMock()
        request.method = "POST"
        assert perm.has_permission(request) is True
    
    def test_denies_unspecified_operations(self):
        """OperationPermission should deny unspecified operations."""
        from aksara.permissions import OperationPermission
        
        perm = OperationPermission(allow=["read"])
        
        for method in ["POST", "PUT", "PATCH", "DELETE"]:
            request = MagicMock()
            request.method = method
            assert perm.has_permission(request) is False


# =============================================================================
# Permission Composition Tests
# =============================================================================

class TestAND:
    """Tests for AND permission composition."""
    
    def test_and_all_pass(self):
        """AND should pass only if all permissions pass."""
        from aksara.permissions import AND, AllowAny, IsAuthenticated
        
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        
        request = MagicMock()
        request.state.user = mock_user
        
        perm = AND(AllowAny(), IsAuthenticated())
        
        assert perm.has_permission(request) is True
    
    def test_and_one_fails(self):
        """AND should fail if any permission fails."""
        from aksara.permissions import AND, AllowAny, IsAdminUser
        
        mock_user = MagicMock()
        mock_user.is_staff = False
        mock_user.is_superuser = False
        
        request = MagicMock()
        request.state.user = mock_user
        
        perm = AND(AllowAny(), IsAdminUser())
        
        assert perm.has_permission(request) is False
    
    def test_and_operator(self):
        """& operator should create AND permission."""
        from aksara.permissions import IsAuthenticated, IsAdminUser
        
        perm = IsAuthenticated() & IsAdminUser()
        
        # Should create AND instance
        from aksara.permissions import AND
        assert isinstance(perm, AND)


class TestOR:
    """Tests for OR permission composition."""
    
    def test_or_one_passes(self):
        """OR should pass if any permission passes."""
        from aksara.permissions import OR, IsAdminUser, IsAuthenticated
        
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        mock_user.is_staff = False
        mock_user.is_superuser = False
        
        request = MagicMock()
        request.state.user = mock_user
        
        perm = OR(IsAdminUser(), IsAuthenticated())
        
        assert perm.has_permission(request) is True
    
    def test_or_all_fail(self):
        """OR should fail if all permissions fail."""
        from aksara.permissions import OR, IsAdminUser, IsAuthenticated
        
        mock_user = MagicMock()
        mock_user.is_authenticated = False
        mock_user.is_staff = False
        mock_user.is_superuser = False
        
        request = MagicMock()
        request.state.user = mock_user
        
        perm = OR(IsAdminUser(), IsAuthenticated())
        
        assert perm.has_permission(request) is False
    
    def test_or_operator(self):
        """| operator should create OR permission."""
        from aksara.permissions import IsAuthenticated, IsAdminUser
        
        perm = IsAuthenticated() | IsAdminUser()
        
        # Should create OR instance
        from aksara.permissions import OR
        assert isinstance(perm, OR)


# =============================================================================
# check_permissions Utility Tests
# =============================================================================

class TestCheckPermissions:
    """Tests for check_permissions utility function."""
    
    def test_check_permissions_all_pass(self):
        """check_permissions should return (True, None) if all pass."""
        from aksara.permissions import check_permissions, AllowAny
        
        request = MagicMock()
        
        allowed, message = check_permissions([AllowAny], request)
        
        assert allowed is True
        assert message is None
    
    def test_check_permissions_one_fails(self):
        """check_permissions should return (False, message) if any fails."""
        from aksara.permissions import check_permissions, IsAuthenticated
        
        request = MagicMock(spec=[])
        
        allowed, message = check_permissions([IsAuthenticated], request)
        
        assert allowed is False
        assert message == "Authentication required."
    
    def test_check_permissions_with_instances(self):
        """check_permissions should work with permission instances."""
        from aksara.permissions import check_permissions, AllowAny
        
        request = MagicMock()
        
        allowed, message = check_permissions([AllowAny()], request)
        
        assert allowed is True
        assert message is None
    
    def test_check_permissions_with_object(self):
        """check_permissions should check object permissions."""
        from aksara.permissions import check_permissions, IsOwnerOrReadOnly
        
        mock_user = MagicMock()
        mock_user.id = 1
        
        request = MagicMock()
        request.method = "POST"
        request.state.user = mock_user
        
        obj = MagicMock()
        obj.user_id = 2  # Different user
        
        allowed, message = check_permissions([IsOwnerOrReadOnly], request, obj=obj)
        
        assert allowed is False


# =============================================================================
# Module Export Tests
# =============================================================================

class TestPermissionsExports:
    """Tests for permissions module exports."""
    
    def test_main_module_exports(self):
        """aksara main module should export permission classes."""
        import aksara
        
        assert hasattr(aksara, "BasePermission")
        assert hasattr(aksara, "AllowAny")
        assert hasattr(aksara, "IsAuthenticated")
        assert hasattr(aksara, "IsAdminUser")
        assert hasattr(aksara, "IsActiveUser")
        assert hasattr(aksara, "IsOwnerOrReadOnly")
        assert hasattr(aksara, "DenyAI")
        assert hasattr(aksara, "OperationPermission")
        assert hasattr(aksara, "AND")
        assert hasattr(aksara, "OR")
        assert hasattr(aksara, "check_permissions")
