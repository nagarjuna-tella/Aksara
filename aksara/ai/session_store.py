"""
AI Investigation Session Store  (v0.5.40)

In-memory store for investigation sessions.  Provides CRUD operations
that the console engine and Studio API endpoints use to persist sessions
across multiple user interactions within the same process lifetime.

v0.5.40: Added ``get_active_session()`` for investigation continuation
support — the console engine uses this to resume the most-recent
non-completed session when the user types "continue" or "next".

Usage::

    from aksara.ai.session_store import (
        create_session,
        get_session,
        update_session,
        list_sessions,
        delete_session,
        get_active_session,
    )

    session = create_session("Why is the app slow?")
    session = get_session(session.id)
    active  = get_active_session()
    all_sessions = list_sessions()

Thread-safety note: the store uses a plain ``dict``.  In the single-process
uvicorn dev-server scenario this is fine.  For production with workers,
sessions would need to be moved to the database — but that is a future
enhancement beyond v0.5.40.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from aksara.ai.investigation import InvestigationSession

logger = logging.getLogger("aksara.ai.session_store")

# ─── In-Memory Store ─────────────────────────────────────────────────────────

_sessions: Dict[str, InvestigationSession] = {}


def create_session(goal: str) -> InvestigationSession:
    """Create a new investigation session and store it.

    Args:
        goal: The user's natural-language investigation goal.

    Returns:
        The newly created ``InvestigationSession``.
    """
    session = InvestigationSession(goal=goal)
    _sessions[session.id] = session
    logger.debug("Created investigation session %s: %s", session.id, goal)
    return session


def get_session(session_id: str) -> Optional[InvestigationSession]:
    """Retrieve a session by ID.

    Args:
        session_id: The unique session identifier.

    Returns:
        The session if found, otherwise ``None``.
    """
    return _sessions.get(session_id)


def update_session(session: InvestigationSession) -> InvestigationSession:
    """Persist changes to an existing session.

    Args:
        session: The session object with updated fields.

    Returns:
        The same session (for chaining).
    """
    session.touch()
    _sessions[session.id] = session
    return session


def list_sessions() -> List[InvestigationSession]:
    """Return all sessions ordered by creation time (newest first).

    Returns:
        List of all stored sessions.
    """
    return sorted(
        _sessions.values(),
        key=lambda s: s.created_at,
        reverse=True,
    )


def delete_session(session_id: str) -> bool:
    """Remove a session from the store.

    Args:
        session_id: The unique session identifier.

    Returns:
        ``True`` if the session was found and deleted, ``False`` otherwise.
    """
    if session_id in _sessions:
        del _sessions[session_id]
        logger.debug("Deleted investigation session %s", session_id)
        return True
    return False


def clear_sessions() -> int:
    """Remove all sessions.  Mainly useful in tests.

    Returns:
        The number of sessions that were cleared.
    """
    count = len(_sessions)
    _sessions.clear()
    return count


def get_active_session() -> Optional[InvestigationSession]:
    """Return the most-recent session that is still in progress.

    An "active" session is one whose status is ``"created"`` or
    ``"running"`` — i.e. it has pending steps that have not yet
    been executed.

    This is used by the console engine's continuation flow: when the
    user types ``"continue"`` or ``"next"``, the engine calls this to
    find the session to resume.

    Returns:
        The most-recently-updated active session, or ``None`` if no such
        session exists in the in-memory store.

    Example::

        session = create_session("Investigate performance")
        active = get_active_session()
        assert active is not None
        assert active.id == session.id
    """
    active_statuses = {"created", "running"}
    candidates = [
        s for s in _sessions.values() if s.status in active_statuses
    ]
    if not candidates:
        return None
    # Return the most-recently updated session.
    return max(candidates, key=lambda s: s.updated_at)
