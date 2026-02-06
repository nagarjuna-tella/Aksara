"""
CRM Example - Views

ViewSets for Customer and Deal with forecast endpoint.
Demonstrates:
- ModelViewSet for CRUD
- Custom forecast action
- Stage and probability filtering
"""

from aksara import ModelViewSet, action, Request
from .models import Customer, Deal
from .serializers import CustomerSerializer, DealSerializer


class CustomerViewSet(ModelViewSet):
    """
    ViewSet for customers.
    
    Endpoints:
        GET    /api/customers/           - List all customers
        POST   /api/customers/           - Create a customer
        GET    /api/customers/{id}/      - Get a customer
        PUT    /api/customers/{id}/      - Update a customer
        DELETE /api/customers/{id}/      - Delete a customer
    
    Query Parameters:
        ?industry=Technology    - Filter by industry
        ?company_size=Enterprise - Filter by company size
    """
    
    model = Customer
    serializer_class = CustomerSerializer
    prefix = "/api/customers"
    tags = ["Customers"]
    ai_exposed = True


class DealViewSet(ModelViewSet):
    """
    ViewSet for deals.
    
    Endpoints:
        GET    /api/deals/                - List all deals
        POST   /api/deals/                - Create a deal
        GET    /api/deals/{id}/           - Get a deal
        PUT    /api/deals/{id}/           - Update a deal
        DELETE /api/deals/{id}/           - Delete a deal
        GET    /api/deals/{id}/forecast/  - Get deal forecast
        GET    /api/deals/pipeline/       - Pipeline summary
    
    Query Parameters:
        ?stage=qualified         - Filter by stage
        ?probability__gte=50     - Filter by min probability
        ?probability__lte=80     - Filter by max probability
    """
    
    model = Deal
    serializer_class = DealSerializer
    prefix = "/api/deals"
    tags = ["Deals"]
    ai_exposed = True
    
    @action(detail=True, methods=["GET"])
    async def forecast(self, pk: str, request: Request):
        """
        Get forecast for a specific deal.
        
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
        """
        stage_order = ["lead", "qualified", "proposal", "negotiation", "closed_won"]
        
        deal = await self.model.objects.get(id=pk)
        current_idx = stage_order.index(deal.stage) if deal.stage in stage_order else 0
        
        if current_idx < len(stage_order) - 1:
            deal.stage = stage_order[current_idx + 1]
            # Increase probability as deal advances
            deal.probability = min(100, deal.probability + 20)
            await deal.save()
            
            return {
                "id": str(deal.id),
                "new_stage": deal.stage,
                "probability": deal.probability,
            }
        
        return {"error": "Deal is already at final stage"}
    
    @action(detail=True, methods=["POST"])
    async def mark_lost(self, pk: str, request: Request):
        """Mark a deal as lost."""
        deal = await self.model.objects.get(id=pk)
        deal.stage = "closed_lost"
        deal.probability = 0
        await deal.save()
        
        return {"id": str(deal.id), "stage": deal.stage}
