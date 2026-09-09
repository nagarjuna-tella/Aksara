"""Data model for the production-shaped support desk reference app."""

from aksara import Model, TenantModel, fields


class Organization(Model):
    name = fields.String(max_length=160, ai_description="Customer organization name")
    slug = fields.String(max_length=80, unique=True, ai_description="Stable organization slug")
    created_at = fields.DateTime(auto_now_add=True)
    updated_at = fields.DateTime(auto_now=True)

    class Meta:
        table_name = "support_organizations"
        app_label = "support_desk"
        ai_name = "Organization"
        ai_description = "Support desk tenant directory"
        ai_agent_exposed = False


class SupportAgent(TenantModel):
    name = fields.String(max_length=120, ai_description="Agent display name")
    email = fields.String(
        max_length=255,
        ai_description="Agent email address",
        ai_sensitive=True,
    )
    role = fields.String(
        max_length=40,
        default="agent",
        ai_description="Agent authorization role",
        ai_agent_writable=False,
    )
    is_active = fields.Boolean(default=True, ai_agent_writable=False)
    created_at = fields.DateTime(auto_now_add=True)
    updated_at = fields.DateTime(auto_now=True)

    class Meta:
        table_name = "support_agents"
        app_label = "support_desk"
        ai_name = "Support agent"
        ai_description = "Human support agent within one tenant"
        ai_agent_exposed = True


class Ticket(TenantModel):
    subject = fields.String(max_length=200, ai_description="Concise customer issue")
    description = fields.Text(ai_description="Customer issue details")
    status = fields.String(
        max_length=32,
        default="open",
        ai_description="Ticket state: open, pending, resolved",
    )
    priority = fields.String(
        max_length=20,
        default="normal",
        ai_description="Ticket priority: low, normal, high, urgent",
    )
    assigned_to = fields.ForeignKey(
        "SupportAgent",
        on_delete="SET NULL",
        nullable=True,
        ai_description="Assigned support agent",
    )
    created_at = fields.DateTime(auto_now_add=True)
    updated_at = fields.DateTime(auto_now=True)

    class Meta:
        table_name = "support_tickets"
        app_label = "support_desk"
        ai_name = "Support ticket"
        ai_description = "Tenant-scoped customer support ticket"
        ai_agent_exposed = True


class DeliveryAttempt(TenantModel):
    ticket = fields.ForeignKey(
        "Ticket",
        on_delete="CASCADE",
        ai_description="Ticket being delivered to an external system",
    )
    attempts = fields.Integer(default=0, ai_agent_writable=False)
    delivered = fields.Boolean(default=False, ai_agent_writable=False)
    last_error = fields.Text(nullable=True, ai_sensitive=True, ai_agent_writable=False)
    created_at = fields.DateTime(auto_now_add=True)
    updated_at = fields.DateTime(auto_now=True)

    class Meta:
        table_name = "support_delivery_attempts"
        app_label = "support_desk"
        ai_name = "Delivery attempt"
        ai_description = "Durable delivery state for a support ticket"
        ai_agent_exposed = False
