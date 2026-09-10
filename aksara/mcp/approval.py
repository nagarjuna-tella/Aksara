"""Cryptographic approval grants bound to one exact MCP mutation."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from aksara.security.principal import Principal


class ApprovalError(ValueError):
    """An approval grant is absent, invalid, rejected, expired, or mismatched."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ApprovalContext:
    approval_id: str
    approved_by: str | None
    expires_at: float


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def _arguments_hash(arguments: Mapping[str, Any]) -> str:
    clean = {key: value for key, value in arguments.items() if key != "_approval_token"}
    return hashlib.sha256(_canonical(clean)).hexdigest()


def _principal_key(principal: Principal) -> str:
    values = (
        principal.auth_method,
        principal.user_id,
        principal.human_owner_id,
        principal.agent_id,
        principal.token_id,
        principal.tenant_id,
    )
    return hashlib.sha256(_canonical(values)).hexdigest()


class ApprovalManager:
    """Issue and verify signed grants without claiming durable workflow state."""

    def __init__(self, secret: str | bytes | None):
        self._secret = secret.encode() if isinstance(secret, str) else secret

    @property
    def configured(self) -> bool:
        return bool(self._secret)

    def issue(
        self,
        *,
        principal: Principal,
        tool_name: str,
        arguments: Mapping[str, Any],
        approved_by: str,
        ttl_seconds: float = 300.0,
        approved: bool = True,
        approval_id: str | None = None,
    ) -> str:
        if not self._secret:
            raise ApprovalError("approval_unavailable", "MCP approval signing is not configured.")
        now = time.time()
        payload = {
            "approval_id": approval_id or uuid.uuid4().hex,
            "approved": approved,
            "approved_by": approved_by,
            "arguments_sha256": _arguments_hash(arguments),
            "expires_at": now + ttl_seconds,
            "issued_at": now,
            "principal_sha256": _principal_key(principal),
            "tenant_id": principal.tenant_id,
            "tool_name": tool_name,
            "version": 1,
        }
        body = _encode(_canonical(payload))
        signature = _encode(hmac.new(self._secret, body.encode(), hashlib.sha256).digest())
        return f"{body}.{signature}"

    def verify(
        self,
        token: str | None,
        *,
        principal: Principal,
        tool_name: str,
        arguments: Mapping[str, Any],
    ) -> ApprovalContext:
        if not token:
            raise ApprovalError("approval_required", "This tool requires human approval.")
        if not self._secret:
            raise ApprovalError("approval_unavailable", "MCP approval signing is not configured.")
        try:
            body, signature = token.split(".", 1)
            expected = _encode(hmac.new(self._secret, body.encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(signature, expected):
                raise ApprovalError("approval_invalid", "Approval signature is invalid.")
            payload = json.loads(_decode(body))
        except ApprovalError:
            raise
        except Exception as exc:
            raise ApprovalError("approval_invalid", "Approval token is malformed.") from exc

        if not payload.get("approved"):
            raise ApprovalError("approval_rejected", "The proposed operation was rejected.")
        if float(payload.get("expires_at", 0)) <= time.time():
            raise ApprovalError("approval_expired", "Approval has expired.")
        if payload.get("tool_name") != tool_name:
            raise ApprovalError("approval_mismatch", "Approval is for a different tool.")
        if payload.get("tenant_id") != principal.tenant_id:
            raise ApprovalError("approval_tenant_mismatch", "Approval belongs to a different tenant.")
        if payload.get("principal_sha256") != _principal_key(principal):
            raise ApprovalError("approval_principal_mismatch", "Approval belongs to a different principal.")
        if payload.get("arguments_sha256") != _arguments_hash(arguments):
            raise ApprovalError("approval_arguments_mismatch", "Approval arguments do not match this invocation.")
        return ApprovalContext(
            approval_id=str(payload["approval_id"]),
            approved_by=str(payload["approved_by"]) if payload.get("approved_by") else None,
            expires_at=float(payload["expires_at"]),
        )


__all__ = ["ApprovalContext", "ApprovalError", "ApprovalManager"]
