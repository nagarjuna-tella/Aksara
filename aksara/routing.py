"""Read effective route metadata without changing FastAPI's routing tree."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from fastapi import routing


def iter_routes(app: Any) -> Iterator[Any]:
    """Yield effective paths, endpoints and metadata across supported FastAPI versions.

    Newer FastAPI keeps included routers lazy. Its route-context iterator applies
    nested include prefixes and overrides; walking original_router directly loses
    that information. Mounts remain mounts, matching the older flat API contract.
    Returned objects are metadata views and must not be used to mutate routing.
    """
    routes = getattr(app, "routes", ()) or ()
    contexts = getattr(routing, "iter_route_contexts", None)
    yield from contexts(routes) if contexts is not None else routes
