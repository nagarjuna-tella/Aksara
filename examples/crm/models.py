"""
CRM Example - Models

Demonstrates:
- Customer model with contact info and PII protection
- Deal model with pipeline stages and AI write guards
- Activity model with FK chain (Customer → Deal → Activity)
- AI metadata: ai_description, ai_sensitive, ai_agent_writable
"""

from aksara import Model, fields


class Customer(Model):
    """
    Customer record for CRM.
    
    Stores contact information and notes about the customer.
    Email and phone are marked ai_sensitive=True because they are PII —
    this excludes them from AI Console context and MCP tool exports.
    """
    
    name = fields.String(
        max_length=200,
        ai_description="Customer or company name",
    )
    email = fields.String(
        max_length=255,
        nullable=True,
        ai_description="Primary contact email",
        ai_sensitive=True,  # PII — excluded from AI context and MCP exports
    )
    phone = fields.String(
        max_length=50,
        nullable=True,
        ai_description="Phone number",
        ai_sensitive=True,  # PII — excluded from AI context and MCP exports
    )
    industry = fields.String(
        max_length=100,
        nullable=True,
        ai_description="Industry or sector (e.g., 'Technology', 'Healthcare')",
    )
    company_size = fields.String(
        max_length=50,
        nullable=True,
        ai_description="Company size category (e.g., 'SMB', 'Enterprise')",
    )
    notes = fields.Text(
        nullable=True,
        ai_description="Internal notes about the customer — useful for AI-powered account summaries",
    )
    created_at = fields.DateTime(
        auto_now_add=True,
        ai_description="When the customer record was created",
    )
    
    class Meta:
        table_name = "customers"
        ai_name = "Customer"
        ai_description = "Customer record with contact information"
        ai_agent_exposed = True


class Deal(Model):
    """
    Sales deal in the pipeline.
    
    Features:
    - Linked to Customer
    - Pipeline stages (lead, qualified, proposal, negotiation, closed_won, closed_lost)
    - Probability percentage for forecasting
    - Expected close date
    
    amount and stage are marked ai_agent_writable=False because deal values
    and stage transitions should go through explicit actions (advance_stage,
    close_won, mark_lost), not raw AI writes.
    """
    
    # Pipeline stage choices
    STAGE_LEAD = "lead"
    STAGE_QUALIFIED = "qualified"
    STAGE_PROPOSAL = "proposal"
    STAGE_NEGOTIATION = "negotiation"
    STAGE_CLOSED_WON = "closed_won"
    STAGE_CLOSED_LOST = "closed_lost"
    
    customer = fields.ForeignKey(
        "Customer",
        on_delete="CASCADE",
        ai_description="The customer this deal is with",
    )
    title = fields.String(
        max_length=200,
        ai_description="Deal title or description",
    )
    amount = fields.Decimal(
        max_digits=12,
        decimal_places=2,
        ai_description="Deal value in currency",
        ai_agent_writable=False,  # Deal values should be set by humans, not AI agents
    )
    stage = fields.String(
        max_length=50,
        default="lead",
        ai_description="Pipeline stage: lead, qualified, proposal, negotiation, closed_won, closed_lost",
        ai_agent_writable=False,  # Use advance_stage/close_won/mark_lost actions instead
    )
    probability = fields.Integer(
        default=10,
        ai_description="Win probability percentage (0-100)",
    )
    close_date = fields.DateTime(
        nullable=True,
        ai_description="Expected or actual close date",
    )
    notes = fields.Text(
        nullable=True,
        ai_description="Notes about the deal",
    )
    created_at = fields.DateTime(
        auto_now_add=True,
        ai_description="When the deal was created",
    )
    updated_at = fields.DateTime(
        auto_now=True,
        ai_description="When the deal was last updated",
    )
    
    class Meta:
        table_name = "deals"
        ai_name = "Deal"
        ai_description = "Sales deal with amount, stage, and probability"
        ai_agent_exposed = True
    
    @property
    def expected_revenue(self) -> float:
        """Calculate expected revenue: amount * probability / 100."""
        return float(self.amount) * (self.probability / 100)


class Activity(Model):
    """
    Activity log entry for a deal.
    
    Tracks calls, emails, meetings, and other interactions.
    Demonstrates a three-level FK chain: Customer → Deal → Activity.
    
    notes has a rich ai_description because it's exactly the kind of
    free-text field an AI assistant would query when summarizing
    account history.
    """
    
    # Activity type choices
    TYPE_CALL = "call"
    TYPE_EMAIL = "email"
    TYPE_MEETING = "meeting"
    TYPE_NOTE = "note"
    
    deal = fields.ForeignKey(
        "Deal",
        on_delete="CASCADE",
        ai_description="The deal this activity is associated with",
    )
    type = fields.String(
        max_length=50,
        default="note",
        ai_description="Activity type: call, email, meeting, or note",
    )
    notes = fields.Text(
        nullable=True,
        ai_description="Free-text description of what happened — AI assistants use this to summarize deal history and recommend next steps",
    )
    occurred_at = fields.DateTime(
        auto_now_add=True,
        ai_description="When this activity took place",
    )
    
    class Meta:
        table_name = "activities"
        ai_name = "Activity"
        ai_description = "Interaction log entry (call, email, meeting) for a deal"
        ai_agent_exposed = True
