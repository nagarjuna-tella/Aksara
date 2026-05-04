"""Tests for TypeScript SDK generation from ModelViewSets."""

from __future__ import annotations

from aksara import Model, fields
from aksara.api import ModelViewSet
from aksara.sdk.typescript import generate_typescript_sdk


class User(Model):
    email = fields.String(max_length=255)
    is_active = fields.Boolean(default=True)

    class Meta:
        table_name = "users"


class UserViewSet(ModelViewSet):
    model = User
    prefix = "/users"
    search_fields = ["email"]
    ordering_fields = ["email"]


class TestTypeScriptSdkGeneration:
    """Tests for CRUD TypeScript SDK rendering."""

    def test_generates_interfaces_and_client_methods(self):
        content = generate_typescript_sdk([UserViewSet])

        assert "export interface UserCreate" in content
        assert "export interface UserUpdate" in content
        assert "export interface UserRead" in content
        assert "export interface UserListParams" in content
        assert "async listUsers" in content
        assert "async getUser" in content
        assert "async createUser" in content
        assert "async updateUser" in content
        assert "async deleteUser" in content

    def test_includes_query_helpers_and_pagination_types(self):
        content = generate_typescript_sdk([UserViewSet])

        assert "export type QueryValue" in content
        assert "export interface PaginatedResponse<T>" in content
        assert "search?: string;" in content
        assert "ordering?: string;" in content
        assert "email?: QueryValue;" in content