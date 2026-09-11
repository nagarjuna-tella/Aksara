# Routing

Register ViewSets after importing their models and configuring the application.
Use the [first project](../getting-started/first-project.md) for the complete
startup, database, and identity setup. Registration itself neither applies
migrations nor authenticates requests.

## Direct registration

`include_viewset(router, viewset_cls)` accepts a FastAPI application or router
and a `ModelViewSet` class. It registers routes in place and returns `None`.
Set `prefix` and `tags` on the ViewSet; they are not keyword arguments to this
helper. The [ViewSet example](viewsets.md) supplies the tutorial's
`TicketViewSet`, including explicit permissions and disabled optional exposure.

```python title="app/urls.py"
from aksara import include_viewset
from .views import TicketViewSet


def register_routes(app):
    include_viewset(app, TicketViewSet)
```

Call `register_routes(app)` once during application construction. A
`urlpatterns` list can organize classes, but the list alone does not register
anything. Do not combine explicit registration and discovery for the same
ViewSet.

## Generated routes

With `prefix = "/api/tickets"`:

| Method | Path | Handler |
| --- | --- | --- |
| GET | `/api/tickets/` | `list` |
| POST | `/api/tickets/` | `create` |
| GET | `/api/tickets/{pk}` | `retrieve` |
| PATCH | `/api/tickets/{pk}` | `update` |
| DELETE | `/api/tickets/{pk}` | `delete` |

There is no generated PUT handler. Detail routes have no trailing slash.
When enabled, SSE uses `/api/tickets/stream`; the introductory example disables
it. Collection actions are registered before the parameterized detail routes.
Detail actions use `/api/tickets/{pk}/<action-path>`.

Set the full public path with `prefix`, not `url_prefix`. If omitted, the
ViewSet uses the model's `__tablename__` prefixed with `/`; do not infer the
path from English pluralization of a class name.

## Discovery

`discover_viewsets(module)` inspects an imported **module object** and returns
its public `ModelViewSet` subclasses. It does not import a dotted string or
register the returned classes. Imported subclasses are included too; discovery
does not restrict results to classes originally defined in that module.
The base `ModelViewSet` is excluded. Keep discovery modules deliberate to avoid
accidentally exposing imported ViewSets.

As an alternative to direct registration:

```python title="app/discovered_urls.py"
from aksara import include_viewset
from aksara.api import discover_viewsets
from . import views


def register_routes(app):
    for viewset_class in discover_viewsets(views):
        include_viewset(app, viewset_class)
```

### Import-and-register helpers

| Helper | Behavior |
| --- | --- |
| `include_app_viewsets(app, app_label, module_name="api")` | Imports `<app_label>.<module_name>`, discovers and registers classes, returns their list. |
| `include_all_app_viewsets(app, module_name="api")` | Applies that helper to `settings.apps`, returning a mapping for apps with registered classes. |

Import these helpers from `aksara.api`. The default module is `api`, not
`views` or `viewsets`; pass `module_name="views"` for a project using `views.py`.
A missing-module error results in an empty registration list. Other import
errors may warn and skip registration. Check the returned classes and actual
route inventory: successful startup alone does not prove the expected API was
registered.

## Route names and reverse lookup

The generated CRUD route names come from endpoint functions, not a
`<model>-<action>` naming contract. `url_name_prefix` is not a supported ViewSet
option. Do not copy `request.url_for("ticket-detail", ...)` without verifying
that a route with that name exists. Applications requiring unique reverse
lookup names should explicitly name their own routes and test resolution.

## Manual routes and nested resources

Use FastAPI's `APIRouter` for application-specific route signatures and attach
it with `app.include_router(router)`. Your handler owns authentication,
authorization, input validation, and database transaction requirements.

The ViewSet helper does not accept an extra `prefix` argument or supply
DRF-style `self.kwargs`. Adding a parent identifier to a path does not establish
parent-child ownership or filter all CRUD operations. For a nested resource,
validate the parent and tenant explicitly and test both collection and object
access. The [tenant tutorial](../tutorials/ticket-desk-tenancy.md) demonstrates
relationship ownership checks without assuming nested routing supplies them.

## Custom action security

In v0.7.0, registering `@action` does **not** automatically invoke ViewSet or
decorator permission checks for HTTP. Follow the explicit authorization example
in [Actions](actions.md). MCP metadata is not an HTTP permission wrapper.

## Verify registration

Inspect the application's actual routes and generated OpenAPI, then exercise
requests with valid and invalid identities. Route/schema inspection proves
registration; HTTP tests prove request behavior. The tutorial includes both
successful calls and authorization failures.
