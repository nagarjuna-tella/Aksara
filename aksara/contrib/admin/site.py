"""
Admin Site

Central AdminSite class for managing model registrations and admin-wide
configuration (branding, theme, access control, custom dashboard).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, Type

if TYPE_CHECKING:
    from aksara.model.base import Model
    from aksara.contrib.admin.options import ModelAdmin
    from fastapi import Request


class AdminSite:
    """
    Central admin site managing model registrations and presentation.

    Usage:
        from aksara.contrib.admin import site, ModelAdmin
        from myapp.models import Article

        site.register(Article)

        @site.register(Article)
        class ArticleAdmin(ModelAdmin):
            list_display = ["title", "author", "created_at"]

    A custom site can be created and mounted independently:

        from aksara.contrib.admin import AdminSite, include_admin

        ops = AdminSite(name="ops", site_header="Ops Console")
        ops.register(Incident)
        include_admin(app, prefix="/ops", site=ops)
    """

    def __init__(
        self,
        name: str = "admin",
        *,
        title: str = "Aksara Admin",
        site_header: str = "Aksara Admin",
        index_title: str = "Dashboard",
        login_url: Optional[str] = None,
        logout_url: Optional[str] = None,
        theme: str = "default",
        index_template: Optional[str] = None,
        extra_css: Optional[List[str]] = None,
        permission_classes: Optional[List[Any]] = None,
    ):
        """
        Args:
            name: Identifier for this site (used in route names).
            title: Browser tab text.
            site_header: Header shown on every admin page.
            index_title: Heading on the dashboard.
            login_url / logout_url: Override auth redirect targets.
            theme: "default" or "dark".
            index_template: Custom dashboard template path.
            extra_css: Additional stylesheet URLs to include.
            permission_classes: Optional BasePermission list gating site access.
                When provided, it replaces the default staff-only gate.
        """
        self.name = name
        self.title = title
        self.site_header = site_header
        self.index_title = index_title
        self.login_url = login_url
        self.logout_url = logout_url
        self.theme = theme
        self.index_template = index_template
        self.extra_css = list(extra_css or [])
        self.permission_classes = list(permission_classes or [])
        self._registry: Dict[Type["Model"], "ModelAdmin"] = {}
        self._index_view_func: Optional[Callable] = None

    # -------------------------------------------------------------------------
    # Registration
    # -------------------------------------------------------------------------

    def register(
        self,
        *models: Any,
        admin_class: Optional[Type["ModelAdmin"]] = None,
    ):
        """
        Register one or more models with the admin site.

        Direct call:        site.register(Book)
        With custom admin:  site.register(Book, BookAdmin)
        As a decorator:     @site.register(Book)
                            class BookAdmin(ModelAdmin): ...
        Several models:     @site.register(Post, Draft)
                            class ContentAdmin(ModelAdmin): ...

        Raises:
            ValueError: If a model is already registered, or no model is given.
        """
        from aksara.model.base import Model
        from aksara.contrib.admin.options import ModelAdmin as DefaultModelAdmin

        model_classes: List[Type["Model"]] = []
        inline_admin: Optional[Type["ModelAdmin"]] = admin_class

        for arg in models:
            if isinstance(arg, type) and issubclass(arg, DefaultModelAdmin):
                inline_admin = arg
            elif isinstance(arg, type) and issubclass(arg, Model):
                model_classes.append(arg)
            else:
                raise TypeError(
                    f"register() expects Model and ModelAdmin classes, got {arg!r}"
                )

        if not model_classes:
            raise ValueError("register() requires at least one model.")

        def _register_one(model: Type["Model"], cls: Type["ModelAdmin"]) -> None:
            if model in self._registry:
                raise ValueError(f"Model {model.__name__} is already registered.")
            self._registry[model] = cls(model, self)

        if inline_admin is not None:
            for model in model_classes:
                _register_one(model, inline_admin)
            return None

        # No admin class yet. Register each model with the default admin now so
        # direct calls work, and return a decorator that re-registers with the
        # decorated class for @decorator usage.
        for model in model_classes:
            _register_one(model, DefaultModelAdmin)

        def decorator(admin_cls: Type["ModelAdmin"]) -> Type["ModelAdmin"]:
            for model in model_classes:
                self._registry[model] = admin_cls(model, self)
            return admin_cls

        return decorator

    def unregister(self, model: Type["Model"]) -> None:
        """Unregister a model from the admin site."""
        self._registry.pop(model, None)

    def is_registered(self, model: Type["Model"]) -> bool:
        """Check if a model is registered."""
        return model in self._registry

    @property
    def registry(self) -> Dict[Type["Model"], "ModelAdmin"]:
        """The model registry (Model class -> ModelAdmin instance)."""
        return self._registry

    def get_model_admin(self, model: Type["Model"]) -> Optional["ModelAdmin"]:
        """Get the ModelAdmin for a registered model."""
        return self._registry.get(model)

    def get_model_by_name(
        self, app_label: str, model_name: str
    ) -> Optional[Type["Model"]]:
        """Look up a registered model by app_label and model name."""
        model_name_lower = model_name.lower()
        for model in self._registry:
            model_app_label = model.meta.app_label or "default"
            if (
                model_app_label == app_label
                and model.__name__.lower() == model_name_lower
            ):
                return model
        return None

    def get_app_list(self) -> Dict[str, list]:
        """Get models grouped by app_label."""
        apps: Dict[str, list] = {}
        for model in self._registry:
            app_label = model.meta.app_label or "default"
            apps.setdefault(app_label, []).append(model)
        return apps

    def clear(self) -> None:
        """Clear all registered models (useful for testing)."""
        self._registry.clear()

    # -------------------------------------------------------------------------
    # Presentation / access
    # -------------------------------------------------------------------------

    def index_view(self, func: Callable) -> Callable:
        """
        Decorator to register a custom dashboard context provider.

        The decorated function receives the request and returns a dict that is
        merged into the index template context:

            @site.index_view
            async def dashboard(request):
                return {"total_users": await User.objects.count()}
        """
        self._index_view_func = func
        return func

    def base_context(self, request: "Request") -> Dict[str, Any]:
        """Common template context for every admin page (branding/theme)."""
        return {
            "site_name": self.site_header,
            "site_title": self.title,
            "site_header": self.site_header,
            "index_title": self.index_title,
            "admin_theme": self.theme,
            "extra_css": self.extra_css,
        }

    def check_site_permission(
        self, request: "Request"
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluate site-level access.

        Returns (allowed, message). When ``permission_classes`` is set it is the
        authority; otherwise access requires an authenticated staff user.
        """
        if self.permission_classes:
            from aksara.permissions import check_permissions

            return check_permissions(self.permission_classes, request)

        user = getattr(request.state, "user", None)
        if user and getattr(user, "is_staff", False):
            return True, None
        return False, "Admin access forbidden. Staff access required."
