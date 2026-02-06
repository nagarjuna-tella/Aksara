"""
Blog Example - URL Configuration

Register ViewSets with the application.
"""

from aksara import include_viewset
from .views import PostViewSet, CommentViewSet


# URL Patterns - list your ViewSets here
urlpatterns = [
    PostViewSet,
    CommentViewSet,
]


def register_routes(app):
    """Register all routes with the Aksara app."""
    for viewset in urlpatterns:
        include_viewset(app, viewset)
