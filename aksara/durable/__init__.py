"""Durable authorized operation primitives.

The public surface is intentionally small. Storage, leases, fence tokens and
physical attempts remain framework implementation details.
"""

from aksara.durable.states import OperationState

__all__ = ["OperationState"]
