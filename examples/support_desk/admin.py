"""Explicit Admin registrations for support desk operators."""

from typing import ClassVar

from aksara.contrib.admin import ModelAdmin, admin_site

from .models import DeliveryAttempt, Organization, SupportAgent, Ticket


@admin_site.register(Organization)
class OrganizationAdmin(ModelAdmin):
    list_display: ClassVar = ["name", "slug", "created_at"]
    search_fields: ClassVar = ["name", "slug"]


@admin_site.register(SupportAgent)
class SupportAgentAdmin(ModelAdmin):
    list_display: ClassVar = ["name", "role", "is_active", "tenant_id"]
    list_filter: ClassVar = ["role", "is_active"]
    search_fields: ClassVar = ["name", "email"]


@admin_site.register(Ticket)
class TicketAdmin(ModelAdmin):
    list_display: ClassVar = ["subject", "status", "priority", "assigned_to", "tenant_id"]
    list_filter: ClassVar = ["status", "priority"]
    search_fields: ClassVar = ["subject", "description"]


@admin_site.register(DeliveryAttempt)
class DeliveryAttemptAdmin(ModelAdmin):
    list_display: ClassVar = ["ticket", "attempts", "delivered", "tenant_id", "updated_at"]
    list_filter: ClassVar = ["delivered"]
