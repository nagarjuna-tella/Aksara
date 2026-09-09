"""Internal cleanup for connections owned by session/transaction contexts."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any


async def release_owned_connection(
    pool: Any,
    connection: Any,
    reset: Callable[[Any], Awaitable[None]] | None,
    original_error: BaseException | None,
) -> None:
    """Always release, finish release on cancellation, and preserve the first error.

    Pool.release resets unfinished transactions and session settings (or discards
    an unusable connection). Tenant reset is best effort, never a release gate.
    ContextVar tokens must be restored by the caller in the owning task.
    """
    error = original_error

    def remember(exc: BaseException) -> None:
        nonlocal error
        if error is None:
            error = exc
        elif exc is not error:
            error.add_note(f"Connection cleanup also failed: {type(exc).__name__}")

    if reset is not None:
        try:
            await reset(connection)
        except BaseException as exc:  # noqa: BLE001 - release must survive cancellation/errors
            remember(exc)

    # A cancellation of the owner must not cancel or orphan pool release.
    release = asyncio.ensure_future(pool.release(connection))
    while not release.done():
        try:
            await asyncio.shield(release)
        except asyncio.CancelledError as exc:
            remember(exc)
        except BaseException as exc:  # noqa: BLE001 - release must survive cancellation/errors
            remember(exc)
            break
    try:
        release.result()
    except BaseException as exc:  # noqa: BLE001 - release must survive cancellation/errors
        remember(exc)
    if error is not None and original_error is None:
        raise error
