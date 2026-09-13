"""Tests for TypeScript SDK generation from ModelViewSets."""

from __future__ import annotations

from pydantic import BaseModel

from aksara import Model, fields
from aksara.api import CursorPagination, ModelViewSet, PageNumberPagination
from aksara.sdk.typescript import ViewSetSdkSpec, generate_typescript_sdk


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


class PageUserViewSet(UserViewSet):
    prefix = "/page-users"
    pagination_class = PageNumberPagination


class CursorUserViewSet(UserViewSet):
    prefix = "/cursor-users"
    pagination_class = CursorPagination


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

    def test_uses_paginator_specific_query_and_response_types(self):
        page_content = generate_typescript_sdk([PageUserViewSet])
        cursor_content = generate_typescript_sdk([CursorUserViewSet])

        assert "page?: number;" in page_content
        assert "size?: number;" in page_content
        assert "limit?: number;" not in page_content.split(
            "export interface UserListParams", 1
        )[1].split("}", 1)[0]
        assert "Promise<PageNumberPaginatedResponse<UserRead>>" in page_content

        assert "cursor?: string;" in cursor_content
        assert "page_size?: number;" in cursor_content
        assert "next_cursor: string | null;" in cursor_content
        assert "Promise<CursorPaginatedResponse<UserRead>>" in cursor_content

    def test_list_params_remain_specific_but_are_accepted_by_query_helper(self):
        content = generate_typescript_sdk([UserViewSet])

        assert "function buildQueryString(params: object = {})" in content
        assert "params?: object" in content
        params = content.split("export interface UserListParams", 1)[1].split(
            "}", 1
        )[0]
        assert "[key: string]" not in params

    def test_preserves_nullable_and_optional_schema_fields(self):
        class NullableCreate(BaseModel):
            title: str
            note: str | None = None

        class NullableUpdate(BaseModel):
            title: str | None = None

        class NullableRead(BaseModel):
            id: str
            note: str | None

        content = generate_typescript_sdk(
            [
                ViewSetSdkSpec(
                    model_name="Nullable",
                    prefix="/nullable",
                    create_schema=NullableCreate,
                    update_schema=NullableUpdate,
                    read_schema=NullableRead,
                    filter_fields=[],
                    search_enabled=False,
                    ordering_enabled=False,
                )
            ]
        )

        assert "note?: string | null;" in content
        assert "title?: string | null;" in content
        assert "note: string | null;" in content
