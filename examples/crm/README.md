# CRM Example

A simple CRM backend demonstrating real-world Aksara patterns.

## Features

- **Customer model** with:
  - Name, email (`ai_sensitive=True`), phone (`ai_sensitive=True`)
  - Industry and company size
  - Notes

- **Deal model** with:
  - Foreign key to Customer
  - Pipeline stages (lead, qualified, proposal, negotiation, closed_won, closed_lost)
  - Amount (`ai_agent_writable=False`) and probability for forecasting
  - Expected close date

- **Activity model** with:
  - Foreign key to Deal (three-level FK chain: Customer → Deal → Activity)
  - Type choices: call, email, meeting, note
  - Notes — rich `ai_description` for AI summarization

- **Custom endpoints**:
  - `GET /api/deals/{id}/forecast/` - Get expected revenue
  - `GET /api/deals/pipeline/` - Pipeline summary by stage
  - `POST /api/deals/{id}/advance_stage/` - Move deal forward
  - `POST /api/deals/{id}/close_won/` - Mark deal as won
  - `POST /api/deals/{id}/mark_lost/` - Mark deal as lost

## AI Metadata Patterns

| Attribute | Used On | Why |
|-----------|---------|-----|
| `ai_description` | Every field | Tells the AI Console and MCP tool catalog what each field means |
| `ai_sensitive=True` | `Customer.email`, `Customer.phone` | PII — excluded from AI context and MCP exports |
| `ai_agent_writable=False` | `Deal.amount`, `Deal.stage` | AI can read these but cannot modify them — use actions instead |

## Quick Start

```bash
cd examples/crm

# Set up database interactively
aksara dbsetup

# Run migrations
aksara makemigrations --app examples.crm.models
aksara migrate

# Start server
aksara dev
```

## Endpoints

| Endpoint | Description |
|----------|-------------|
| `/` | Welcome page |
| `/docs` | API documentation |
| `/admin/` | Admin panel |
| `/api/customers/` | Customers CRUD |
| `/api/deals/` | Deals CRUD |
| `/api/activities/` | Activities CRUD |
| `/api/deals/pipeline/` | Pipeline summary |
| `/api/deals/{id}/forecast/` | Deal forecast |

## Example: Forecast Calculation

```bash
# Get forecast for a deal
curl http://localhost:8000/api/deals/{id}/forecast/

# Response:
{
  "id": "...",
  "title": "Enterprise License",
  "amount": 50000.00,
  "probability": 60,
  "expected_revenue": 30000.00,
  "stage": "proposal",
  "close_date": "2026-03-15"
}
```

## Pipeline Stages

| Stage | Description | Default Probability |
|-------|-------------|---------------------|
| lead | Initial contact | 10% |
| qualified | Needs confirmed | 25% |
| proposal | Proposal sent | 50% |
| negotiation | In negotiation | 75% |
| closed_won | Deal won | 100% |
| closed_lost | Deal lost | 0% |
