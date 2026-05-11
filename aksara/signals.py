"""
Lifecycle Signals (Pub/Sub)

Provides a mechanism to decouple applications by allowing certain senders
to notify a set of receivers that some action has taken place.
"""

import weakref
from collections import OrderedDict
from typing import Any, Callable, List, Optional, Tuple


def _make_receiver_ref(receiver: Callable) -> Any:
    """Wrap bound methods in a WeakMethod to avoid keeping instances alive."""
    if hasattr(receiver, "__self__") and hasattr(receiver, "__func__"):
        try:
            return weakref.WeakMethod(receiver)
        except TypeError:
            pass
    return receiver


def _resolve_ref(ref_or_callable: Any) -> Optional[Callable]:
    """Resolve a (possibly weak) ref; returns None if the referent was GC'd."""
    if isinstance(ref_or_callable, weakref.ref):
        return ref_or_callable()
    return ref_or_callable


def _receiver_key(sender: Any, receiver: Callable) -> tuple:
    """Stable hashable key for a (sender, receiver) pair.

    For bound methods the key uses (id(self), id(func)) so that accessing
    ``obj.method`` at different times (which creates a new wrapper each time)
    still maps to the same slot.
    """
    sender_id = id(sender)
    if hasattr(receiver, "__self__") and hasattr(receiver, "__func__"):
        return (sender_id, id(receiver.__self__), id(receiver.__func__))
    return (sender_id, id(receiver))


class Signal:
    """
    Base class for all signals.

    connect/disconnect are O(1).  Receivers that are bound methods are stored
    as weak references so they do not prevent garbage collection of the owning
    object.  Dead references are pruned lazily during send().
    """

    def __init__(self, name: Optional[str] = None):
        self.name = name
        # OrderedDict: preserves connect order, O(1) insert/delete.
        # key → (sender, ref_or_callable)
        self._receivers: "OrderedDict[tuple, Tuple[Any, Any]]" = OrderedDict()

    # ------------------------------------------------------------------
    # Backward-compatible public attribute
    # ------------------------------------------------------------------

    @property
    def receivers(self) -> List[Tuple[Any, Callable]]:
        """Read-only list of live (sender, callable) pairs (for compatibility)."""
        live = []
        for r_sender, ref in self._receivers.values():
            resolved = _resolve_ref(ref)
            if resolved is not None:
                live.append((r_sender, resolved))
        return live

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def connect(self, receiver: Callable, sender: Any = None) -> None:
        """Connect *receiver* to *sender* for this signal.

        Args:
            receiver: An async callable that will receive the signal.
            sender:   The sender to filter on (None = any sender).
        """
        key = _receiver_key(sender, receiver)
        self._receivers[key] = (sender, _make_receiver_ref(receiver))

    def disconnect(self, receiver: Callable, sender: Any = None) -> bool:
        """Disconnect *receiver* from *sender* for this signal.

        Returns True if a matching entry was found and removed, False otherwise.
        """
        key = _receiver_key(sender, receiver)
        if key in self._receivers:
            del self._receivers[key]
            return True
        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _iter_live(self, sender: Any) -> List[Callable]:
        """Return live receivers for *sender*, pruning any dead weak refs."""
        dead: List[tuple] = []
        live: List[Callable] = []
        for key, (r_sender, ref) in list(self._receivers.items()):
            if r_sender is None or r_sender is sender or r_sender == sender:
                resolved = _resolve_ref(ref)
                if resolved is None:
                    dead.append(key)
                else:
                    live.append(resolved)
        for key in dead:
            self._receivers.pop(key, None)
        return live

    # ------------------------------------------------------------------
    # Send methods
    # ------------------------------------------------------------------

    async def send(self, sender: Any, **named) -> List[Tuple[Callable, Any]]:
        """Send signal from *sender* to all connected receivers.

        Receivers must be async callables.

        Returns:
            List of (receiver, response) pairs.
        """
        responses = []
        for receiver in self._iter_live(sender):
            response = await receiver(sender=sender, **named)
            responses.append((receiver, response))
        return responses

    async def send_robust(self, sender: Any, **named) -> List[Tuple[Callable, Any]]:
        """Send signal, catching and returning exceptions instead of raising.

        Returns:
            List of (receiver, response_or_exception) pairs.
        """
        responses = []
        for receiver in self._iter_live(sender):
            try:
                response = await receiver(sender=sender, **named)
                responses.append((receiver, response))
            except Exception as e:
                responses.append((receiver, e))
        return responses


# Built-in Model Lifecycle Signals
pre_save = Signal("pre_save")
post_save = Signal("post_save")
pre_delete = Signal("pre_delete")
post_delete = Signal("post_delete")
