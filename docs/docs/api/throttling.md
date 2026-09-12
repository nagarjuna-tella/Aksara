# Throttling

Aksara v0.7.0 includes a best-effort **Admin POST rate limit**. Generated
`ModelViewSet` APIs do not expose a general `throttle_classes` contract.
Configure application or gateway limits separately for REST endpoints, custom
actions, and MCP traffic. The Admin settings do not cover those surfaces.

## Admin controls

The Admin integration applies the limiter to POST requests below its mounted
prefix, normally `/admin/`. Its defaults are:

| Setting | Environment variable | Default |
| --- | --- | --- |
| `admin_rate_limit_enabled` | `AKSARA_ADMIN_RATE_LIMIT_ENABLED` | `True` |
| `admin_rate_limit_requests` | `AKSARA_ADMIN_RATE_LIMIT_REQUESTS` | `20` |
| `admin_rate_limit_window_seconds` | `AKSARA_ADMIN_RATE_LIMIT_WINDOW_SECONDS` | `60` |

Each bucket combines client address and request path. The limiter counts
requests in the configured rolling window and rejects excess requests with
HTTP 429 and a `Retry-After` header. It applies before the downstream handler,
so the bucket counts attempts, not only successful mutations. GET requests and
paths outside the mounted Admin prefix are not covered.

The counters live in application process memory. They are not shared across
workers and reset when the process restarts. Treat this as a local protective
control, not a distributed quota or durable abuse ledger.

The implementation uses the direct client address, except that it accepts the
first `X-Forwarded-For` value when the direct peer is loopback (`127.0.0.1` or
`::1`). Configure your proxy to overwrite untrusted forwarded headers and
verify the effective client address in your deployment. Do not assume arbitrary
proxy chains are recognized automatically.

## Application API limits

Define the endpoints, identity or address key, request budget, window, and
response behavior required by your application. Install and configure your
chosen middleware or gateway explicitly; adding a ViewSet attribute does not
create enforcement. If a limit must span workers, its counter must also span
workers.

Verify the boundary with actual HTTP requests: requests below the budget should
reach the intended handler, excess requests should be rejected, unrelated
identities should have the intended independent budgets, and restart or
multi-worker behavior should match your documented policy. Test through the
production proxy path as well as directly against the application.

Rate limits do not replace [authentication](authentication.md),
[permissions](permissions.md), tenant isolation, or payload validation. MCP
execution budgets and Durable Operation idempotency solve different problems;
neither establishes a general HTTP request-rate limit.

## Related documentation

- [Settings reference](../reference/settings-reference.md) — configuration and precedence
- [Deployment](../tutorials/deployment.md) — production process and proxy responsibilities
- [Actions](actions.md) — explicit authorization for custom HTTP handlers
