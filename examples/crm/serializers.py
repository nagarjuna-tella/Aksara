"""
CRM Example - Serializers

Pydantic-based serializers for data validation.
"""

from aksara.api import ModelSerializer
from .models import Customer, Deal, Activity


class CustomerSerializer(ModelSerializer):
    """Serializer for Customer model."""
    
    class Meta:
        model = Customer
        fields = [
            "id", "name", "email", "phone", "industry",
            "company_size", "notes", "created_at"
        ]
        read_only_fields = ["id", "created_at"]


class DealSerializer(ModelSerializer):
    """Serializer for Deal model."""
    
    class Meta:
        model = Deal
        fields = [
            "id", "customer_id", "title", "amount", "stage",
            "probability", "close_date", "notes", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class DealForecastSerializer(ModelSerializer):
    """Serializer for deal forecast view."""
    
    class Meta:
        model = Deal
        fields = [
            "id", "title", "amount", "stage", "probability", "close_date"
        ]


class ActivitySerializer(ModelSerializer):
    """Serializer for Activity model."""
    
    class Meta:
        model = Activity
        fields = [
            "id", "deal_id", "type", "notes", "occurred_at"
        ]
        read_only_fields = ["id", "occurred_at"]
