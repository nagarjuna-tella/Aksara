# Caching

Aksara 0.6.1 does not ship a public general-purpose `aksara.cache` API. Earlier
conceptual documentation described cache backends, decorators, and queryset
caching that are not present in the installed package.

Applications can use a cache library directly for application-owned derived
values. Keep authorization and tenant scope in every cache key, choose an
explicit invalidation policy, and never use cached visibility decisions as a
substitute for current `Principal`, permission, policy, tenant, or RLS checks.

A framework cache contract remains out of scope for v0.6.1. The v0.7 durable
operation direction also does not require Redis or a new general cache API.
