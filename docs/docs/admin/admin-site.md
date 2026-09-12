# AdminSite

The container for your admin interface — it holds registered models and controls branding, theme, and access.

---

## What is AdminSite?

An **AdminSite** holds the models you want to manage and the presentation
settings for the admin. Aksara ships a ready-to-use global instance called
`site`; most apps register everything on it and mount it with `include_admin()`.

```python
from aksara.contrib.admin import site

site.register(Post)
```

You can also create additional, independently-configured sites:

```python
from aksara.contrib.admin import AdminSite

ops = AdminSite(name="ops", site_header="Ops Console", theme="dark")
```

---

## Configuration Options

`AdminSite` accepts the following (all keyword-only except `name`):

| Option | What It Does | Default |
|--------|--------------|---------|
| `name` | Route-name namespace for this site (must be unique per app) | `"admin"` |
| `title` | Browser tab text | `"Aksara Admin"` |
| `site_header` | Header/brand shown on every page | `"Aksara Admin"` |
| `index_title` | Heading on the dashboard | `"Dashboard"` |
| `login_url` / `logout_url` | Override auth redirect targets | `None` |
| `theme` | `"default"` or `"dark"` | `"default"` |
| `index_template` | Custom dashboard template path | `None` |
| `extra_css` | Extra stylesheet URLs to include | `[]` |
| `permission_classes` | `BasePermission` list gating site access | `[]` |

```python
admin = AdminSite(
    name="blog",
    title="Blog Admin",
    site_header="Blog Administration",
    index_title="Dashboard",
    theme="dark",
    extra_css=["/static/blog-admin.css"],
)
```

`title` is used in the browser title, `site_header` is the brand shown in the
admin chrome, and `index_title` is the dashboard heading.

---

## Registering Models

### Decorator (recommended)

```python
from aksara.contrib.admin import site, ModelAdmin

@site.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["title", "author"]
```

### Direct call

```python
class PostAdmin(ModelAdmin):
    list_display = ["title", "author"]

site.register(Post, PostAdmin)   # with a custom admin
site.register(Author)            # with defaults
```

### Multiple models, same config

```python
@site.register(Post, Draft, Archive)
class ContentAdmin(ModelAdmin):
    list_display = ["title", "created_at"]
```

Registering the same model twice raises `ValueError`. Use `site.unregister(Model)`
to remove a registration.

---

## Mounting the Admin

`include_admin()` attaches routes, session and rate-limit middleware, and static
files to your app. CSRF validation runs in the Admin form handlers.

```python
from aksara.contrib.admin import include_admin

include_admin(app)                       # global `site` at /admin/
include_admin(app, prefix="/manage")     # custom prefix
```

The admin CSRF cookie is scoped to the mounted prefix. If you mount at
`/manage`, admin forms under `/manage/` work without sharing that cookie with
unrelated paths.

### Multiple admin sites

Each site has a unique `name`, so several sites can be mounted on one app without
route collisions:

```python
from aksara.contrib.admin import AdminSite, include_admin

public_admin = AdminSite(name="content", site_header="Content")
public_admin.register(Post)
public_admin.register(Category)

ops_admin = AdminSite(name="ops", site_header="Operations")
ops_admin.register(AuditLog)

include_admin(app, prefix="/admin", site=public_admin)
include_admin(app, prefix="/ops", site=ops_admin)
```

Each mounted site has independent route names and branding. The session cookie is
shared, so a user authenticated as staff can move between sites, but each site
still runs its own `permission_classes` and each `ModelAdmin` still runs its own
model/object permission hooks.

### Custom login and logout targets

Use `login_url` when authentication is handled by your own route instead of the
built-in admin login form. Aksara appends a safe relative `next` parameter:

```python
admin = AdminSite(
    name="staff",
    login_url="/accounts/login",
    logout_url="/accounts/signed-out",
)
```

When an unauthenticated user opens `/staff/`, they are redirected to:

```text
/accounts/login?next=/staff/
```

`logout_url` controls where the built-in logout route redirects after clearing
the session cookie.

---

## Custom Dashboard

Use the `@site.index_view` decorator to add context to the dashboard. The function
receives the request and returns a dict that is merged into the index template
context:

```python
@site.index_view
async def dashboard(request):
    return {
        "total_users": await User.objects.count(),
        "draft_count": await Post.objects.filter(is_published=False).count(),
    }
```

To render an entirely custom dashboard, point `index_template` at your own template:

```python
admin = AdminSite(index_template="admin/my_dashboard.html")
```

Your template extends the admin base and can use any keys returned by the
`index_view` function.

---

## Access Control

By default the admin requires an authenticated **staff** user (`is_staff=True`).
To customize site-level access, pass `permission_classes` (see
[Permissions](admin-permissions.md)):

```python
from aksara.permissions import IsAdminUser

admin = AdminSite(permission_classes=[IsAdminUser])
```

When `permission_classes` is set, it replaces the default staff-only gate for
site access, including the built-in login flow. Permission methods may be sync or
async when evaluated by admin requests. Per-model access is still governed by
each `ModelAdmin`'s permission methods.

---

## Security Notes

- Keep `AKSARA_ADMIN_CSRF_ENABLED` enabled outside tests. The admin uses a
  same-site CSRF cookie plus a hidden form token for POST requests.
- Mount admin only on trusted origins. The admin is designed for staff users, not
  for public anonymous traffic.
- If you pass `permission_classes`, those classes replace the default site-level
  staff gate. Model-level and object-level permissions still run afterward.
- Session lookup failures are logged and treated as unauthenticated requests.

---

## Inspecting the Registry

```python
for model, model_admin in site.registry.items():
    print(model.__name__, model_admin.__class__.__name__)

if site.is_registered(Post):
    ...

post_admin = site.get_model_admin(Post)
```

---

## Related Documentation

- [ModelAdmin](model-admin.md) — Customize how models appear
- [Permissions](admin-permissions.md) — Fine-grained access control
- [Actions](actions.md) — Bulk action behavior
- [Widgets](widgets.md) — Form widget customization
- [Models](../orm/models.md) — Define your data structure
