"""
CRM Example - Models

Demonstrates:
- Customer model with contact info
- Deal model with pipeline stages and probability
- FK relationship between Deal and Customer
"""

from aksara import Model, fields


class Customer(Model):
    """
    Customer record for CRM.
    
    Stores contact information and notes about the customer.
    """
    
    name = fields.String(
        max_length=200,
        ai_description="Customer or company name",
    )
    email = fields.String(
        max_length=255,
        nullable=True,
        ai_description="Primary contact email",
    )
    phone = fields.String(
        max_length=50,
        nullable=True,
        ai_description="Phone number",
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
        ai_description="Internal notes about the customer",
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
        precision=12,
        scale=2,
        ai_description="Deal value in currency",
    )
    stage = fields.String(
        max_length=50,
        default="lead",
        ai_description="Pipeline stage: lead, qualified, proposal, negotiation, closed_won, closed_lost",
    )
    probability = fields.Integer(
        default=10,
        ai_description="Win probability percentage (0-100)",
    )
    close_date = fields.Date(
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
