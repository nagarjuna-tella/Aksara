# Authentication

Authenticate users in your Aksara API.

---

## Overview

Aksara supports multiple authentication methods:

- **Session authentication** — Cookie-based sessions
- **Token authentication** — Bearer tokens
- **JWT authentication** — JSON Web Tokens
- **Custom authentication** — Build your own

```python
from aksara import Aksara
from aksara.middleware import AuthenticationMiddleware

app = Aksara()
app.add_middleware(AuthenticationMiddleware)
```

---

## User Model

Aksara provides a built-in User model:

```python
from aksara.contrib.auth import User

# Create user
user = await User.objects.create(
    email="jane@example.com",
    password="securepassword123",  # Automatically hashed
)

# Check password
is_valid = user.check_password("securepassword123")

# Get user
user = await User.objects.get(email="jane@example.com")
```

### User Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `email` | Email | Unique email address |
| `password` | String | Hashed password |
| `is_active` | Boolean | Can user login |
| `is_staff` | Boolean | Admin access |
| `is_superuser` | Boolean | Full permissions |
| `created_at` | DateTime | Registration date |
| `last_login` | DateTime | Last login time |

### Custom User Model

```python
from aksara.contrib.auth import AbstractUser

class User(AbstractUser):
    """Custom user with additional fields."""
    
    name = fields.String(max_length=100)
    avatar_url = fields.URL(nullable=True)
    bio = fields.Text(nullable=True)
    
    class Meta:
        table_name = "users"
```

---

## Session Authentication

Cookie-based authentication for web apps:

### Setup

```python
from aksara import Aksara
from aksara.middleware import SessionMiddleware, AuthenticationMiddleware

app = Aksara()
app.add_middleware(
    SessionMiddleware,
    secret_key="your-secret-key",
    session_cookie="session",
    max_age=3600 * 24 * 7,  # 7 days
)
app.add_middleware(AuthenticationMiddleware)
```

### Login Endpoint

```python
from aksara.contrib.auth import authenticate, login

@app.post("/auth/login")
async def login_view(request):
    data = await request.json()
    
    # Authenticate user
    user = await authenticate(
        email=data["email"],
        password=data["password"],
    )
    
    if not user:
        return JSONResponse(
            {"error": "Invalid credentials"},
            status_code=401,
        )
    
    # Create session
    await login(request, user)
    
    return {"message": "Logged in", "user_id": str(user.id)}
```

### Logout Endpoint

```python
from aksara.contrib.auth import logout

@app.post("/auth/logout")
async def logout_view(request):
    await logout(request)
    return {"message": "Logged out"}
```

### Accessing User

```python
@app.get("/profile")
async def profile(request):
    if not request.user.is_authenticated:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    return {
        "id": str(request.user.id),
        "email": request.user.email,
    }
```

---

## Token Authentication

Bearer token authentication for APIs:

### Setup

```python
from aksara.contrib.auth.tokens import TokenAuthentication

app.add_middleware(TokenAuthentication)
```

### Token Model

```python
from aksara.contrib.auth.tokens import Token

# Create token for user
token = await Token.objects.create(user=user)
print(token.key)  # "abc123..."

# Tokens auto-expire (configurable)
```

### Login with Token

```python
from aksara.contrib.auth import authenticate
from aksara.contrib.auth.tokens import Token

@app.post("/auth/token")
async def get_token(request):
    data = await request.json()
    
    user = await authenticate(
        email=data["email"],
        password=data["password"],
    )
    
    if not user:
        return JSONResponse({"error": "Invalid credentials"}, status_code=401)
    
    # Get or create token
    token, created = await Token.objects.get_or_create(user=user)
    
    return {"token": token.key}
```

### Using Token

```bash
curl -H "Authorization: Bearer abc123..." http://localhost:8000/api/posts/
```

### In ViewSet

```python
class PostViewSet(ModelViewSet):
    model = Post
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
```

---

## JWT Authentication

JSON Web Token authentication:

### Setup

```python
# settings.py
JWT_SECRET = "your-jwt-secret-key"
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION = 3600  # 1 hour
```

```python
from aksara.contrib.auth.jwt import JWTAuthentication

app.add_middleware(JWTAuthentication)
```

### Generate JWT

```python
from aksara.contrib.auth.jwt import create_access_token, create_refresh_token

@app.post("/auth/token")
async def get_jwt(request):
    data = await request.json()
    
    user = await authenticate(
        email=data["email"],
        password=data["password"],
    )
    
    if not user:
        return JSONResponse({"error": "Invalid credentials"}, status_code=401)
    
    return {
        "access_token": create_access_token(user),
        "refresh_token": create_refresh_token(user),
        "token_type": "bearer",
    }
```

### Refresh Token

```python
from aksara.contrib.auth.jwt import verify_refresh_token, create_access_token

@app.post("/auth/refresh")
async def refresh_jwt(request):
    data = await request.json()
    refresh_token = data.get("refresh_token")
    
    user = await verify_refresh_token(refresh_token)
    if not user:
        return JSONResponse({"error": "Invalid refresh token"}, status_code=401)
    
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
    }
```

### JWT Payload

```python
# Default payload
{
    "sub": "user-uuid",           # User ID
    "email": "user@example.com",  # User email
    "exp": 1704067200,            # Expiration timestamp
    "iat": 1704063600,            # Issued at timestamp
}

# Custom claims
def create_access_token(user):
    return jwt.encode({
        "sub": str(user.id),
        "email": user.email,
        "is_staff": user.is_staff,
        "roles": user.roles,  # Custom claim
        "exp": datetime.utcnow() + timedelta(hours=1),
    }, JWT_SECRET, algorithm=JWT_ALGORITHM)
```

---

## Custom Authentication

Create your own authentication backend:

```python
from aksara.contrib.auth import BaseAuthentication

class APIKeyAuthentication(BaseAuthentication):
    """Authenticate with API key."""
    
    async def authenticate(self, request):
        api_key = request.headers.get("X-API-Key")
        
        if not api_key:
            return None
        
        # Look up API key
        key = await APIKey.objects.filter(
            key=api_key,
            is_active=True,
        ).select_related("user").first()
        
        if not key:
            return None
        
        # Update last used
        key.last_used = datetime.now()
        await key.save()
        
        return (key.user, key)  # (user, auth_info)

# Use it
app.add_middleware(APIKeyAuthentication)
```

### Multiple Authentication Methods

```python
from aksara.contrib.auth import MultiAuthentication

app.add_middleware(
    MultiAuthentication,
    backends=[
        SessionAuthentication,
        TokenAuthentication,
        JWTAuthentication,
        APIKeyAuthentication,
    ],
)
```

---

## Password Management

### Hashing

```python
from aksara.contrib.auth import hash_password, check_password

# Hash a password
hashed = hash_password("mypassword123")

# Verify password
is_valid = check_password("mypassword123", hashed)
```

### Password Reset

```python
from aksara.contrib.auth.tokens import PasswordResetToken

@app.post("/auth/forgot-password")
async def forgot_password(request):
    data = await request.json()
    
    user = await User.objects.filter(email=data["email"]).first()
    if not user:
        # Don't reveal if email exists
        return {"message": "If email exists, reset link sent"}
    
    # Create reset token
    token = await PasswordResetToken.create(user)
    
    # Send email (implement your email logic)
    await send_email(
        to=user.email,
        subject="Password Reset",
        body=f"Reset link: https://app.com/reset?token={token.key}",
    )
    
    return {"message": "If email exists, reset link sent"}

@app.post("/auth/reset-password")
async def reset_password(request):
    data = await request.json()
    
    # Verify token
    token = await PasswordResetToken.objects.filter(
        key=data["token"],
        is_used=False,
        expires_at__gt=datetime.now(),
    ).first()
    
    if not token:
        return JSONResponse({"error": "Invalid or expired token"}, status_code=400)
    
    # Update password
    user = await token.user
    user.password = hash_password(data["new_password"])
    await user.save()
    
    # Mark token as used
    token.is_used = True
    await token.save()
    
    return {"message": "Password reset successful"}
```

---

## Registration

```python
from aksara.contrib.auth import User, hash_password

@app.post("/auth/register")
async def register(request):
    data = await request.json()
    
    # Check if email exists
    existing = await User.objects.filter(email=data["email"]).first()
    if existing:
        return JSONResponse({"error": "Email already registered"}, status_code=400)
    
    # Create user
    user = await User.objects.create(
        email=data["email"],
        password=data["password"],  # Auto-hashed
        name=data.get("name", ""),
    )
    
    # Optionally: send verification email
    # await send_verification_email(user)
    
    return {
        "id": str(user.id),
        "email": user.email,
        "message": "Registration successful",
    }
```

---

## Email Verification

```python
from aksara.contrib.auth.tokens import EmailVerificationToken

@app.post("/auth/send-verification")
async def send_verification(request):
    user = request.user
    
    token = await EmailVerificationToken.create(user)
    
    await send_email(
        to=user.email,
        subject="Verify your email",
        body=f"Verify: https://app.com/verify?token={token.key}",
    )
    
    return {"message": "Verification email sent"}

@app.post("/auth/verify-email")
async def verify_email(request):
    data = await request.json()
    
    token = await EmailVerificationToken.objects.filter(
        key=data["token"],
        is_used=False,
    ).first()
    
    if not token:
        return JSONResponse({"error": "Invalid token"}, status_code=400)
    
    user = await token.user
    user.email_verified = True
    await user.save()
    
    token.is_used = True
    await token.save()
    
    return {"message": "Email verified"}
```

---

## Complete Example

```python
# auth/routes.py
from fastapi import APIRouter
from aksara.contrib.auth import (
    User, authenticate, login, logout,
    hash_password, check_password,
)
from aksara.contrib.auth.jwt import (
    create_access_token, create_refresh_token,
    verify_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register")
async def register(request):
    """Register a new user."""
    data = await request.json()
    
    # Validate
    if await User.objects.filter(email=data["email"]).exists():
        return JSONResponse({"error": "Email taken"}, status_code=400)
    
    # Create user
    user = await User.objects.create(
        email=data["email"],
        password=data["password"],
        name=data.get("name", ""),
    )
    
    # Return tokens
    return {
        "user": {"id": str(user.id), "email": user.email},
        "access_token": create_access_token(user),
        "refresh_token": create_refresh_token(user),
    }


@router.post("/login")
async def login_endpoint(request):
    """Login with email and password."""
    data = await request.json()
    
    user = await authenticate(
        email=data["email"],
        password=data["password"],
    )
    
    if not user:
        return JSONResponse({"error": "Invalid credentials"}, status_code=401)
    
    if not user.is_active:
        return JSONResponse({"error": "Account disabled"}, status_code=401)
    
    # Update last login
    user.last_login = datetime.now()
    await user.save()
    
    return {
        "user": {"id": str(user.id), "email": user.email},
        "access_token": create_access_token(user),
        "refresh_token": create_refresh_token(user),
    }


@router.post("/refresh")
async def refresh(request):
    """Refresh access token."""
    data = await request.json()
    
    user = await verify_refresh_token(data.get("refresh_token"))
    if not user:
        return JSONResponse({"error": "Invalid refresh token"}, status_code=401)
    
    return {
        "access_token": create_access_token(user),
    }


@router.post("/logout")
async def logout_endpoint(request):
    """Logout (invalidate session if using sessions)."""
    await logout(request)
    return {"message": "Logged out"}


@router.get("/me")
async def me(request):
    """Get current user."""
    if not request.user.is_authenticated:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    return {
        "id": str(request.user.id),
        "email": request.user.email,
        "name": request.user.name,
        "is_staff": request.user.is_staff,
    }


@router.put("/me")
async def update_me(request):
    """Update current user."""
    if not request.user.is_authenticated:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    data = await request.json()
    user = request.user
    
    if "name" in data:
        user.name = data["name"]
    if "bio" in data:
        user.bio = data["bio"]
    
    await user.save()
    
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
    }


@router.post("/change-password")
async def change_password(request):
    """Change password."""
    if not request.user.is_authenticated:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    data = await request.json()
    user = request.user
    
    # Verify current password
    if not check_password(data["current_password"], user.password):
        return JSONResponse({"error": "Invalid current password"}, status_code=400)
    
    # Update password
    user.password = hash_password(data["new_password"])
    await user.save()
    
    return {"message": "Password changed"}
```

---

## Related Documentation

- [Permissions](permissions.md) — Access control
- [Middleware](../middleware/index.md) — Authentication middleware
- [Settings](../getting-started/settings.md) — Auth configuration
