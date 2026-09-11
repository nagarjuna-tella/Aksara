"""Check the documented ViewSet registration against real generated routes."""

import ast
import inspect
import re
from pathlib import Path

from fastapi import FastAPI

from aksara import Model, ModelViewSet, fields, include_viewset

ROOT = Path(__file__).resolve().parents[2]


def test_viewset_example_registers_documented_routes():
    page = (ROOT / "docs/docs/api/viewsets.md").read_text()
    source = re.search(r'```python title="app/views.py"\n(.*?)```', page, re.DOTALL).group(1)
    tree = ast.parse(source)
    # Supply the tutorial model prerequisite; execute the ViewSet body unchanged.
    tree.body = [node for node in tree.body if not (isinstance(node, ast.ImportFrom) and node.level)]

    class ReferenceTicket(Model):
        subject = fields.String(max_length=200)

    namespace = {"Ticket": ReferenceTicket}
    exec(compile(tree, "documented-viewset", "exec"), namespace)  # noqa: S102 - trusted repository documentation
    app = FastAPI()
    include_viewset(app, namespace["TicketViewSet"])
    routes = {(route.path, method) for route in app.routes for method in route.methods
              if route.path.startswith("/api/tickets")}
    assert routes == {
        ("/api/tickets/", "GET"), ("/api/tickets/", "POST"),
        ("/api/tickets/{pk}", "GET"), ("/api/tickets/{pk}", "PATCH"),
        ("/api/tickets/{pk}", "DELETE"),
    }
    schema = app.openapi()
    assert "201" in schema["paths"]["/api/tickets/"]["post"]["responses"]
    assert "200" in schema["paths"]["/api/tickets/{pk}"]["delete"]["responses"]
    view = namespace["TicketViewSet"]()
    assert [type(p).__name__ for p in view.get_permissions()] == ["IsAuthenticated"]
    assert not view.ai_exposed and not view.stream_enabled


def test_documented_viewset_defaults_and_hooks():
    assert ModelViewSet.default_limit == 20
    assert ModelViewSet.max_limit == 100
    assert ModelViewSet.ai_exposed and ModelViewSet.stream_enabled
    assert not inspect.iscoroutinefunction(ModelViewSet.get_queryset)
    assert not inspect.iscoroutinefunction(ModelViewSet.check_permissions)
    for name in ("list_serializer_class", "retrieve_serializer_class",
                 "create_serializer_class", "update_serializer_class"):
        assert getattr(ModelViewSet, name) is None
    for name in ("serializer_class", "authentication_classes", "queryset", "filterset_fields",
                 "allowed_actions", "excluded_actions", "page_size", "get_request_data"):
        assert not hasattr(ModelViewSet, name)
