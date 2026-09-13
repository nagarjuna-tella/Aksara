"""
Aksara Testing Utilities

Helpers for testing Aksara applications.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from aksara.db import Database
    from aksara.identity import AksaraUserProtocol


class AksaraTestClient:
    """
    Test client for Aksara applications.
    
    Wraps the Starlette TestClient with additional Aksara-specific features
    like user authentication simulation.
    
    Usage:
        from aksara.testing import create_test_app, AksaraTestClient
        
        async def test_api():
            app = await create_test_app()
            
            async with AksaraTestClient(app) as client:
                # Anonymous request
                response = client.get("/api/posts/")
                
                # Authenticated request
                response = client.with_user(user).get("/api/posts/")
    """
    
    def __init__(self, app: Any, base_url: str = "http://test"):
        """
        Initialize the test client.
        
        Args:
            app: The Aksara/FastAPI application to test
            base_url: Base URL for requests (default: http://test)
        """
        from starlette.testclient import TestClient
        
        self._app = app
        self._client = TestClient(app, base_url=base_url)
        self._current_user: Optional["AksaraUserProtocol"] = None
    
    def with_user(self, user: "AksaraUserProtocol") -> "AksaraTestClient":
        """
        Return a client that simulates authenticated requests as the given user.
        
        The user will be available in request.state.user for all requests
        made through the returned client.
        
        Args:
            user: The user to authenticate as
            
        Returns:
            A new AksaraTestClient instance with the user set
        """
        new_client = AksaraTestClient(self._app)
        new_client._current_user = user
        new_client._client = self._client
        return new_client
    
    def _inject_user(self) -> None:
        """Inject the current user into request state via middleware."""
        if self._current_user is not None:
            user = self._current_user
            
            # Add middleware to inject user if not already added
            for middleware in self._app.middleware:
                if hasattr(middleware, '__aksara_test_user_middleware__'):
                    return
            
            async def user_injection_middleware(request, call_next):
                request.state.user = user
                return await call_next(request)
            
            user_injection_middleware.__aksara_test_user_middleware__ = True
    
    def get(self, url: str, **kwargs) -> Any:
        """Make a GET request."""
        self._maybe_add_user_header(kwargs)
        return self._client.get(url, **kwargs)
    
    def post(self, url: str, **kwargs) -> Any:
        """Make a POST request."""
        self._maybe_add_user_header(kwargs)
        return self._client.post(url, **kwargs)
    
    def put(self, url: str, **kwargs) -> Any:
        """Make a PUT request."""
        self._maybe_add_user_header(kwargs)
        return self._client.put(url, **kwargs)
    
    def patch(self, url: str, **kwargs) -> Any:
        """Make a PATCH request."""
        self._maybe_add_user_header(kwargs)
        return self._client.patch(url, **kwargs)
    
    def delete(self, url: str, **kwargs) -> Any:
        """Make a DELETE request."""
        self._maybe_add_user_header(kwargs)
        return self._client.delete(url, **kwargs)
    
    def _maybe_add_user_header(self, kwargs: dict) -> None:
        """Add user header for test user injection."""
        if self._current_user is not None:
            headers = kwargs.get("headers", {})
            # Use a special test header to identify the user
            headers["X-Test-User-Id"] = str(getattr(self._current_user, "id", 0))
            kwargs["headers"] = headers
    
    def __enter__(self) -> "AksaraTestClient":
        return self
    
    def __exit__(self, *args) -> None:
        self._client.close()
    
    async def __aenter__(self) -> "AksaraTestClient":
        return self
    
    async def __aexit__(self, *args) -> None:
        self._client.close()


async def create_test_app(
    database_url: Optional[str] = None,
    apply_migrations: bool = False,
    **app_kwargs,
) -> Any:
    """
    Create a Aksara application configured for testing.
    
    Sets up a test application with optional database connection
    and migration application.
    
    Usage:
        from aksara.testing import create_test_app
        
        @pytest.fixture
        async def app():
            app = await create_test_app(
                database_url="postgresql://localhost/test_db",
                apply_migrations=True,
            )
            yield app
    
    Args:
        database_url: Database URL for testing. If not provided,
                     uses DATABASE_URL env var or settings.
        apply_migrations: Whether to run pending migrations (default: False)
        **app_kwargs: Additional arguments passed to Aksara()
        
    Returns:
        A configured Aksara application instance
    """
    import os
    from aksara.app import Aksara
    from aksara.conf import settings
    
    # Determine database URL
    db_url = database_url or os.environ.get("DATABASE_URL") or settings.database_url
    
    # Default test settings
    defaults = {
        "title": "Aksara Test App",
        "auto_discover_views": False,  # Disable auto-discovery in tests
        "debug": True,
    }
    defaults.update(app_kwargs)
    
    # Create the app
    app = Aksara(database_url=db_url, **defaults)
    
    # Apply migrations if requested
    if apply_migrations and db_url:
        await _apply_test_migrations(db_url)
    
    return app


async def _apply_test_migrations(database_url: str) -> None:
    """Apply pending migrations via the canonical executor path.

    Delegates to apply_migrations() so test environments get the same
    advisory-lock, transaction-per-migration, SQL-splitting, and checksum
    guarantees as production runs.  Previously this helper used a manual
    loop that recorded NULL checksums and skipped transaction wrapping.

    Raises:
        RuntimeError: If apply_migrations() reports one or more migration
            errors, including the first failed migration and any skipped
            pending migrations.
    """
    from pathlib import Path
    from aksara.db import Database
    from aksara.conf import settings
    from aksara.migrations.executor import apply_migrations

    mig_dir = Path(settings.migrations_dir)
    db = Database(database_url)
    await db.connect()
    try:
        result = await apply_migrations(
            db,
            mig_dir,
            fake=False,
            verbose=False,
            include_internal=True,
        )
        errors = result.get("errors") or []
        if errors:
            failed_name, failed_error = errors[0]
            pending_skipped = result.get("pending_skipped") or []
            message = (
                f"Test migration application failed at {failed_name}: {failed_error}."
            )
            if pending_skipped:
                message += f" Pending migrations skipped: {pending_skipped}"
            raise RuntimeError(message)
    finally:
        await db.disconnect()


@asynccontextmanager
async def test_database(
    database_url: str,
    cleanup: bool = True,
) -> AsyncGenerator["Database", None]:
    """
    Context manager for test database connections.
    
    Creates an owned database pool for testing. With cleanup enabled, database
    calls made in the current async context use one pinned connection and are
    rolled back when the context exits. The owned pool is always closed.
    
    Usage:
        from aksara.testing import test_database
        
        async def test_queries():
            async with test_database("postgresql://localhost/test") as db:
                # Run tests
                user = await User.objects.create(name="Test")
                assert user.id is not None
    
    Args:
        database_url: PostgreSQL connection URL
        cleanup: Whether to pin same-context operations to a rollback
            transaction (default: True)
        
    Yields:
        Connected Database instance
    """
    from aksara.db import Database
    from aksara.db.session import session_context

    previous_database = Database._instance
    db = Database(database_url)
    try:
        await db.connect()

        if cleanup:
            async with session_context(db) as connection:
                transaction = connection.transaction()
                await transaction.start()
                try:
                    yield db
                finally:
                    await transaction.rollback()
        else:
            yield db
    finally:
        try:
            await db.disconnect()
        finally:
            if Database._instance is db:
                Database._instance = previous_database


def create_test_user(
    id: int = 1,
    username: str = "testuser",
    email: str = "test@example.com",
    is_active: bool = True,
    is_admin: bool = False,
    **extra_attrs,
) -> "AksaraUserProtocol":
    """
    Create a mock user for testing authentication.
    
    Creates a simple user object that implements AksaraUserProtocol
    for testing permission checks and authenticated endpoints.
    
    Usage:
        from aksara.testing import create_test_user
        
        user = create_test_user(username="alice", is_admin=True)
        
        async def test_admin_endpoint():
            client = AksaraTestClient(app)
            response = client.with_user(user).get("/admin/")
            assert response.status_code == 200
    
    Args:
        id: User ID
        username: Username
        email: Email address
        is_active: Whether the user is active
        is_admin: Whether the user is an admin
        **extra_attrs: Additional attributes to set on the user
        
    Returns:
        A mock user object implementing AksaraUserProtocol
    """
    
    class TestUser:
        """Mock user for testing."""
        
        def __init__(self):
            self.id = id
            self.username = username
            self.email = email
            self.is_active = is_active
            self.is_admin = is_admin
            self.is_authenticated = True
            
            # Set extra attributes
            for key, value in extra_attrs.items():
                setattr(self, key, value)
        
        def __repr__(self) -> str:
            return f"TestUser(id={self.id}, username={self.username})"
    
    return TestUser()


async def create_auth_test_user(
    db: "Database",
    username: str = "testuser",
    email: str = "test@example.com",
    password: str = "testpass123",
    is_active: bool = True,
    is_admin: bool = False,
) -> Any:
    """
    Create a real User in the database using aksara.contrib.auth.
    
    This function requires aksara[auth] to be installed and the
    User model migrations to be applied.
    
    Usage:
        from aksara.testing import create_auth_test_user, test_database
        
        async def test_with_real_user():
            async with test_database(db_url) as db:
                user = await create_auth_test_user(db, username="alice")
                # user is a real User model instance
    
    Args:
        db: Connected database instance
        username: Username for the user
        email: Email address
        password: Password (will be hashed)
        is_active: Whether the user is active
        is_admin: Whether the user is an admin
        
    Returns:
        The created User model instance
        
    Raises:
        ImportError: If aksara.contrib.auth is not available
    """
    try:
        from aksara.contrib.auth.models import User
        from aksara.contrib.auth.manager import UserManager
    except ImportError:
        raise ImportError(
            "aksara.contrib.auth is not available. "
            "Install with: pip install aksara-framework[auth]"
        )
    
    manager = UserManager(User, db)
    user = await manager.create_user(
        username=username,
        email=email,
        password=password,
        is_active=is_active,
        is_admin=is_admin,
    )
    return user


class AksaraTestCase:
    """
    Base class for Aksara test cases.
    
    Provides setup and teardown helpers for database testing.
    
    Usage:
        from aksara.testing import AksaraTestCase
        
        class TestPosts(AksaraTestCase):
            database_url = "postgresql://localhost/test"
            
            async def asyncSetUp(self):
                await super().asyncSetUp()
                # Create test data
                self.user = await create_test_user(self.db)
            
            async def test_create_post(self):
                post = await Post.objects.using(self.db).create(
                    title="Test",
                    author_id=self.user.id,
                )
                assert post.id is not None
    """
    
    database_url: Optional[str] = None
    apply_migrations: bool = False
    
    db: Optional["Database"] = None
    app: Optional[Any] = None
    client: Optional[AksaraTestClient] = None
    
    async def asyncSetUp(self) -> None:
        """Set up test fixtures."""
        import os
        from aksara.db import Database
        
        db_url = self.database_url or os.environ.get("DATABASE_URL")
        
        if db_url:
            self.db = Database(db_url)
            await self.db.connect()
            
            if self.apply_migrations:
                await _apply_test_migrations(db_url)
    
    async def asyncTearDown(self) -> None:
        """Tear down test fixtures."""
        if self.client:
            self.client._client.close()
        
        if self.db:
            await self.db.disconnect()


__all__ = [
    "AksaraTestClient",
    "create_test_app",
    "test_database",
    "create_test_user",
    "create_auth_test_user",
    "AksaraTestCase",
]
