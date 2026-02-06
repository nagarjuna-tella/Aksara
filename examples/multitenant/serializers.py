"""
Multitenant Example - Serializers
"""

from aksara.api import ModelSerializer
from .models import Tenant, User, Project


class TenantSerializer(ModelSerializer):
    """Serializer for Tenant model."""
    
    class Meta:
        model = Tenant
        fields = [
            "id", "name", "slug", "domain", "plan",
            "is_active", "metadata", "created_at"
        ]
        read_only_fields = ["id", "created_at"]


class UserSerializer(ModelSerializer):
    """Serializer for User model."""
    
    class Meta:
        model = User
        fields = [
            "id", "tenant_id", "email", "name", "role",
            "is_active", "last_login", "created_at"
        ]
        read_only_fields = ["id", "created_at"]


class ProjectSerializer(ModelSerializer):
    """Serializer for Project model."""
    
    class Meta:
        model = Project
        fields = [
            "id", "tenant_id", "name", "description",
            "is_public", "created_at"
        ]
        read_only_fields = ["id", "created_at"]
