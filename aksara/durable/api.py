"""Explicit opt-in HTTP boundary for durable operation semantics."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from aksara.durable.errors import (
    ApprovalConflict,
    AuthorizationDenied,
    CancellationConflict,
    DurableOperationError,
    IdempotencyConflict,
    IdempotencyIdentityExpired,
    OperationNotFound,
)
from aksara.durable.service import DurableOperationService
from aksara.durable.types import OperationRecord, PrincipalReference
from aksara.security.context import principal_from_request
from aksara.security.principal import Principal

PrincipalReferenceFactory = Callable[
    [Principal, Request], PrincipalReference | Awaitable[PrincipalReference]
]


class DurableDispatchRequest(BaseModel):
    action: str = Field(min_length=1, max_length=255)
    action_version: str = Field(min_length=1, max_length=64)
    command: dict[str, Any]
    available_at: datetime | None = None
    deadline_at: datetime | None = None
    max_attempts: int | None = Field(default=None, ge=1, le=1000)


class DurableCancellationRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class DurableApprovalRequest(BaseModel):
    approve: bool
    reason: str | None = Field(default=None, max_length=1000)


class DurableOperationResponse(BaseModel):
    id: UUID
    application_namespace: str
    tenant_id: str | None
    action: str
    action_version: str
    effect_class: str
    state: str
    state_version: int
    attempt_count: int
    max_attempts: int
    available_at: datetime
    deadline_at: datetime | None
    cancellation_requested_at: datetime | None
    result: Any = None
    result_expires_at: datetime | None = None
    error: Any = None
    error_expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    retain_until: datetime


class DurableDispatchResponse(BaseModel):
    operation: DurableOperationResponse
    created: bool
    status_url: str


def _response(operation: OperationRecord) -> DurableOperationResponse:
    return DurableOperationResponse(
        id=operation.id,
        application_namespace=operation.application_namespace,
        tenant_id=operation.tenant_id,
        action=operation.action_name,
        action_version=operation.action_version,
        effect_class=operation.effect_class.value,
        state=operation.state.value,
        state_version=operation.state_version,
        attempt_count=operation.attempt_count,
        max_attempts=operation.max_attempts,
        available_at=operation.available_at,
        deadline_at=operation.deadline_at,
        cancellation_requested_at=operation.cancellation_requested_at,
        result=operation.result,
        result_expires_at=operation.result_expires_at,
        error=operation.error,
        error_expires_at=operation.error_expires_at,
        created_at=operation.created_at,
        updated_at=operation.updated_at,
        completed_at=operation.completed_at,
        retain_until=operation.retain_until,
    )


async def _reference(
    factory: PrincipalReferenceFactory,
    principal: Principal,
    request: Request,
) -> PrincipalReference:
    value = factory(principal, request)
    if inspect.isawaitable(value):
        value = await value
    if not isinstance(value, PrincipalReference):
        raise TypeError("principal_reference_factory must return PrincipalReference")
    expected_kind = (
        "system"
        if principal.is_system
        else ("agent" if principal.is_ai_agent else "user")
    )
    if value.principal_kind != expected_kind or value.tenant_id != principal.tenant_id:
        raise AuthorizationDenied(
            "principal reference identity does not match the current principal"
        )
    if not principal.is_system and (
        value.subject_id != principal.user_id
        or value.human_owner_id != principal.human_owner_id
        or value.agent_id != principal.agent_id
        or value.credential_id != principal.token_id
    ):
        raise AuthorizationDenied(
            "principal reference identity does not match the current principal"
        )
    return value


def _principal(request: Request) -> Principal:
    principal = principal_from_request(request)
    if principal.is_anonymous:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return principal


def _raise_http(error: Exception) -> None:
    if isinstance(error, OperationNotFound):
        raise HTTPException(status_code=404, detail={"code": error.code}) from error
    if isinstance(error, AuthorizationDenied):
        raise HTTPException(status_code=403, detail={"code": error.code}) from error
    if isinstance(error, (IdempotencyConflict, ApprovalConflict, CancellationConflict)):
        raise HTTPException(status_code=409, detail={"code": error.code}) from error
    if isinstance(error, IdempotencyIdentityExpired):
        raise HTTPException(status_code=410, detail={"code": error.code}) from error
    if isinstance(error, DurableOperationError):
        raise HTTPException(status_code=422, detail={"code": error.code}) from error
    raise error


def create_durable_operations_router(
    service: DurableOperationService,
    *,
    principal_reference_factory: PrincipalReferenceFactory,
    prefix: str = "/durable/operations",
    tags: list[str] | None = None,
) -> APIRouter:
    """Build an explicitly mounted durable dispatch/status/cancel router."""

    router_tags: list[str | Enum] = list(tags) if tags else ["Durable Operations"]
    router = APIRouter(prefix=prefix, tags=router_tags)

    @router.post("", response_model=DurableDispatchResponse, status_code=202)
    async def dispatch(
        payload: DurableDispatchRequest,
        request: Request,
        response: Response,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> DurableDispatchResponse:
        principal = _principal(request)
        correlation: dict[str, Any] = {}
        for key in ("request_id", "correlation_id"):
            value = getattr(request.state, key, None)
            if value is not None:
                correlation[key] = str(value)
        try:
            reference = await _reference(principal_reference_factory, principal, request)
            admission = await service.admit(
                payload.action,
                payload.action_version,
                payload.command,
                reference,
                idempotency_key=idempotency_key,
                available_at=payload.available_at,
                deadline_at=payload.deadline_at,
                max_attempts=payload.max_attempts,
                correlation=correlation,
            )
        except DurableOperationError as error:
            _raise_http(error)
            raise AssertionError("unreachable")
        status_url = f"{prefix}/{admission.operation.id}"
        response.headers["Location"] = status_url
        if not admission.created and admission.operation.terminal:
            response.status_code = status.HTTP_200_OK
        return DurableDispatchResponse(
            operation=_response(admission.operation),
            created=admission.created,
            status_url=status_url,
        )

    @router.get("/{operation_id}", response_model=DurableOperationResponse)
    async def get_status(operation_id: UUID, request: Request) -> DurableOperationResponse:
        principal = _principal(request)
        try:
            operation = await service.get(
                operation_id,
                tenant_id=principal.tenant_id,
                principal=principal,
            )
        except DurableOperationError as error:
            _raise_http(error)
            raise AssertionError("unreachable")
        return _response(operation)

    @router.post("/{operation_id}/cancel", response_model=DurableOperationResponse)
    async def cancel(
        operation_id: UUID,
        payload: DurableCancellationRequest,
        request: Request,
    ) -> DurableOperationResponse:
        principal = _principal(request)
        try:
            reference = await _reference(principal_reference_factory, principal, request)
            operation = await service.request_cancellation(
                operation_id,
                tenant_id=principal.tenant_id,
                principal=principal,
                requester_reference=reference,
                reason=payload.reason,
            )
        except DurableOperationError as error:
            _raise_http(error)
            raise AssertionError("unreachable")
        return _response(operation)

    @router.post("/{operation_id}/decision", response_model=DurableOperationResponse)
    async def decide(
        operation_id: UUID,
        payload: DurableApprovalRequest,
        request: Request,
    ) -> DurableOperationResponse:
        principal = _principal(request)
        try:
            reference = await _reference(principal_reference_factory, principal, request)
            operation = await service.decide_approval(
                operation_id,
                tenant_id=principal.tenant_id,
                approver=principal,
                approver_reference=reference,
                approve=payload.approve,
                reason=payload.reason,
            )
        except DurableOperationError as error:
            _raise_http(error)
            raise AssertionError("unreachable")
        return _response(operation)

    return router


__all__ = [
    "DurableApprovalRequest",
    "DurableCancellationRequest",
    "DurableDispatchRequest",
    "DurableDispatchResponse",
    "DurableOperationResponse",
    "PrincipalReferenceFactory",
    "create_durable_operations_router",
]
