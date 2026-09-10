# Testing

Comprehensive testing patterns for Aksara applications.

---

## Overview

Aksara provides testing utilities built on pytest:

- **Test client** — Make API requests
- **Database fixtures** — Clean database per test
- **Factories** — Generate test data
- **Mocking** — Mock services and AI

---

## Setup

### Install Test Dependencies

```bash
pip install aksara-framework[test]
# or
pip install pytest pytest-asyncio httpx
```

### Configure pytest

```ini
# pytest.ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_functions = test_*
```

Or in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## Basic Test Structure

### Test Case Class

```python
# tests/test_users.py
import pytest
from aksara.testing import AksaraTestCase
from myapp.models import User

class TestUserModel(AksaraTestCase):
    async def asyncSetUp(self):
        """Run before each test."""
        self.user = await User.objects.create(
            email="test@example.com",
            name="Test User"
        )
    
    async def asyncTearDown(self):
        """Run after each test."""
        pass  # Database is rolled back automatically
    
    async def test_user_creation(self):
        """Test creating a user."""
        assert self.user.id is not None
        assert self.user.email == "test@example.com"
    
    async def test_user_update(self):
        """Test updating a user."""
        self.user.name = "Updated Name"
        await self.user.save()
        
        refreshed = await User.objects.get(id=self.user.id)
        assert refreshed.name == "Updated Name"
```

### Function-Based Tests

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
import pytest
from aksara.testing import async_test, db_session
from myapp.models import User

@pytest.fixture
async def user(db_session):
    return await User.objects.create(
        email="test@example.com",
        name="Test User"
    )

@async_test
async def test_user_exists(user):
    assert await User.objects.filter(id=user.id).exists()
```

---

## API Testing

### Test Client

```python
from aksara.testing import AksaraTestCase

class TestPostAPI(AksaraTestCase):
    async def asyncSetUp(self):
        self.user = await User.objects.create(
            email="test@example.com",
            password=hash_password("password")
        )
        self.token = create_token(self.user)
    
    async def test_list_posts(self):
        """Test listing posts."""
        response = await self.client.get("/api/posts/")
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    async def test_create_post_authenticated(self):
        """Test creating a post while authenticated."""
        response = await self.client.post(
            "/api/posts/",
            json={"title": "Test", "content": "Content"},
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        assert response.status_code == 201
        assert response.json()["title"] == "Test"
    
    async def test_create_post_unauthenticated(self):
        """Test creating a post without auth."""
        response = await self.client.post(
            "/api/posts/",
            json={"title": "Test", "content": "Content"}
        )
        
        assert response.status_code == 401
```

### Authentication Helpers

```python
class TestAuthenticatedAPI(AksaraTestCase):
    async def asyncSetUp(self):
        self.user = await User.objects.create(
            email="test@example.com",
            password=hash_password("password")
        )
        # Login helper
        self.authenticate(self.user)
    
    async def test_protected_endpoint(self):
        # Auth headers added automatically
        response = await self.client.get("/api/me/")
        assert response.status_code == 200
```

### Request Assertions

```python
async def test_post_detail(self):
    post = await Post.objects.create(title="Test", content="Content")
    
    response = await self.client.get(f"/api/posts/{post.id}/")
    
    # Status code
    assert response.status_code == 200
    
    # Response data
    data = response.json()
    assert data["id"] == str(post.id)
    assert data["title"] == "Test"
    
    # Response headers
    assert "application/json" in response.headers["content-type"]
```

---

## Factories

### Basic Factory

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
# tests/factories.py
from aksara.testing import Factory, Faker
from myapp.models import User, Post

class UserFactory(Factory):
    class Meta:
        model = User
    
    email = Faker("email")
    name = Faker("name")
    password = "hashed_password"
    is_active = True

class PostFactory(Factory):
    class Meta:
        model = Post
    
    title = Faker("sentence")
    content = Faker("paragraph")
    author = Factory.SubFactory(UserFactory)
    is_published = True
```

### Using Factories

```python
from tests.factories import UserFactory, PostFactory

class TestPosts(AksaraTestCase):
    async def test_with_factories(self):
        # Create single instance
        user = await UserFactory.create()
        
        # Create with overrides
        admin = await UserFactory.create(
            email="admin@example.com",
            is_admin=True
        )
        
        # Create multiple
        users = await UserFactory.create_batch(5)
        
        # Create with related objects
        post = await PostFactory.create(
            author=admin,
            title="Admin Post"
        )
```

### Factory Sequences

```python
class UserFactory(Factory):
    class Meta:
        model = User
    
    # Unique values using sequence
    email = Factory.Sequence(lambda n: f"user{n}@example.com")
    username = Factory.Sequence(lambda n: f"user{n}")
```

### Factory Traits

```python
class UserFactory(Factory):
    class Meta:
        model = User
    
    email = Faker("email")
    is_admin = False
    is_active = True
    
    class Params:
        admin = Factory.Trait(is_admin=True)
        inactive = Factory.Trait(is_active=False)

# Usage
admin = await UserFactory.create(admin=True)
inactive = await UserFactory.create(inactive=True)
```

---

## Database Fixtures

### Automatic Rollback

```python
from aksara.testing import AksaraTestCase

class TestDatabase(AksaraTestCase):
    # Database is automatically rolled back after each test
    
    async def test_creates_data(self):
        await User.objects.create(email="test@example.com")
        count = await User.objects.count()
        assert count == 1
    
    async def test_clean_database(self):
        # Previous test's data is gone
        count = await User.objects.count()
        assert count == 0
```

### Shared Fixtures

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
import pytest
from aksara.testing import db_session

@pytest.fixture(scope="module")
async def test_data(db_session):
    """Create test data shared across module."""
    user = await User.objects.create(email="shared@example.com")
    posts = await PostFactory.create_batch(10, author=user)
    return {"user": user, "posts": posts}

async def test_first(test_data):
    assert len(test_data["posts"]) == 10

async def test_second(test_data):
    # Same data available
    assert test_data["user"].email == "shared@example.com"
```

---

## Mocking

### Mock External Services

```python
from unittest.mock import AsyncMock, patch

class TestPayment(AksaraTestCase):
    @patch("myapp.services.payment.process_payment")
    async def test_checkout(self, mock_payment):
        mock_payment.return_value = {"status": "success", "transaction_id": "123"}
        
        response = await self.client.post(
            "/api/checkout/",
            json={"amount": 100}
        )
        
        assert response.status_code == 200
        mock_payment.assert_called_once_with(amount=100)
```

### Mock AI Services

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.testing import mock_ai

class TestAIFeatures(AksaraTestCase):
    async def test_ai_query(self):
        with mock_ai(response="SELECT * FROM users"):
            response = await self.client.post(
                "/api/ai/query/",
                json={"query": "Get all users"}
            )
            
            assert response.status_code == 200
```

### Mock Database Queries

```python
from unittest.mock import patch, AsyncMock

async def test_with_mocked_query():
    mock_users = [User(id="1", email="test@example.com")]
    
    with patch.object(User.objects, "all", new_callable=AsyncMock) as mock:
        mock.return_value = mock_users
        
        users = await User.objects.all()
        assert len(users) == 1
```

---

## Testing Async Code

### Async Test Functions

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result == expected

# With AksaraTestCase, async is automatic
class TestAsync(AksaraTestCase):
    async def test_no_decorator_needed(self):
        result = await some_async_function()
        assert result == expected
```

### Testing Background Tasks

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.testing import capture_tasks

class TestBackgroundTasks(AksaraTestCase):
    async def test_creates_background_task(self):
        with capture_tasks() as tasks:
            response = await self.client.post("/api/send-email/")
        
        assert len(tasks) == 1
        assert tasks[0].name == "send_email"
```

---

## Testing ViewSets

### ViewSet Testing

```python
from aksara.testing import AksaraTestCase
from myapp.viewsets import PostViewSet

class TestPostViewSet(AksaraTestCase):
    async def test_list_action(self):
        await PostFactory.create_batch(5)
        
        response = await self.client.get("/api/posts/")
        
        assert response.status_code == 200
        assert len(response.json()) == 5
    
    async def test_custom_action(self):
        post = await PostFactory.create(is_published=False)
        self.authenticate(post.author)
        
        response = await self.client.post(f"/api/posts/{post.id}/publish/")
        
        assert response.status_code == 200
        
        # Verify database change
        await post.refresh_from_db()
        assert post.is_published is True
```

### Permission Testing

```python
class TestPermissions(AksaraTestCase):
    async def test_admin_only_endpoint(self):
        user = await UserFactory.create(is_admin=False)
        self.authenticate(user)
        
        response = await self.client.delete("/api/posts/123/")
        assert response.status_code == 403
    
    async def test_owner_can_edit(self):
        post = await PostFactory.create()
        self.authenticate(post.author)
        
        response = await self.client.patch(
            f"/api/posts/{post.id}/",
            json={"title": "Updated"}
        )
        assert response.status_code == 200
```

---

## Testing Migrations

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.testing import MigrationTestCase

class TestMigrations(MigrationTestCase):
    async def test_migration_0003(self):
        # Apply up to migration before
        await self.migrate("myapp", "0002")
        
        # Create data in old schema
        await self.execute("INSERT INTO posts (title) VALUES ('Test')")
        
        # Apply the migration
        await self.migrate("myapp", "0003")
        
        # Verify migration worked
        result = await self.execute("SELECT slug FROM posts WHERE title = 'Test'")
        assert result[0]["slug"] == "test"
```

---

## Test Configuration

### Test Settings

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
# tests/conftest.py
import pytest
from aksara.testing import setup_test_database

@pytest.fixture(scope="session")
def test_settings():
    return {
        "DATABASE_URL": "postgresql://localhost/test_db",
        "DEBUG": True,
        "AI_MODE": False,
    }

@pytest.fixture(scope="session", autouse=True)
async def setup_database(test_settings):
    await setup_test_database(test_settings)
```

### Test Markers

```python
import pytest

# Skip slow tests
@pytest.mark.slow
async def test_slow_operation():
    pass

# Run only in CI
@pytest.mark.ci_only
async def test_integration():
    pass

# pytest.ini
# markers =
#     slow: marks tests as slow
#     ci_only: marks tests for CI only
```

---

## Running Tests

### Basic Commands

```bash
# Run all tests
aksara test

# Run specific file
aksara test tests/test_users.py

# Run specific test
aksara test tests/test_users.py::TestUserAPI::test_create

# Run with coverage
aksara test --cov=myapp

# Run with verbose output
aksara test -v
```

### Test Coverage

```bash
# Generate coverage report
aksara test --cov=myapp --cov-report=html

# View report
open htmlcov/index.html
```

---

## Best Practices

### Do

- Test one thing per test
- Use descriptive test names
- Use factories for test data
- Clean up after tests
- Test edge cases

### Don't

- Don't test framework code
- Don't rely on test order
- Don't share mutable state
- Don't skip error handling tests

### Naming Conventions

```text
# Good: descriptive, action-focused
async def test_create_user_with_valid_data():
async def test_create_user_fails_with_invalid_email():
async def test_delete_post_requires_authentication():

# Bad: vague, non-descriptive
async def test_user():
async def test_api():
async def test_1():
```

---

## Related Documentation

- [Signals](signals.md)
- [ViewSets](../api/viewsets.md)
- [CLI Commands](../cli/commands.md)
