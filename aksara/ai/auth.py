"""
Aksara AI Agent Token Signing and Verification

HMAC-SHA256 short-lived tokens for AI agent request authentication.

v0.5.40: Added signed agent tokens

Usage::

    from aksara.ai.auth import sign_agent_token, verify_agent_token

    # Issuer side
    token = sign_agent_token(agent_id="my-agent", secret="secret-key")

    # Verifier side (raises ValueError on failure)
    payload = verify_agent_token(token, secret="secret-key")
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

_ALGORITHM = "sha256"
_SEPARATOR = b"."


def _b64_encode(data: bytes) -> str:
    """URL-safe base64 without padding."""
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64_decode(data: str) -> bytes:
    """URL-safe base64 decode, restoring padding."""
    import base64
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


def sign_agent_token(
    agent_id: str,
    secret: str,
    *,
    ttl_seconds: int = 300,
    extra: dict[str, Any] | None = None,
) -> str:
    """Return a signed agent token valid for *ttl_seconds*.

    The token format is ``<header>.<payload>.<signature>`` where each part is
    URL-safe base64 without padding.  The payload JSON contains at minimum:

    * ``agent_id`` — the agent identifier
    * ``iat`` — issued-at Unix timestamp (int)
    * ``exp`` — expiry Unix timestamp (int)

    Args:
        agent_id: Identifier for the agent (e.g. ``"aksara-codegen"``).
        secret: Shared secret used for HMAC signing.
        ttl_seconds: Token lifetime in seconds (default 300).
        extra: Optional additional claims to embed in the payload.

    Returns:
        A compact ``header.payload.signature`` string.
    """
    if not agent_id:
        raise ValueError("agent_id must not be empty")
    if not secret:
        raise ValueError("secret must not be empty")

    now = int(time.time())
    payload: dict[str, Any] = {
        "agent_id": agent_id,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    if extra:
        payload.update(extra)

    header = _b64_encode(json.dumps({"alg": _ALGORITHM, "typ": "AKT"}).encode())
    body = _b64_encode(json.dumps(payload, separators=(",", ":")).encode())

    signing_input = f"{header}.{body}".encode()
    sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    return f"{header}.{body}.{_b64_encode(sig)}"


def verify_agent_token(
    token: str,
    secret: str,
    *,
    clock_skew_seconds: int = 0,
) -> dict[str, Any]:
    """Verify and decode a signed agent token.

    Args:
        token: The compact token string produced by :func:`sign_agent_token`.
        secret: The shared secret used for verification.
        clock_skew_seconds: Extra tolerance (in seconds) added to both
            ``iat`` and ``exp`` checks to accommodate minor clock drift.

    Returns:
        The decoded payload ``dict`` if the token is valid.

    Raises:
        ValueError: If the token format, signature, or expiry is invalid.
    """
    if not secret:
        raise ValueError("secret must not be empty")

    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format")

    header_b64, body_b64, sig_b64 = parts

    # --- Verify signature first (constant-time) ----------------------------
    signing_input = f"{header_b64}.{body_b64}".encode()
    expected_sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    try:
        actual_sig = _b64_decode(sig_b64)
    except Exception as exc:
        raise ValueError("Invalid token encoding") from exc

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("Token signature is invalid")

    # --- Decode payload -----------------------------------------------------
    try:
        payload = json.loads(_b64_decode(body_b64))
    except Exception as exc:
        raise ValueError("Invalid token payload") from exc

    # --- Validate claims ----------------------------------------------------
    now = int(time.time())

    exp = payload.get("exp")
    if exp is not None and now > exp + clock_skew_seconds:
        raise ValueError("Token has expired")

    iat = payload.get("iat")
    if iat is not None and iat > now + clock_skew_seconds:
        raise ValueError("Token issued in the future")

    return payload
