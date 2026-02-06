# CRM Example

A simple CRM backend demonstrating real-world Aksara patterns.

## Features

- **Customer model** with:
  - Name, email, phone
  - Industry and company size
  - Notes

- **Deal model** with:
  - Foreign key to Customer
  - Pipeline stages (lead, qualified, proposal, negotiation, closed_won, closed_lost)
  - Amount and probability for forecasting
  - Expected close date

- **Custom endpoints**:
  - `GET /api/deals/{id}/forecast/` - Get expected revenue
  - `GET /api/deals/pipeline/` - Pipeline summary by stage
  - `POST /api/deals/{id}/advance_stage/` - Move deal forward
  - `POST /api/deals/{id}/mark_lost/` - Mark deal as lost

## Quick Start

```bash
cd examples/crm
export DATABASE_URL=postgresql://postgres:password@localhost:5432/aksara_crm
createdb aksara_crm
aksara makemigrations --app examples.crm.models
aksara migrate
uvicorn examples.crm.main:app --reload
```

## Endpoints

| Endpoint | Description |
|----------|-------------|
| `/` | Welcome page |
| `/docs` | API documentation |
| `/admin/` | Admin panel |
| `/api/customers/` | Customers CRUD |
| `/api/deals/` | Deals CRUD |
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
| qualified | Needs confirmed | 30% |
| proposal | Proposal sent | 50% |
| negotiation | In negotiation | 70% |
| closed_won | Deal won | 100% |
| closed_lost | Deal lost | 0% |
