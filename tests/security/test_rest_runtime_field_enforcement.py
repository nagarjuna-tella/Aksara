"""
Tests for runtime field enforcement wired into ModelViewSet.

Round 3: proves that raw payload bypass attempts fail at the viewset layer —
even when a field is present in the Pydantic schema, a principal that is not
allowed to write it receives a 403 with denied_fields in the response body.

These tests drive the ViewSet.create() and ViewSet.update() methods directly,
with fake request objects and fake Aksara-model-shaped classes, so they run
without a real database or HTTP server.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import BaseModel

from aksara.api.viewsets import ModelViewSet
from aksara.security.principal import Principal


# ---------------------------------------------------------------------------
# Fake model infrastructure that matches Aksara's _fields pattern
# ---------------------------------------------------------------------------


@dataclass
class FakeFieldDef:
    """Minimal field descriptor compatible with policy._iter_fields and Aksara schemas."""
    name: str
    ai_sensitive: bool = False
    ai_agent_writable: bool = True
    read_only: bool = False
    system_only: bool = False
    primary_key: bool = False
    nullable: bool = True
    # Additional attributes read by generate_create_schema / generate_update_schema
    default: Any = None
    ai_description: Optional[str] = None
    unique: bool = False
    db_index: bool = False

    @property
    def column_name(self) -> str:
        return self.name


def make_fake_model(name: str, field_defs: List[FakeFieldDef]):
    """Create a minimal Aksara-model-shaped class with the given fields."""
    attrs = {
        "_fields": {f.name: f for f in field_defs},
        "__tablename__": name.lower() + "s",
        "__name__": name,
        "_fk_fields": {},
        "_m2m_fields": {},
    }
    return type(name, (), attrs)


# Trivial Pydantic passthrough schema — used to skip real schema generation
# in tests that only want to probe the policy enforcement layer.
class _PassthroughSchema(BaseModel):
    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Fake ViewSet and request helpers
# ---------------------------------------------------------------------------


@dataclass
class FakeState:
    principal: Any = None
    is_ai_agent: bool = False
    user: Any = None
    tenant_id: Any = None


@dataclass
class FakeRequest:
    state: Any = None
    user: Any = None
    headers: dict = field(default_factory=dict)
    method: str = "PATCH"


@dataclass
class FakeUser:
    is_authenticated: bool = True
    id: str = "u1"


def make_viewset(model_cls):
    """Instantiate a ModelViewSet subclass for the given fake model.

    Sets trivial Pydantic schemas to bypass generate_*_schema() calls,
    which require full field compatibility with Aksara's field types.
    """
    class TestViewSet(ModelViewSet):
        model = model_cls
        permission_classes = []
        # Bypass schema generation — we only test the enforcement layer
        create_schema_class = _PassthroughSchema
        update_schema_class = _PassthroughSchema
        read_schema_class = _PassthroughSchema

    return TestViewSet()


def make_request_with_principal(principal: Principal, method="PATCH") -> FakeRequest:
    state = FakeState(principal=principal)
    return FakeRequest(state=state, method=method)


def make_request_with_user(user, method="PATCH") -> FakeRequest:
    state = FakeState(user=user)
    return FakeRequest(state=state, method=method)


def make_anonymous_request(method="PATCH") -> FakeRequest:
    return FakeRequest(state=FakeState(), method=method)


# ---------------------------------------------------------------------------
# Helper to run async viewset methods synchronously in tests
# ---------------------------------------------------------------------------


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# REST create enforcement tests
# ---------------------------------------------------------------------------


class TestRESTCreateEnforcement:
    def test_rest_create_rejects_raw_ai_restricted_field(self):
        """An AI agent cannot create an object with ai_agent_writable=False field."""
        InvoiceModel = make_fake_model("Invoice", [
            FakeFieldDef(name="invoice_number"),
            FakeFieldDef(name="internal_notes", ai_agent_writable=False),
        ])
        viewset = make_viewset(InvoiceModel)
        principal = Principal.for_ai_agent(scopes=["mcp:write:invoice"])
        request = make_request_with_principal(principal, method="POST")

        with pytest.raises(HTTPException) as exc_info:
            run(viewset.create(
                data={"invoice_number": "INV-1001", "internal_notes": "bypass"},
                request=request,
            ))

        assert exc_info.value.status_code == 403
        detail = exc_info.value.detail
        assert "internal_notes" in detail["denied_fields"]

    def test_rest_create_rejects_tenant_id_override(self):
        """Any non-system principal cannot override tenant_id on create."""
        OrderModel = make_fake_model("Order", [
            FakeFieldDef(name="total"),
            FakeFieldDef(name="tenant_id"),
        ])
        viewset = make_viewset(OrderModel)
        user = FakeUser()
        state = FakeState(user=user, tenant_id="t1")
        request = FakeRequest(state=state, method="POST")

        with pytest.raises(HTTPException) as exc_info:
            run(viewset.create(
                data={"total": 100, "tenant_id": "attacker-tenant"},
                request=request,
            ))

        assert exc_info.value.status_code == 403
        assert "tenant_id" in exc_info.value.detail["denied_fields"]

    def test_rest_create_rejects_read_only_field(self):
        """A read_only field must be rejected on create for any principal."""
        ArticleModel = make_fake_model("Article", [
            FakeFieldDef(name="title"),
            FakeFieldDef(name="created_at", read_only=True),
        ])
        viewset = make_viewset(ArticleModel)
        user = FakeUser()
        request = make_request_with_user(user, method="POST")

        with pytest.raises(HTTPException) as exc_info:
            run(viewset.create(
                data={"title": "Test", "created_at": "2026-01-01"},
                request=request,
            ))

        assert exc_info.value.status_code == 403
        assert "created_at" in exc_info.value.detail["denied_fields"]

    def test_rest_create_rejects_system_only_field_for_normal_user(self):
        """A system_only field must be rejected for non-system principals."""
        OrderModel = make_fake_model("Order", [
            FakeFieldDef(name="amount"),
            FakeFieldDef(name="is_deleted", system_only=True),
        ])
        viewset = make_viewset(OrderModel)
        user = FakeUser()
        request = make_request_with_user(user, method="POST")

        with pytest.raises(HTTPException) as exc_info:
            run(viewset.create(
                data={"amount": 50, "is_deleted": True},
                request=request,
            ))

        assert exc_info.value.status_code == 403
        assert "is_deleted" in exc_info.value.detail["denied_fields"]

    def test_rest_allowed_create_still_succeeds(self):
        """Legitimate create payloads must not be blocked."""
        InvoiceModel = make_fake_model("Invoice", [
            FakeFieldDef(name="invoice_number"),
            FakeFieldDef(name="amount"),
        ])
        viewset = make_viewset(InvoiceModel)
        user = FakeUser()
        request = make_request_with_user(user, method="POST")

        # Patch the actual DB call so the test doesn't need a database
        fake_instance = MagicMock()
        fake_instance.id = "uuid-1"
        with patch.object(
            InvoiceModel, "objects", create=True
        ) as mock_mgr:
            mock_mgr.create = AsyncMock(return_value=fake_instance)
            with patch.object(viewset, "_serialize", return_value={"id": "uuid-1"}):
                result = run(viewset.create(
                    data={"invoice_number": "INV-1001", "amount": 500},
                    request=request,
                ))
        assert result == {"id": "uuid-1"}

    def test_rest_create_error_payload_has_denied_fields_key(self):
        """403 response body must include denied_fields list."""
        Model = make_fake_model("Thing", [
            FakeFieldDef(name="name"),
            FakeFieldDef(name="locked", ai_agent_writable=False),
        ])
        viewset = make_viewset(Model)
        p = Principal.for_ai_agent()
        request = make_request_with_principal(p, method="POST")

        with pytest.raises(HTTPException) as exc_info:
            run(viewset.create(
                data={"name": "x", "locked": "bypass"},
                request=request,
            ))

        detail = exc_info.value.detail
        assert isinstance(detail, dict)
        assert "denied_fields" in detail
        assert "reason" in detail
        assert "detail" in detail


# ---------------------------------------------------------------------------
# REST update enforcement tests
# ---------------------------------------------------------------------------


class TestRESTUpdateEnforcement:
    def _make_saved_instance(self, model_cls):
        instance = MagicMock()
        instance.id = "obj-1"
        instance.__class__ = model_cls
        return instance

    def test_rest_update_rejects_raw_ai_restricted_field(self):
        """An AI agent update with ai_agent_writable=False field must fail."""
        InvoiceModel = make_fake_model("Invoice", [
            FakeFieldDef(name="status"),
            FakeFieldDef(name="internal_notes", ai_agent_writable=False),
        ])
        viewset = make_viewset(InvoiceModel)
        p = Principal.for_ai_agent(scopes=["mcp:write:invoice"])
        request = make_request_with_principal(p, method="PATCH")

        instance = self._make_saved_instance(InvoiceModel)
        with patch.object(InvoiceModel, "objects", create=True) as mock_mgr:
            mock_mgr.get = AsyncMock(return_value=instance)
            with pytest.raises(HTTPException) as exc_info:
                run(viewset.update(
                    pk="obj-1",
                    data={"status": "paid", "internal_notes": "tampered"},
                    request=request,
                ))

        assert exc_info.value.status_code == 403
        assert "internal_notes" in exc_info.value.detail["denied_fields"]

    def test_rest_update_rejects_tenant_id_override(self):
        """A normal user update with tenant_id must fail."""
        OrderModel = make_fake_model("Order", [
            FakeFieldDef(name="status"),
            FakeFieldDef(name="tenant_id"),
        ])
        viewset = make_viewset(OrderModel)
        user = FakeUser()
        state = FakeState(user=user, tenant_id="t1")
        request = FakeRequest(state=state, method="PATCH")

        instance = self._make_saved_instance(OrderModel)
        with patch.object(OrderModel, "objects", create=True) as mock_mgr:
            mock_mgr.get = AsyncMock(return_value=instance)
            with pytest.raises(HTTPException) as exc_info:
                run(viewset.update(
                    pk="obj-1",
                    data={"status": "shipped", "tenant_id": "evil-tenant"},
                    request=request,
                ))

        assert exc_info.value.status_code == 403
        assert "tenant_id" in exc_info.value.detail["denied_fields"]

    def test_rest_patch_rejects_read_only_field(self):
        """A read_only field must be rejected on partial update."""
        ArticleModel = make_fake_model("Article", [
            FakeFieldDef(name="title"),
            FakeFieldDef(name="created_at", read_only=True),
        ])
        viewset = make_viewset(ArticleModel)
        user = FakeUser()
        request = make_request_with_user(user, method="PATCH")

        instance = self._make_saved_instance(ArticleModel)
        with patch.object(ArticleModel, "objects", create=True) as mock_mgr:
            mock_mgr.get = AsyncMock(return_value=instance)
            with pytest.raises(HTTPException) as exc_info:
                run(viewset.update(
                    pk="obj-1",
                    data={"title": "new title", "created_at": "2020-01-01"},
                    request=request,
                ))

        assert exc_info.value.status_code == 403
        assert "created_at" in exc_info.value.detail["denied_fields"]

    def test_rest_allowed_update_still_succeeds(self):
        """Legitimate update payloads must not be blocked."""
        ArticleModel = make_fake_model("Article", [
            FakeFieldDef(name="title"),
            FakeFieldDef(name="body"),
        ])
        viewset = make_viewset(ArticleModel)
        user = FakeUser()
        request = make_request_with_user(user, method="PATCH")

        instance = MagicMock()
        instance.id = "obj-1"
        instance.save = AsyncMock()

        with patch.object(ArticleModel, "objects", create=True) as mock_mgr:
            mock_mgr.get = AsyncMock(return_value=instance)
            with patch.object(viewset, "_serialize", return_value={"id": "obj-1"}):
                result = run(viewset.update(
                    pk="obj-1",
                    data={"title": "Updated Title"},
                    request=request,
                ))
        assert result == {"id": "obj-1"}

    def test_rest_update_mcp_agent_ai_restricted_field_fails(self):
        """MCP agent cannot update a field with ai_agent_writable=False."""
        InvoiceModel = make_fake_model("Invoice", [
            FakeFieldDef(name="amount"),
            FakeFieldDef(name="approval_override", ai_agent_writable=False),
        ])
        viewset = make_viewset(InvoiceModel)
        p = Principal.for_mcp_agent(
            tenant_id="t1", scopes=["mcp:write:invoice"]
        )
        request = make_request_with_principal(p, method="PATCH")

        instance = self._make_saved_instance(InvoiceModel)
        with patch.object(InvoiceModel, "objects", create=True) as mock_mgr:
            mock_mgr.get = AsyncMock(return_value=instance)
            with pytest.raises(HTTPException) as exc_info:
                run(viewset.update(
                    pk="obj-1",
                    data={"amount": 999, "approval_override": True},
                    request=request,
                ))

        assert exc_info.value.status_code == 403
        assert "approval_override" in exc_info.value.detail["denied_fields"]

    def test_rest_update_system_principal_can_write_system_only_field(self):
        """System principal must be allowed to write system_only fields."""
        OrderModel = make_fake_model("Order", [
            FakeFieldDef(name="status"),
            FakeFieldDef(name="is_deleted", system_only=True),
        ])
        viewset = make_viewset(OrderModel)
        p = Principal.system()
        request = make_request_with_principal(p, method="PATCH")

        instance = MagicMock()
        instance.id = "obj-1"
        instance.save = AsyncMock()

        with patch.object(OrderModel, "objects", create=True) as mock_mgr:
            mock_mgr.get = AsyncMock(return_value=instance)
            with patch.object(viewset, "_serialize", return_value={"id": "obj-1"}):
                result = run(viewset.update(
                    pk="obj-1",
                    data={"status": "cancelled", "is_deleted": True},
                    request=request,
                ))
        assert result == {"id": "obj-1"}


# ---------------------------------------------------------------------------
# Bulk update / upsert surface notes
# ---------------------------------------------------------------------------
# bulk_update (manager.py:bulk_update) and upsert (manager.py:upsert) are
# lower-level manager operations that take model instances / field names rather
# than raw JSON payloads. They are called programmatically, not directly from
# client HTTP requests, and do not have a request/principal context in their
# signatures.
#
# Round 3 enforcement is at the REST viewset boundary (create/update). Callers
# of bulk_update/upsert from inside the application are assumed trusted; those
# that come from HTTP routes go through the viewset enforcement first.
#
# Studio write paths are all internal tooling endpoints (AI flows, diagnostics)
# and do not expose user-data model CRUD. They are not covered by REST field
# enforcement in Round 3 and are documented as remaining work.
#
# These surfaces are marked in the security matrix as:
#   - bulk_update: partial (enforcement pattern documented; not wired yet)
#   - upsert: partial (enforcement pattern documented; not wired yet)
#   - Studio create/update: planned
