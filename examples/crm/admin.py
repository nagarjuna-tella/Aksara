"""
CRM Example - Admin Registration
"""

from aksara.contrib.admin import ModelAdmin, admin_site
from .models import Customer, Deal


@admin_site.register(Customer)
class CustomerAdmin(ModelAdmin):
    """Admin configuration for Customer model."""
    
    list_display = ["name", "email", "industry", "company_size", "created_at"]
    list_filter = ["industry", "company_size"]
    search_fields = ["name", "email"]


@admin_site.register(Deal)
class DealAdmin(ModelAdmin):
    """Admin configuration for Deal model."""
    
    list_display = ["title", "amount", "stage", "probability", "close_date"]
    list_filter = ["stage"]
    search_fields = ["title"]
