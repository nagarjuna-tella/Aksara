# CRM Pattern

A sales CRM backend with customers, deals, pipeline stages, and revenue forecasting.

## Quick Start

```bash
aksara startproject mycrm --template crm
cd mycrm
pip install -e ".[dev]"
aksara makemigrations --app app.models
aksara migrate
aksara dev
```

## Models

### Customer

```python
class Customer(Model):
    """Customer/lead in the CRM."""
    
    name = fields.String(max_length=200, ai_description="Customer name")
    email = fields.Email(unique=True, ai_description="Primary contact email")
    phone = fields.String(max_length=50, nullable=True, ai_description="Phone number")
    company = fields.String(max_length=200, nullable=True, ai_description="Company name")
    status = fields.String(
        max_length=50,
        default="lead",
        ai_description="Customer status: lead, prospect, customer, churned",
    )
    notes = fields.Text(nullable=True, ai_description="Internal notes")
    created_at = fields.DateTime(auto_now_add=True)
    updated_at = fields.DateTime(auto_now=True)
    
    class Meta:
        table_name = "customers"
        ai_name = "Customer"
        ai_agent_exposed = True
```

### Deal

```python
class Deal(Model):
    """Sales deal/opportunity."""
    
    customer = fields.ForeignKey(
        Customer,
        on_delete="CASCADE",
        related_name="deals",
        ai_description="Associated customer",
    )
    title = fields.String(max_length=200, ai_description="Deal title")
    value = fields.Decimal(
        max_digits=12,
        decimal_places=2,
        ai_description="Deal value in dollars",
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
    expected_close_date = fields.Date(
        nullable=True,
        ai_description="Expected close date",
    )
    notes = fields.Text(nullable=True, ai_description="Deal notes")
    created_at = fields.DateTime(auto_now_add=True)
    updated_at = fields.DateTime(auto_now=True)
    
    class Meta:
        table_name = "deals"
        ai_name = "Deal"
        ai_agent_exposed = True
    
    @property
    def expected_revenue(self) -> float:
        """Calculate expected revenue: value * (probability / 100)."""
        return float(self.value) * (self.probability / 100)
```

## Authentication (v0.5.8)

The CRM example includes API key authentication for protected endpoints.

### Setup

```python
# settings.py
import os

CRM_API_KEY = os.getenv("CRM_API_KEY", "dev-crm-key")
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100
```

### Auth Module

```python
# auth.py
from fastapi import HTTPException, Header
from . import settings

def verify_api_key(api_key: str) -> bool:
    """Verify API key against configured key."""
    return api_key == settings.CRM_API_KEY

async def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    """FastAPI dependency for API key authentication."""
    if not verify_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key
```

### Usage

```python
from fastapi import Depends
from .auth import require_api_key

class CustomerViewSet(ModelViewSet):
    dependencies = [Depends(require_api_key)]
    # All endpoints now require X-API-Key header

class DealViewSet(ModelViewSet):
    dependencies = [Depends(require_api_key)]
```

### Example Request

```bash
curl http://localhost:8000/api/customers/ \
  -H "X-API-Key: dev-crm-key"
```

## Pagination & Ordering (v0.5.8)

List endpoints support pagination and ordering via query parameters.

### Query Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `page` | 1 | Page number (1-based) |
| `page_size` | 10 | Items per page (max 100) |
| `order_by` | `created_at` | Field to sort by |
| `status` | - | Filter customers by status |
| `stage` | - | Filter deals by pipeline stage |

### Ordering

- Ascending: `?order_by=name`
- Descending: `?order_by=-value` (for deals)
- Pipeline order: `?order_by=stage` (uses STAGE_ORDER)

### Example Requests

```bash
# List customers sorted by name
curl "http://localhost:8000/api/customers/?order_by=name" \
  -H "X-API-Key: dev-crm-key"

# List deals sorted by value (highest first)
curl "http://localhost:8000/api/deals/?order_by=-value" \
  -H "X-API-Key: dev-crm-key"

# Filter deals by stage
curl "http://localhost:8000/api/deals/?stage=proposal" \
  -H "X-API-Key: dev-crm-key"
```

### Response Format

```json
{
  "results": [...],
  "page": 1,
  "page_size": 10,
  "total": 25
}
```

## AI-Ready Endpoints (v0.5.8)

The CRM example includes an AI-aware endpoint for customer context summaries.

### AI Customer Context

```python
@action(
    detail=True,
    methods=["GET"],
    path="ai-context",
    name="summarize_customer_context",
    description="Get a comprehensive summary of a customer's record, deals, and pipeline health.",
    ai_exposed=True,
)
async def ai_context(self, pk: str, request: Request):
    """AI Tool: Summarize customer context."""
    customer = await self.model.objects.get(id=pk)
    deals = await Deal.objects.filter(customer_id=pk).all()
    
    total_value = sum(float(d.value) for d in deals)
    weighted_value = sum(
        float(d.value) * STAGE_PROBABILITIES.get(d.stage, 0) / 100
        for d in deals
    )
    pipeline = {}
    for d in deals:
        pipeline.setdefault(d.stage, {"count": 0, "value": 0})
        pipeline[d.stage]["count"] += 1
        pipeline[d.stage]["value"] += float(d.value)
    
    return {
        "customer_id": str(customer.id),
        "customer_name": customer.name,
        "customer_status": customer.status,
        "company": customer.company,
        "deal_summary": {
            "total_deals": len(deals),
            "total_value": total_value,
            "weighted_value": weighted_value,
            "pipeline_breakdown": pipeline,
        },
        "notes": customer.notes,
    }
```

### Example Request

```bash
curl http://localhost:8000/api/customers/1/ai-context/ \
  -H "X-API-Key: dev-crm-key"
```

### Response

```json
{
  "customer_id": "abc123",
  "customer_name": "Acme Corp",
  "customer_status": "customer",
  "company": "Acme Corporation",
  "deal_summary": {
    "total_deals": 3,
    "total_value": 75000.00,
    "weighted_value": 42500.00,
    "pipeline_breakdown": {
      "closed_won": {"count": 1, "value": 25000.00},
      "proposal": {"count": 2, "value": 50000.00}
    }
  },
  "notes": "Key enterprise account"
}
```

### AI Tools Discovery

This endpoint is discoverable at `/ai/tools` with `ai_exposed=True`:

```json
{
  "name": "summarize_customer_context",
  "description": "Get a comprehensive summary of a customer's record, deals, and pipeline health.",
  "endpoint": "/api/customers/{id}/ai-context/"
}
```

## Deal Pipeline Stages

| Stage | Probability | Description |
|-------|-------------|-------------|
| lead | 10% | Initial contact |
| qualified | 25% | Qualified lead |
| proposal | 50% | Proposal sent |
| negotiation | 75% | In negotiation |
| closed_won | 100% | Deal won |
| closed_lost | 0% | Deal lost |

## API Endpoints

### Customers

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/customers/` | List customers |
| POST | `/api/customers/` | Create a customer |
| GET | `/api/customers/{id}/` | Get customer details |
| PUT | `/api/customers/{id}/` | Update a customer |
| DELETE | `/api/customers/{id}/` | Delete a customer |

### Deals

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/deals/` | List deals |
| POST | `/api/deals/` | Create a deal |
| GET | `/api/deals/{id}/` | Get deal details |
| PUT | `/api/deals/{id}/` | Update a deal |
| DELETE | `/api/deals/{id}/` | Delete a deal |
| GET | `/api/deals/forecast/` | Revenue forecast |
| GET | `/api/deals/pipeline/` | Pipeline summary |
| POST | `/api/deals/{id}/advance_stage/` | Move deal to next stage |

## Custom Actions

### Revenue Forecast

```python
@action(detail=False, methods=["GET"])
async def forecast(self, request: Request):
    """
    Get revenue forecast based on deal probability.
    
    Returns total, weighted (expected), and closed revenue.
    """
    deals = await self.model.objects.all()
    
    total_value = sum(float(d.value) for d in deals)
    weighted_value = sum(d.expected_revenue for d in deals)
    closed_value = sum(
        float(d.value) for d in deals 
        if d.stage == "closed_won"
    )
    
    return {
        "total_pipeline": total_value,
        "weighted_forecast": weighted_value,
        "closed_revenue": closed_value,
        "deal_count": len(deals),
    }
```

### Pipeline Summary

```python
@action(detail=False, methods=["GET"])
async def pipeline(self, request: Request):
    """
    Get pipeline summary grouped by stage.
    
    Returns count and total value per stage.
    """
    deals = await self.model.objects.all()
    
    stages = {}
    for deal in deals:
        if deal.stage not in stages:
            stages[deal.stage] = {"count": 0, "value": 0}
        stages[deal.stage]["count"] += 1
        stages[deal.stage]["value"] += float(deal.value)
    
    return {"stages": stages}
```

### Advance Stage

```python
STAGE_ORDER = ["lead", "qualified", "proposal", "negotiation", "closed_won"]
STAGE_PROBABILITIES = {
    "lead": 10,
    "qualified": 25,
    "proposal": 50,
    "negotiation": 75,
    "closed_won": 100,
}

@action(detail=True, methods=["POST"])
async def advance_stage(self, pk: str, request: Request):
    """
    Advance a deal to the next pipeline stage.
    
    Also updates probability based on stage.
    """
    deal = await self.model.objects.get(id=pk)
    
    if deal.stage == "closed_won":
        return {"error": "Deal already closed won"}
    if deal.stage == "closed_lost":
        return {"error": "Cannot advance a lost deal"}
    
    try:
        current_idx = STAGE_ORDER.index(deal.stage)
        next_stage = STAGE_ORDER[current_idx + 1]
        deal.stage = next_stage
        deal.probability = STAGE_PROBABILITIES[next_stage]
        await deal.save()
        return {
            "status": "advanced",
            "stage": next_stage,
            "probability": deal.probability,
        }
    except (ValueError, IndexError):
        return {"error": f"Cannot advance from stage: {deal.stage}"}
```

## Example Requests

### Create a Customer

```bash
curl -X POST http://localhost:8000/api/customers/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corp",
    "email": "contact@acme.com",
    "company": "Acme Corporation",
    "status": "lead"
  }'
```

### Create a Deal

```bash
curl -X POST http://localhost:8000/api/deals/ \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": 1,
    "title": "Enterprise License",
    "value": 50000.00,
    "stage": "lead",
    "expected_close_date": "2025-03-01"
  }'
```

### Get Forecast

```bash
curl http://localhost:8000/api/deals/forecast/
```

Response:
```json
{
  "total_pipeline": 150000.00,
  "weighted_forecast": 45000.00,
  "closed_revenue": 25000.00,
  "deal_count": 5
}
```

### Advance Deal Stage

```bash
curl -X POST http://localhost:8000/api/deals/1/advance_stage/
```

Response:
```json
{
  "status": "advanced",
  "stage": "qualified",
  "probability": 25
}
```

## Serializers

### DealSerializer with Computed Field

```python
class DealSerializer(ModelSerializer):
    expected_revenue: Optional[float] = None
    
    class Meta:
        model = Deal
        fields = [
            "id", "customer_id", "title", "value", "stage",
            "probability", "expected_revenue", "expected_close_date",
            "notes", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "expected_revenue", "created_at", "updated_at"]
    
    @classmethod
    def from_model(cls, deal: Deal) -> "DealSerializer":
        instance = super().from_model(deal)
        instance.expected_revenue = deal.expected_revenue
        return instance
```

## Extending the Pattern

### Add Activities/Tasks

```python
class Activity(Model):
    """Sales activity/task."""
    
    deal = fields.ForeignKey(Deal, on_delete="CASCADE", related_name="activities")
    type = fields.String(max_length=50)  # call, email, meeting, demo
    subject = fields.String(max_length=200)
    description = fields.Text(nullable=True)
    due_date = fields.DateTime(nullable=True)
    completed = fields.Boolean(default=False)
    completed_at = fields.DateTime(nullable=True)
    
    class Meta:
        table_name = "activities"
```

### Add Products/Line Items

```python
class Product(Model):
    """Product catalog."""
    
    name = fields.String(max_length=200)
    sku = fields.String(max_length=50, unique=True)
    price = fields.Decimal(max_digits=10, decimal_places=2)
    
    class Meta:
        table_name = "products"

class DealLineItem(Model):
    """Line item on a deal."""
    
    deal = fields.ForeignKey(Deal, on_delete="CASCADE", related_name="line_items")
    product = fields.ForeignKey(Product, on_delete="PROTECT")
    quantity = fields.Integer(default=1)
    unit_price = fields.Decimal(max_digits=10, decimal_places=2)
    
    class Meta:
        table_name = "deal_line_items"
```

### Add Sales Rep Assignment

```python
class SalesRep(Model):
    """Sales representative."""
    
    name = fields.String(max_length=200)
    email = fields.Email(unique=True)
    team = fields.String(max_length=100, nullable=True)
    
    class Meta:
        table_name = "sales_reps"

class Deal(Model):
    # ... existing fields ...
    sales_rep = fields.ForeignKey(SalesRep, nullable=True, on_delete="SET_NULL")
```

## Next Steps

- [Blog Pattern](blog.md) - Content management
- [Multitenant Pattern](multitenant.md) - SaaS backend
- [Custom Actions](../api/viewsets.md) - ViewSet actions
