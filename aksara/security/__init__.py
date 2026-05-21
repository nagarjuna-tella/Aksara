"""
Aksara Security Module

Round 1: Security baseline — matrix loader, validator, and check helpers.
Round 2: Principal, PolicyDecision, PolicyEngine, context resolvers, adapters.

Public API::

    from aksara.security import Principal, PolicyDecision, PolicyEngine
    from aksara.security import default_policy, get_policy_engine
    from aksara.security import (
        anonymous_principal,
        system_principal,
        principal_from_request,
        principal_from_user,
        principal_from_mcp_claims,
        principal_from_ai_agent,
    )
    from aksara.security.exceptions import PolicyDenied, SecurityError
"""

from aksara.security.decisions import PolicyDecision
from aksara.security.exceptions import PolicyDenied, PrincipalResolutionError, SecurityError, TenantContextMissing
from aksara.security.policy import PolicyEngine, default_policy, get_policy_engine
from aksara.security.principal import AuthMethod, Principal
from aksara.security.context import (
    anonymous_principal,
    system_principal,
    principal_from_user,
    principal_from_request,
    principal_from_mcp_claims,
    principal_from_ai_agent,
)
from aksara.security.enforcement import (
    enforce_payload_policy,
    enforce_request_payload_policy,
    policy_denied_to_error_payload,
)

__all__ = [
    # Principal
    "Principal",
    "AuthMethod",
    # PolicyDecision
    "PolicyDecision",
    # PolicyEngine
    "PolicyEngine",
    "default_policy",
    "get_policy_engine",
    # Context resolvers
    "anonymous_principal",
    "system_principal",
    "principal_from_user",
    "principal_from_request",
    "principal_from_mcp_claims",
    "principal_from_ai_agent",
    # Runtime enforcement (Round 3)
    "enforce_payload_policy",
    "enforce_request_payload_policy",
    "policy_denied_to_error_payload",
    # Exceptions
    "SecurityError",
    "PolicyDenied",
    "PrincipalResolutionError",
    "TenantContextMissing",
]
