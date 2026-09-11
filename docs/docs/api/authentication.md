# Authentication and request identity

**Stable within the documented backend boundary.** Authentication establishes
who is calling. Permissions and PolicyEngine decide what that caller may do.
A header, user ID, or tenant ID supplied by a client is not authenticated
identity by itself.

For a complete running application, start with the
[ticket-desk authentication adapter](../getting-started/first-project.md), then
add [tenant membership and roles](../tutorials/ticket-desk-tenancy.md). Those
examples verify credentials on the server and attach both the canonical
Principal and the user-shaped state used by permission classes.

## Connect an identity provider to the application

The application owns credential validation: for example, a server-managed API
token, a validated session, or a JWT verified with your identity provider's
keys, issuer, audience, and expiry rules. After validation, resolve current
account status, roles, and tenant membership from trusted state.

Attach `request.state.principal` for PolicyEngine and
`request.state.user` for the permission/dependency compatibility surface. Keep
them consistent. The user-shaped object supplies `id`, `is_authenticated`,
`is_active`, `is_staff`, and `is_superuser` as needed by your permissions.
A `Principal` alone does not expose every one of those user attributes.

`Principal.for_user(...)` constructs an authenticated identity; it does **not**
verify credentials or check membership. Never construct it from an unverified
user ID or client-provided roles. Reset request context in `finally` when your
adapter sets tenant or user context variables; the tenancy tutorial shows this
lifecycle.

The old `AuthenticationMiddleware`, `TokenAuthentication`, `JWTAuthentication`,
`login()`, and `logout()` recipes on this page are not a supported turnkey
application-authentication stack. Aksara provides backend primitives and optional
contrib authentication; choose and implement the application's login/session
boundary explicitly.

## Use the optional built-in user model

`aksara.contrib.auth.User` stores `email`, **`hashed_password`**, status flags,
optional `metadata`, and the inherited ID/timestamps. It has no plain `password`
field or `user.check_password()` method. Use `create_user()` to hash a password;
ordinary `objects.create(password=...)` is not that contract.

Enable `aksara.contrib.auth` in the global `installed_apps` configuration and
apply its internal migrations with the migration role before using the account
helpers. The application database must be connected. See
[configuration](../reference/settings-reference.md),
[migrations](../orm/migrations.md), and
[production roles](../tutorials/deployment.md).

These complete service functions can live in `app/accounts.py`:

```python title="app/accounts.py"
from aksara.contrib.auth import User, verify_password


async def create_account(email: str, password: str):
    # The application must validate signup eligibility and password policy first.
    return await User.objects.create_user(email=email, password=password)


async def authenticate_account(email: str, password: str):
    # Returns an active User or None. Does not issue a cookie, token, or Principal.
    return await User.objects.authenticate(email=email, password=password)


def password_matches(user: User, password: str) -> bool:
    return verify_password(password, user.hashed_password)
```

`create_user()` normalizes email and defaults to an active, non-staff,
non-superuser account. `authenticate()` rejects a wrong password, unknown
account, or inactive account. It is not a password-policy validator or a
rate limiter. A failed authentication result also does not prove database health;
check operational failures through your diagnostics and logs.

Do not return a whole user record from a public registration endpoint. Select
response fields explicitly and exclude `hashed_password`, status flags, and
private metadata. Do not let signup payloads set `is_staff` or `is_superuser`.

For a custom user model, subclass `AbstractUser` and deliberately configure its
manager and authentication integration. The built-in helpers and session
lookup target the concrete built-in `User`; a subclass does not automatically
replace it throughout the framework.

## Understand the FastAPI dependencies

| Helper | What it actually does |
|---|---|
| `get_current_user(request)` | Reads the user already attached to `request.state`; does not parse or validate a bearer token |
| `get_current_active_user(request)` | Also rejects an inactive attached user |
| `require_auth()` | Creates a dependency requiring an active attached user; default denial is HTTP 401 |
| `require_staff()` | Requires an active user and the `is_staff` flag; missing user is 401, non-staff is 403 |
| `require_superuser()` | Requires an active user and `is_superuser`; missing user is 401, insufficient role is 403 |

Use these only after your authentication adapter is installed. Their presence
on an endpoint does not manufacture authenticated state. Generated ViewSet
permission denials use HTTP 403; do not infer a universal authentication error
code from one helper. See [permissions](permissions.md).

## Sessions, registration, and recovery

Contrib auth also exports `create_session_token(db, user, expires_in=...)`,
`get_user_from_session_token(db, token)`, `invalidate_session_token(db, token)`,
and `cleanup_expired_sessions(db)`. These manage opaque tokens in
`aksara_sessions`. They require provisioned tables and do not set a response
cookie or install a general application authentication middleware.

The application owns its HTTP login/logout routes, cookie settings, CSRF
protection for cookie-authenticated writes, rate limits, signup policy, email
verification, password reset, session revocation policy, and secret handling.
Admin has its own login flow; it is not a ready-made application identity
provider. Do not copy the historical password-reset or email-verification
methods from this page: they were not APIs exported by the installed package.

## Humans, tools, and delayed work

An MCP token identifies a machine actor with provenance, scopes, and expiry;
it is not interchangeable with a human login cookie. Use the
[official MCP client tutorial](../tutorials/ticket-desk-mcp.md) to carry that
identity through generated execution.

Ordinary tasks do not persist a complete Principal. Durable Operations instead
store an identity reference that your resolver uses to reconstruct current
authority at execution time. See [application boundaries](../concepts/application-boundaries.md)
and [Durable Operations](../advanced/durable-operations.md).
