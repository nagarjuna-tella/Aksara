"""
Tests for the v0.5.51 admin feature build:

- AdminSite configuration, multi-model register, index_view, permission_classes
- ModelAdmin list_display_links, custom columns, fields/exclude/fieldsets,
  ordering, has_module_permission, actions resolution
- SimpleListFilter / FieldListFilter
- Flash messages
- Multi-site router namespacing
- DB-backed: search, ordering + pagination, field filtering, bulk actions
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aksara import Model, fields
from aksara.contrib.admin import AdminSite, ModelAdmin, SimpleListFilter, action
from aksara.contrib.admin.actions import (
    delete_selected,
    pop_messages,
    queue_message,
    write_messages_cookie,
)
from aksara.contrib.admin.filters import FieldListFilter
from aksara.contrib.admin.urls import build_admin_router
from aksara.permissions import IsAdminUser
from aksara.registry import ModelRegistry


def make_request(query=None, user=None, cookies=None):
    """Minimal request stand-in for unit tests."""
    return SimpleNamespace(
        query_params=query or {},
        state=SimpleNamespace(user=user),
        cookies=cookies or {},
    )


def staff_user():
    return SimpleNamespace(is_staff=True, is_superuser=False, is_authenticated=True, id="u1")


# ---------------------------------------------------------------------------
# AdminSite configuration
# ---------------------------------------------------------------------------

class TestAdminSiteConfig:
    def test_config_defaults(self):
        site = AdminSite()
        assert site.title == "Aksara Admin"
        assert site.theme == "default"
        assert site.permission_classes == []

    def test_config_custom(self):
        site = AdminSite(
            name="ops",
            title="Ops",
            site_header="Ops Console",
            index_title="Home",
            theme="dark",
            extra_css=["/x.css"],
        )
        ctx = site.base_context(make_request())
        assert ctx["site_header"] == "Ops Console"
        assert ctx["admin_theme"] == "dark"
        assert ctx["extra_css"] == ["/x.css"]

    def test_index_view_decorator(self):
        site = AdminSite(name="cfg1")

        @site.index_view
        async def dashboard(request):
            return {"x": 1}

        assert site._index_view_func is dashboard

    def test_check_site_permission_default_staff(self):
        site = AdminSite(name="cfg2")
        allowed, _ = site.check_site_permission(make_request(user=staff_user()))
        assert allowed is True
        denied, _ = site.check_site_permission(make_request(user=None))
        assert denied is False

    def test_check_site_permission_with_permission_classes(self):
        site = AdminSite(name="cfg3", permission_classes=[IsAdminUser])
        allowed, _ = site.check_site_permission(make_request(user=staff_user()))
        assert allowed is True
        anon = SimpleNamespace(is_staff=False, is_superuser=False, is_authenticated=False)
        denied, msg = site.check_site_permission(make_request(user=anon))
        assert denied is False


class TestMultiModelRegister:
    def setup_method(self):
        ModelRegistry.clear()

    def test_register_multiple_models_with_one_admin(self):
        site = AdminSite(name="multi")

        class Alpha(Model):
            name = fields.String()
            class Meta:
                app_label = "m"

        class Beta(Model):
            name = fields.String()
            class Meta:
                app_label = "m"

        @site.register(Alpha, Beta)
        class SharedAdmin(ModelAdmin):
            list_display = ["name"]

        assert site.is_registered(Alpha)
        assert site.is_registered(Beta)
        assert isinstance(site.get_model_admin(Alpha), SharedAdmin)
        assert isinstance(site.get_model_admin(Beta), SharedAdmin)

    def test_register_requires_a_model(self):
        site = AdminSite(name="empty")
        with pytest.raises(ValueError):
            site.register()


# ---------------------------------------------------------------------------
# ModelAdmin options
# ---------------------------------------------------------------------------

class _Doc(Model):
    title = fields.String()
    slug = fields.String()
    body = fields.Text()
    status = fields.String(choices=["draft", "published"])
    pinned = fields.Boolean(default=False)

    class Meta:
        app_label = "docs"


def doc_admin(**attrs):
    site = AdminSite(name="t")
    cls = type("DocAdmin", (ModelAdmin,), attrs)
    return cls(_Doc, site)


class TestModelAdminOptions:
    def test_list_display_links_default_first(self):
        ma = doc_admin(list_display=["title", "status"])
        assert ma.get_list_display_links(make_request(), ["title", "status"]) == ["title"]

    def test_list_display_links_explicit(self):
        ma = doc_admin(list_display=["title", "status"], list_display_links=["status"])
        assert ma.get_list_display_links(make_request(), ["title", "status"]) == ["status"]

    def test_custom_column_detection_and_label(self):
        def word_count(self, obj):
            return len((obj.body or "").split())
        word_count.short_description = "Words"
        word_count.allow_html = False

        ma = doc_admin(list_display=["title", "word_count"], word_count=word_count)
        assert ma.is_callable_column("word_count") is True
        assert ma.is_callable_column("title") is False
        assert ma.get_column_label("word_count") == "Words"
        assert ma.get_column_label("title") == "Title"
        assert ma.column_allows_html("word_count") is False

    def test_custom_column_allow_html(self):
        def badge(self, obj):
            return "<b>x</b>"
        badge.allow_html = True
        ma = doc_admin(list_display=["badge"], badge=badge)
        assert ma.column_allows_html("badge") is True

    def test_fields_explicit(self):
        ma = doc_admin(fields=["title", "slug"])
        assert ma.get_fields(make_request()) == ["title", "slug"]

    def test_exclude(self):
        ma = doc_admin(exclude=["body"])
        result = ma.get_fields(make_request())
        assert "body" not in result
        assert "title" in result

    def test_default_form_excludes_pk_timestamps_readonly(self):
        ma = doc_admin(readonly_fields=["status"])
        result = ma.get_fields(make_request())
        assert "id" not in result
        assert "created_at" not in result
        assert "status" not in result
        assert "title" in result

    def test_fieldsets_explicit_and_form_fields_flatten(self):
        ma = doc_admin(
            fieldsets=[
                (None, {"fields": ["title", "slug"]}),
                ("Meta", {"fields": ["status"], "classes": ["collapse"]}),
            ]
        )
        sets = ma.get_fieldsets(make_request())
        assert sets[0][0] is None
        assert sets[1][0] == "Meta"
        assert ma.get_form_fields(make_request()) == ["title", "slug", "status"]

    def test_fieldsets_default_single_section(self):
        ma = doc_admin(fields=["title"])
        sets = ma.get_fieldsets(make_request())
        assert len(sets) == 1
        assert sets[0][0] is None
        assert sets[0][1]["fields"] == ["title"]

    def test_get_ordering(self):
        ma = doc_admin(ordering=["-title"])
        assert ma.get_ordering(make_request()) == ["-title"]

    def test_has_module_permission_default(self):
        ma = doc_admin()
        assert ma.has_module_permission(make_request(user=staff_user())) is True
        assert ma.has_module_permission(make_request(user=None)) is False


class TestActionsResolution:
    def test_action_decorator_sets_attrs(self):
        @action(description="Publish", permissions=["change"])
        async def publish(self, request, queryset):
            pass
        assert publish._is_admin_action is True
        assert publish.action_description == "Publish"
        assert publish.allowed_permissions == ["change"]

    def test_get_actions_resolves_names_and_builtin(self):
        @action(description="Archive")
        async def archive(self, request, queryset):
            pass
        ma = doc_admin(actions=["delete_selected", "archive"], archive=archive)
        actions = ma.get_actions(make_request())
        assert "delete_selected" in actions
        assert "archive" in actions
        assert actions["delete_selected"]["allowed_permissions"] == ["delete"]
        assert actions["archive"]["description"] == "Archive"

    def test_get_actions_skips_unknown(self):
        ma = doc_admin(actions=["nonexistent"])
        assert ma.get_actions(make_request()) == {}


class TestBulkActionPermissions:
    async def test_actions_reject_objects_failing_object_permission(self):
        from fastapi import HTTPException
        from aksara.conf import configure, settings
        from aksara.contrib.admin.views import _run_list_action

        class FakeForm(dict):
            def getlist(self, key):
                return self.get(key, [])

        denied = SimpleNamespace(id="denied", qty=9)
        allowed = SimpleNamespace(id="allowed", qty=1)

        class FakeQuerySet:
            def __init__(self, objects):
                self.objects = objects

            def filter(self, **kwargs):
                return self

            async def all(self):
                return self.objects

        class GuardedAdmin(ModelAdmin):
            actions = ["delete_selected"]

            async def get_queryset(self, request):
                return FakeQuerySet([denied, allowed])

            def has_delete_permission(self, request, obj=None):
                if obj is None:
                    return True
                return obj.qty < 5

            async def delete_model(self, request, obj):
                raise AssertionError("delete_model should not be called")

        class FakeModel:
            __name__ = "FakeModel"

        form = FakeForm({"action": "delete_selected", "_selected": ["denied", "allowed"]})

        def url_for(name, **kwargs):
            return "/admin/app/fakemodel/"

        request = SimpleNamespace(
            form=AsyncMock(return_value=form),
            headers={},
            cookies={},
            state=SimpleNamespace(user=staff_user()),
            url=SimpleNamespace(path="/admin/app/fakemodel/", query=""),
            url_for=url_for,
        )

        original_csrf = settings.admin_csrf_enabled
        configure(admin_csrf_enabled=False)
        try:
            with pytest.raises(HTTPException) as exc_info:
                await _run_list_action(
                    request,
                    FakeModel,
                    GuardedAdmin(FakeModel, AdminSite(name="admin")),
                    AdminSite(name="admin"),
                    "app",
                    "fakemodel",
                )
        finally:
            configure(admin_csrf_enabled=original_csrf)

        assert exc_info.value.status_code == 403


class TestFlashMessages:
    def test_queue_and_pop_roundtrip(self):
        req = make_request()
        queue_message(req, "Saved!", level="success")
        queue_message(req, "Heads up", level="warning")

        captured = {}

        class FakeResp:
            def set_cookie(self, key, value, **kw):
                captured["key"] = key
                captured["value"] = value

        write_messages_cookie(req, FakeResp())
        read = make_request(cookies={"aksara_admin_messages": captured["value"]})
        msgs = pop_messages(read)
        assert [m["text"] for m in msgs] == ["Saved!", "Heads up"]
        assert msgs[0]["alert_class"] == "alert-success"
        assert msgs[1]["alert_class"] == "alert-warning"

    def test_pop_messages_empty(self):
        assert pop_messages(make_request()) == []


class TestSimpleListFilter:
    def test_lookups_and_value(self):
        class StatusFilter(SimpleListFilter):
            title = "Status"
            parameter_name = "st"

            def lookups(self, request, model_admin):
                return [("a", "A"), ("b", "B")]

            def queryset(self, request, queryset):
                return queryset

        f = StatusFilter(make_request(query={"st": "a"}), doc_admin())
        assert f.value() == "a"
        assert f.has_output() is True
        choices = f.choices_for_template()
        assert choices[0]["label"] == "All"
        assert any(c["label"] == "A" and c["selected"] for c in choices)


class TestMultiSiteRouter:
    def test_route_names_namespaced(self):
        site = AdminSite(name="ops")
        router = build_admin_router(site)
        names = {r.name for r in router.routes}
        assert "ops:index" in names
        assert "ops:model_list" in names
        assert "admin:index" not in names

    def test_safe_error_message(self):
        from aksara.contrib.admin.views import _safe_error_message
        assert _safe_error_message(ValueError("bad slug"), "save") == "bad slug"
        generic = _safe_error_message(RuntimeError("secret internals"), "save")
        assert "secret internals" not in generic


class TestAdminRoutingSecurity:
    def test_custom_prefix_sets_matching_csrf_path_and_login_default(self):
        from starlette.testclient import TestClient
        from aksara import Aksara
        from aksara.contrib.admin import include_admin

        site = AdminSite(name="manage")
        app = Aksara(database_url=None, debug=True, auto_discover_views=False, enable_admin=False)
        include_admin(app, prefix="/manage", site=site)

        with TestClient(app, raise_server_exceptions=False, follow_redirects=False) as client:
            login = client.get("/manage/login/")
            assert login.status_code == 200
            assert "Path=/manage" in login.headers["set-cookie"]
            csrf_token = client.cookies.get("aksara_admin_csrf")

            user = MagicMock()
            user.is_staff = True
            with patch("aksara.contrib.auth.authenticate", new=AsyncMock(return_value=user)):
                with patch(
                    "aksara.contrib.auth.create_session_token",
                    new=AsyncMock(return_value="token"),
                ):
                    response = client.post(
                        "/manage/login/",
                        data={
                            "username": "admin@test.com",
                            "password": "secret",
                            "csrf_token": csrf_token,
                        },
                    )

            assert response.status_code == 302
            assert response.headers["location"] == "/manage/"

    def test_custom_login_and_logout_urls_are_used(self):
        from starlette.testclient import TestClient
        from aksara import Aksara
        from aksara.contrib.admin import include_admin

        site = AdminSite(
            name="secure",
            login_url="/staff/login",
            logout_url="/signed-out",
        )
        app = Aksara(database_url=None, debug=True, auto_discover_views=False, enable_admin=False)
        include_admin(app, prefix="/secure", site=site)

        with TestClient(app, raise_server_exceptions=False, follow_redirects=False) as client:
            denied = client.get("/secure/")
            assert denied.status_code == 302
            assert denied.headers["location"] == "/staff/login?next=%2Fsecure%2F"

            csrf = client.get("/secure/login/")
            assert csrf.status_code == 200
            response = client.post(
                "/secure/logout/",
                data={"csrf_token": client.cookies.get("aksara_admin_csrf")},
            )
            assert response.status_code == 302
            assert response.headers["location"] == "/signed-out"

    def test_configured_title_and_index_title_render(self):
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.testclient import TestClient
        from aksara import Aksara
        from aksara.contrib.admin import include_admin

        class StaffMW(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                request.state.user = staff_user()
                return await call_next(request)

        site = AdminSite(
            name="ops",
            title="Ops Browser",
            site_header="Ops Console",
            index_title="Operations Home",
        )
        app = Aksara(database_url=None, debug=True, auto_discover_views=False, enable_admin=False)
        app.add_middleware(StaffMW)
        include_admin(app, prefix="/ops", site=site)

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/ops/")

        assert response.status_code == 200
        assert "<title>Operations Home - Ops Browser</title>" in response.text
        assert "<h1>Operations Home</h1>" in response.text


class TestModelAdminSaveSafety:
    async def test_invalid_m2m_ids_do_not_save_or_clear_relations(self):
        class Related:
            objects = SimpleNamespace(get=AsyncMock(side_effect=LookupError("missing")))

        class FakeModel:
            meta = SimpleNamespace(
                many_to_many={"tags": SimpleNamespace(to_model=Related)}
            )

        obj = SimpleNamespace(save=AsyncMock())
        ma = ModelAdmin(FakeModel, AdminSite(name="m2m"))

        with pytest.raises(ValueError):
            await ma.save_model(make_request(), obj, {"title": "x", "tags": ["bad"]}, False)

        obj.save.assert_not_awaited()


# ---------------------------------------------------------------------------
# DB-backed integration of ORM-dependent features
# ---------------------------------------------------------------------------

class _Thing(Model):
    name = fields.String()
    category = fields.String()
    qty = fields.Integer(default=0)

    class Meta:
        app_label = "things"


class _ThingAdmin(ModelAdmin):
    list_display = ["name", "category", "qty"]
    search_fields = ["name"]
    list_filter = ["category"]
    ordering = ["-qty"]
    actions = ["delete_selected"]


@pytest.fixture
async def thing_admin():
    """Create the things table, seed rows, yield a configured ModelAdmin."""
    from aksara.db import Database

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is unavailable for live database tests")

    database = Database(database_url)
    await database.connect()
    await database.execute(f"DROP TABLE IF EXISTS {_Thing.__tablename__} CASCADE")
    await database.execute(_Thing.get_create_table_sql())
    for n, c, q in [
        ("alpha", "tools", 5),
        ("beta", "tools", 1),
        ("gamma", "food", 9),
        ("delta", "food", 3),
        ("epsilon", "tools", 7),
    ]:
        await _Thing.objects.create(name=n, category=c, qty=q)

    site = AdminSite(name="admin")
    ma = _ThingAdmin(_Thing, site)
    try:
        yield ma
    finally:
        await database.execute(f"DROP TABLE IF EXISTS {_Thing.__tablename__} CASCADE")
        await database.disconnect()


async def _base_qs(ma):
    import inspect
    qs = ma.get_queryset(make_request(user=staff_user()))
    return await qs if inspect.isawaitable(qs) else qs


class TestDBBackedFeatures:
    async def test_search_filters_to_matching_rows(self, thing_admin):
        ma = thing_admin
        req = make_request(user=staff_user())
        qs = ma.get_search_results(req, await _base_qs(ma), "a")
        assert await qs.count() == 4  # alpha, beta, gamma, delta

    async def test_ordering_and_pagination(self, thing_admin):
        ma = thing_admin
        page1 = await (await _base_qs(ma)).order_by(*ma.get_ordering(make_request())).limit(2).offset(0).all()
        page2 = await (await _base_qs(ma)).order_by(*ma.get_ordering(make_request())).limit(2).offset(2).all()
        assert [r.name for r in page1] == ["gamma", "epsilon"]
        assert [r.name for r in page2] == ["alpha", "delta"]

    async def test_field_filter_choices_and_apply(self, thing_admin):
        ma = thing_admin
        req = make_request(user=staff_user(), query={"category": "food"})
        filt = await FieldListFilter.create("category", req, ma)
        labels = {label for _v, label in filt.lookup_choices}
        assert {"tools", "food"} <= labels
        filtered = filt.apply(await _base_qs(ma))
        assert await filtered.count() == 2

    async def test_delete_selected_action(self, thing_admin):
        ma = thing_admin
        req = make_request(user=staff_user())
        rows = await (await _base_qs(ma)).all()
        ids = [str(rows[0].id), str(rows[1].id)]
        target = (await _base_qs(ma)).filter(id__in=ids)
        await delete_selected(ma, req, target)
        assert await (await _base_qs(ma)).count() == 3


# ---------------------------------------------------------------------------
# End-to-end HTTP integration (list render, filters, pagination, bulk action)
# ---------------------------------------------------------------------------

class Gadget(Model):
    name = fields.String()
    category = fields.String()
    qty = fields.Integer(default=0)

    class Meta:
        app_label = "lab"


@action(description="Zero out qty", permissions=["change"])
async def _zero_qty(self, request, queryset):
    n = await queryset.update(qty=0)
    self.message_user(request, f"Zeroed {n}", level="success")


class GadgetAdmin(ModelAdmin):
    list_display = ["name", "category", "qty", "badge"]
    list_display_links = ["name"]
    search_fields = ["name"]
    list_filter = ["category"]
    ordering = ["-qty"]
    list_per_page = 2
    actions = ["delete_selected", "zero_qty"]
    zero_qty = _zero_qty

    def badge(self, obj):
        return f'<span class="bdg">{obj.category}</span>'

    badge.short_description = "Cat"
    badge.allow_html = True


def _staff_middleware():
    from starlette.middleware.base import BaseHTTPMiddleware
    from unittest.mock import MagicMock

    class StaffMW(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            user = MagicMock()
            user.is_staff = True
            user.email = "admin@test.com"
            user.id = "u1"
            request.state.user = user
            return await call_next(request)

    return StaffMW


class TestAdminHTTPIntegration:
    """Full request/response cycle against a live database."""

    def setup_method(self):
        ModelRegistry.clear()
        from aksara.contrib.admin import site
        site.clear()

    def _seed(self):
        import asyncio
        from aksara.db import Database

        async def run():
            db = Database(os.getenv("DATABASE_URL"))
            await db.connect()
            await db.execute(f"DROP TABLE IF EXISTS {Gadget.__tablename__} CASCADE")
            await db.execute(Gadget.get_create_table_sql())
            for n, c, q in [
                ("aa", "tools", 5),
                ("ab", "tools", 1),
                ("ac", "food", 9),
                ("ad", "food", 3),
                ("ae", "tools", 7),
            ]:
                await Gadget.objects.create(name=n, category=c, qty=q)
            await db.disconnect()

        asyncio.run(run())

    def _drop(self):
        import asyncio
        from aksara.db import Database

        async def run():
            db = Database(os.getenv("DATABASE_URL"))
            await db.connect()
            await db.execute(f"DROP TABLE IF EXISTS {Gadget.__tablename__} CASCADE")
            await db.disconnect()

        asyncio.run(run())

    def _qtys(self):
        import asyncio
        from aksara.db import Database

        async def run():
            db = Database(os.getenv("DATABASE_URL"))
            await db.connect()
            rows = await Gadget.objects.all()
            await db.disconnect()
            return sorted(r.qty for r in rows)

        return asyncio.run(run())

    def test_list_render_and_bulk_action(self):
        if not os.getenv("DATABASE_URL"):
            pytest.skip("DATABASE_URL is unavailable for live database tests")

        import re
        from starlette.testclient import TestClient
        from aksara import Aksara
        from aksara.conf import configure, settings
        from aksara.contrib.admin import site

        site.register(Gadget, GadgetAdmin)
        self._seed()
        # CSRF round-tripping is covered by the existing login/add/delete POST
        # tests; here we isolate the new action-execution path.
        original_csrf = settings.admin_csrf_enabled
        configure(admin_csrf_enabled=False)
        try:
            app = Aksara(database_url=os.getenv("DATABASE_URL"), debug=True, auto_discover_views=False)
            app.add_middleware(_staff_middleware())

            with TestClient(app, raise_server_exceptions=False, follow_redirects=False) as client:
                # List renders with the full feature surface.
                resp = client.get("/admin/lab/gadget/?o=-qty&category=tools")
                assert resp.status_code == 200
                body = resp.text
                assert "Filters" in body                 # filter sidebar
                assert "data-select-all" in body          # action checkboxes
                assert "sortable-header" in body           # sortable columns
                assert 'class="bdg"' in body               # custom HTML column
                assert "Zero out qty" in body              # custom action

                # Add form renders fieldsets.
                add = client.get("/admin/lab/gadget/add/")
                assert add.status_code == 200

                # Search narrows the list.
                searched = client.get("/admin/lab/gadget/?q=aa")
                assert searched.status_code == 200

                # Run a bulk action on two selected rows.
                page = client.get("/admin/lab/gadget/?all=1")
                ids = re.findall(r'name="_selected" value="([^"]+)"', page.text)[:2]
                assert len(ids) == 2

                action_resp = client.post(
                    "/admin/lab/gadget/",
                    data={"action": "zero_qty", "_selected": ids},
                )
                assert action_resp.status_code == 303

            # Two rows zeroed by the action.
            assert self._qtys().count(0) == 2
        finally:
            configure(admin_csrf_enabled=original_csrf)
            self._drop()
