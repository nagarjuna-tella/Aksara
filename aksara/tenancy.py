"""Multi-tenancy model helpers for PostgreSQL row-level security."""

from __future__ import annotations

from aksara.db.tenant_context import (
    TENANT_SETTING_NAME,
    apply_tenant_context,
    build_disable_rls_sql,
    build_enable_rls_sql,
    get_tenant_policy_name,
    reset_tenant_context,
)
from aksara.fields import UUID
from aksara.model.base import Model


class TenantModel(Model):
    """Abstract base model for tenant-scoped data.

    Inheriting from TenantModel adds a required ``tenant_id`` UUID column and
    marks the model so makemigrations emits PostgreSQL RLS policy operations.
    """

    __abstract__ = True

    tenant_id = UUID()


def is_tenant_model(model_class: type[Model]) -> bool:
    """Return True when a model class is tenant-scoped."""
    return bool(getattr(model_class, "tenant_id", None) or "tenant_id" in getattr(model_class, "_fields", {})) and issubclass(model_class, TenantModel)


__all__ = [
    "TENANT_SETTING_NAME",
    "TenantModel",
    "apply_tenant_context",
    "build_disable_rls_sql",
    "build_enable_rls_sql",
    "get_tenant_policy_name",
    "is_tenant_model",
    "reset_tenant_context",
]