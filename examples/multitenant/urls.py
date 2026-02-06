"""
Multitenant Example - URL Configuration
"""

from aksara import include_viewset
from .views import TenantViewSet, UserViewSet, ProjectViewSet


urlpatterns = [
    TenantViewSet,
    UserViewSet,
    ProjectViewSet,
]


def register_routes(app):
    """Register all routes with the Aksara app."""
    for viewset in urlpatterns:
        include_viewset(app, viewset)
