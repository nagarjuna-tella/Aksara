"""
CRM Example - Views (v0.5.8)

ViewSets for Customer and Deal with forecast endpoint.
Demonstrates:
- ModelViewSet for CRUD
- API key authentication
- Pagination and ordering
- AI-aware endpoints
- Pipeline stage management
"""

from typing import Optional
from aksara import ModelViewSet, action, Request
from fastapi import Depends, Query
from .models import Customer, Deal, Activity
from .serializers import CustomerSerializer, DealSerializer, ActivitySerializer
from .auth import require_api_key
from .settings import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

# Stage order for pipeline progression
STAGE_ORDER = ["lead", "qualified", "proposal", "negotiation", "closed_won"]
STAGE_PROBABILITIES = {
    "lead": 10,
    "qualified": 25,
    "proposal": 50,
    "negotiation": 75,
    "closed_won": 100,
    "closed_lost": 0,
}


class CustomerViewSet(ModelViewSet):
    """
    ViewSet for customers.
    
    Authentication:
        All endpoints require X-API-Key header.
    
    Endpoints:
        GET    /api/customers/                    - List customers (paginated)
        POST   /api/customers/                    - Create a customer
        GET    /api/customers/{id}/               - Get a customer
        PUT    /api/customers/{id}/               - Update a customer
        DELETE /api/customers/{id}/               - Delete a customer
        GET    /api/customers/{id}/ai-context/    - AI: summarize customer
    
    Query Parameters:
        ?page=1              - Page number
        ?page_size=10        - Items per page (max: 100)
        ?order_by=name       - Ordering (default: name)
        ?industry=Technology - Filter by industry
        ?company_size=Enterprise - Filter by company size
    """
    
    model = Customer
    serializer_class = CustomerSerializer
    prefix = "/api/customers"
    tags = ["CRM API"]
    ai_exposed = True
    
    # Apply auth to all endpoints in this ViewSet
    dependencies = [Depends(require_api_key)]
    
    async def list(
        self,
        request: Request,
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
        order_by: str = Query("name", description="Order by field"),
        industry: Optional[str] = Query(None, description="Filter by industry"),
        company_size: Optional[str] = Query(None, description="Filter by company size"),
    ):
        """List customers with pagination and filtering."""
        queryset = self.model.objects
        
        # Apply filters
        filters = {}
        if industry:
            filters["industry"] = industry
        if company_size:
            filters["company_size"] = company_size
        
        if filters:
            queryset = queryset.filter(**filters)
        
        all_customers = await queryset.all()
        total = len(all_customers)
        
        # Apply ordering
        if order_by.startswith("-"):
            field = order_by[1:]
            customers = sorted(all_customers, key=lambda c: getattr(c, field, "") or "", reverse=True)
        else:
            customers = sorted(all_customers, key=lambda c: getattr(c, order_by, "") or "")
        
        # Apply pagination
        offset = (page - 1) * page_size
        paginated = customers[offset:offset + page_size]
        
        return {
            "results": [CustomerSerializer.from_model(c).model_dump() for c in paginated],
            "page": page,
            "page_size": page_size,
            "total": total,
        }
    
    # =========================================================================
    # AI-Aware Endpoint (v0.5.8)
    # =========================================================================
    
    @action(
        detail=True,
        methods=["GET"],
        path="ai-context",
        name="summarize_customer_context",
        description="Aggregate customer data, deals, and activity into a structured context object for LLM summarization.",
        ai_exposed=True,
    )
    async def ai_context(self, pk: str, request: Request):
        """
        AI Tool: Summarize customer context.
        
        Aggregates customer information and their deals into a structured
        format that an LLM can use to generate summaries or recommendations.
        
        Returns:
            customer_id: Customer UUID
            name: Customer name
            contact: Contact information
            industry: Customer's industry
            deals: Summary of associated deals
            notes_snapshot: Recent notes (if any)
        """
        customer = await self.model.objects.get(id=pk)
        
        # Get all deals for this customer
        deals = await Deal.objects.filter(customer_id=pk).all()
        
        # Aggregate deals by stage
        deals_by_stage = {}
        total_amount = 0
        total_expected = 0
        for deal in deals:
            stage = deal.stage
            if stage not in deals_by_stage:
                deals_by_stage[stage] = {"count": 0, "amount": 0}
            deals_by_stage[stage]["count"] += 1
            deals_by_stage[stage]["amount"] += float(deal.amount)
            total_amount += float(deal.amount)
            total_expected += float(deal.amount) * (deal.probability / 100)
        
        # Find most recent deal update
        last_activity = None
        if deals:
            sorted_deals = sorted(deals, key=lambda d: d.updated_at or d.created_at, reverse=True)
            last_deal = sorted_deals[0]
            last_activity = (last_deal.updated_at or last_deal.created_at).isoformat()
        
        return {
            "customer_id": str(customer.id),
            "name": customer.name,
            "contact": {
                "email": customer.email,
                "phone": customer.phone,
            },
            "industry": customer.industry,
            "company_size": customer.company_size,
            "deals": {
                "count": len(deals),
                "by_stage": deals_by_stage,
                "total_amount": total_amount,
                "total_expected_revenue": total_expected,
            },
            "last_activity": last_activity,
            "notes_snapshot": (customer.notes or "")[:500] if customer.notes else None,
        }


class DealViewSet(ModelViewSet):
    """
    ViewSet for deals.
    
    Authentication:
        All endpoints require X-API-Key header.
    
    Endpoints:
        GET    /api/deals/                - List deals (paginated)
        POST   /api/deals/                - Create a deal
        GET    /api/deals/{id}/           - Get a deal
        PUT    /api/deals/{id}/           - Update a deal
        DELETE /api/deals/{id}/           - Delete a deal
        GET    /api/deals/{id}/forecast/  - Get deal forecast
        GET    /api/deals/pipeline/       - Pipeline summary
        POST   /api/deals/{id}/advance_stage/ - Advance to next stage
        POST   /api/deals/{id}/mark_lost/ - Mark deal as lost
    
    Query Parameters:
        ?page=1              - Page number
        ?page_size=10        - Items per page (max: 100)
        ?order_by=-amount    - Ordering (e.g., amount, -close_date)
        ?stage=qualified     - Filter by stage
    """
    
    model = Deal
    serializer_class = DealSerializer
    prefix = "/api/deals"
    tags = ["CRM API"]
    ai_exposed = True
    
    # Apply auth to all endpoints in this ViewSet
    dependencies = [Depends(require_api_key)]
    
    async def list(
        self,
        request: Request,
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
        order_by: str = Query("-amount", description="Order by field (prefix with - for descending)"),
        stage: Optional[str] = Query(None, description="Filter by stage"),
    ):
        """
        List deals with pagination, filtering, and ordering.
        
        Supports sorting by multiple criteria like amount or close_date.
        """
        queryset = self.model.objects
        
        if stage:
            queryset = queryset.filter(stage=stage)
        
        all_deals = await queryset.all()
        total = len(all_deals)
        
        # Apply ordering
        if order_by.startswith("-"):
            field = order_by[1:]
            deals = sorted(
                all_deals,
                key=lambda d: getattr(d, field, None) or 0,
                reverse=True
            )
        else:
            deals = sorted(
                all_deals,
                key=lambda d: getattr(d, order_by, None) or 0
            )
        
        # Apply pagination
        offset = (page - 1) * page_size
        paginated = deals[offset:offset + page_size]
        
        return {
            "results": [DealSerializer.from_model(d).model_dump() for d in paginated],
            "page": page,
            "page_size": page_size,
            "total": total,
        }
    
    @action(detail=True, methods=["GET"], ai_exposed=True)
    async def forecast(self, pk: str, request: Request):
        """
        Get forecast for a specific deal.
        This description becomes the MCP tool description for AI agents.
        
        Returns:
            - Deal details
            - Expected revenue (amount * probability / 100)
        """
        deal = await self.model.objects.get(id=pk)
        expected_revenue = float(deal.amount) * (deal.probability / 100)
        
        return {
            "id": str(deal.id),
            "title": deal.title,
            "amount": float(deal.amount),
            "probability": deal.probability,
            "expected_revenue": expected_revenue,
            "stage": deal.stage,
            "close_date": deal.close_date.isoformat() if deal.close_date else None,
        }
    
    @action(detail=False, methods=["GET"])
    async def pipeline(self, request: Request):
        """
        Get pipeline summary with totals by stage.
        
        Returns summary of deals grouped by stage:
        - Count per stage
        - Total amount per stage
        - Total expected revenue per stage
        """
        deals = await self.model.objects.all()
        
        stages = {}
        for deal in deals:
            stage = deal.stage
            if stage not in stages:
                stages[stage] = {
                    "count": 0,
                    "total_amount": 0,
                    "expected_revenue": 0,
                }
            stages[stage]["count"] += 1
            stages[stage]["total_amount"] += float(deal.amount)
            stages[stage]["expected_revenue"] += float(deal.amount) * (deal.probability / 100)
        
        return {
            "stages": stages,
            "total_deals": len(deals),
            "total_pipeline_value": sum(float(d.amount) for d in deals),
            "total_expected_revenue": sum(
                float(d.amount) * (d.probability / 100) for d in deals
            ),
        }
    
    @action(detail=True, methods=["POST"])
    async def advance_stage(self, pk: str, request: Request):
        """
        Advance deal to next stage.
        
        Stage progression:
        lead → qualified → proposal → negotiation → closed_won
        
        Probability is automatically adjusted based on the new stage.
        """
        deal = await self.model.objects.get(id=pk)
        
        if deal.stage == "closed_won":
            return {"error": "Deal is already closed won"}
        if deal.stage == "closed_lost":
            return {"error": "Cannot advance a lost deal"}
        
        current_idx = STAGE_ORDER.index(deal.stage) if deal.stage in STAGE_ORDER else 0
        
        if current_idx < len(STAGE_ORDER) - 1:
            deal.stage = STAGE_ORDER[current_idx + 1]
            deal.probability = STAGE_PROBABILITIES.get(deal.stage, deal.probability)
            await deal.save()
            
            return {
                "id": str(deal.id),
                "new_stage": deal.stage,
                "probability": deal.probability,
            }
        
        return {"error": "Deal is already at final stage"}
    
    @action(detail=True, methods=["POST"], ai_exposed=False)
    async def close_won(self, pk: str, request: Request):
        """Mark a deal as won. (Hidden from AI/MCP via ai_exposed=False)"""
        deal = await self.model.objects.get(id=pk)
        deal.stage = "closed_won"
        deal.probability = 100
        await deal.save()
        return {"id": str(deal.id), "stage": deal.stage, "probability": 100}

    @action(detail=True, methods=["POST"])
    async def mark_lost(self, pk: str, request: Request):
        """Mark a deal as lost."""
        deal = await self.model.objects.get(id=pk)
        deal.stage = "closed_lost"
        deal.probability = 0
        await deal.save()
        
        return {"id": str(deal.id), "stage": deal.stage}


class ActivityViewSet(ModelViewSet):
    """
    ViewSet for deal activities.
    
    Endpoints:
        GET    /api/activities/           - List activities
        POST   /api/activities/           - Log an activity
        GET    /api/activities/{id}/      - Get an activity
        DELETE /api/activities/{id}/      - Delete an activity
    
    Query Parameters:
        ?deal_id=<uuid>   - Filter by deal
        ?type=call        - Filter by activity type
    """
    
    model = Activity
    serializer_class = ActivitySerializer
    prefix = "/api/activities"
    tags = ["CRM API"]
    ai_exposed = True
    
    # Apply auth to all endpoints in this ViewSet
    dependencies = [Depends(require_api_key)]
