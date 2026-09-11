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


def _load_documented_class(page_name, title, model):
    page = (ROOT / page_name).read_text()
    source = re.search(r'```python title="' + re.escape(title) + r'"\n(.*?)```', page, re.DOTALL).group(1)
    tree = ast.parse(source)
    tree.body = [node for node in tree.body if not (isinstance(node, ast.ImportFrom) and node.level)]
    namespace = {"Ticket": model}
    exec(compile(tree, "documented-api", "exec"), namespace)  # noqa: S102 - trusted repository documentation
    return namespace


def test_documented_serializer_validation():
    from aksara.exceptions import ValidationError

    class SerializerTicket(Model):
        subject = fields.String(max_length=200)
        description = fields.Text(default="")
        resolved = fields.Boolean(default=False)

    namespace = _load_documented_class("docs/docs/api/serializers.md", "app/serializers.py", SerializerTicket)
    serializer_class = namespace["TicketCreateSerializer"]
    serializer = serializer_class(data={"subject": "  A ticket  ", "resolved": True})
    assert serializer.is_valid()
    assert serializer.validated_data["subject"] == "A ticket"
    assert "resolved" not in serializer.validated_data
    try:
        serializer_class(data={"subject": "  "}).is_valid()
    except ValidationError as exc:
        assert exc.errors == {"subject": "A visible subject is required"}
    else:
        raise AssertionError("Blank subject was accepted")
    assert "partial" not in inspect.signature(serializer_class).parameters
    assert not hasattr(serializer_class.Meta, "write_only_fields")


def test_custom_action_example_checks_anonymous_identity():
    from fastapi.testclient import TestClient

    class ActionTicket(Model):
        subject = fields.String(max_length=200)

    view = _load_documented_class("docs/docs/api/actions.md", "app/views.py", ActionTicket)["TicketViewSet"]
    app = FastAPI()

    @app.middleware("http")
    async def anonymous(request, call_next):
        request.state.user = None
        return await call_next(request)

    include_viewset(app, view)
    with TestClient(app) as client:
        response = client.get("/api/tickets/00000000-0000-0000-0000-000000000001/summary")
    assert response.status_code == 403
