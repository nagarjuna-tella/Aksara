"""
CRM Example - URL Configuration
"""

from aksara import include_viewset
from .views import CustomerViewSet, DealViewSet


urlpatterns = [
    CustomerViewSet,
    DealViewSet,
]


def register_routes(app):
    """Register all routes with the Aksara app."""
    for viewset in urlpatterns:
        include_viewset(app, viewset)
