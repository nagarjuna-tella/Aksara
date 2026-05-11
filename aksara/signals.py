"""
Lifecycle Signals (Pub/Sub)

Provides a mechanism to decouple applications by allowing certain senders
to notify a set of receivers that some action has taken place.
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional, Tuple


class Signal:
    """
    Base class for all signals.
    """
    
    def __init__(self, name: Optional[str] = None):
        self.name = name
        self.receivers: List[Tuple[Any, Callable]] = []
        
    def connect(self, receiver: Callable, sender: Any = None) -> None:
        """
        Connect receiver to sender for signal.
        
        Args:
            receiver: An async callable that will receive the signal
            sender: The sender to connect to (if None, receives from any sender)
        """
        self.receivers.append((sender, receiver))
        
    def disconnect(self, receiver: Callable, sender: Any = None) -> bool:
        """
        Disconnect receiver from sender for signal.
        
        Args:
            receiver: The callable to disconnect
            sender: The sender to disconnect from
            
        Returns:
            True if disconnected, False if not found
        """
        try:
            self.receivers.remove((sender, receiver))
            return True
        except ValueError:
            return False
            
    async def send(self, sender: Any, **named) -> List[Tuple[Callable, Any]]:
        """
        Send signal from sender to all connected receivers.
        
        Receivers must be async functions.
        
        Args:
            sender: The sender of the signal
            **named: Named arguments to pass to receivers
            
        Returns:
            List of tuple pairs [(receiver, response), ...]
        """
        responses = []
        
        for r_sender, receiver in self.receivers:
            if r_sender is None or r_sender == sender:
                response = await receiver(sender=sender, **named)
                responses.append((receiver, response))

        return responses

    async def send_robust(self, sender: Any, **named) -> List[Tuple[Callable, Any]]:
        """
        Send signal from sender to all connected receivers, catching errors.
        
        Args:
            sender: The sender of the signal
            **named: Named arguments to pass to receivers
            
        Returns:
            List of tuple pairs [(receiver, response_or_exception), ...]
        """
        responses = []
        
        for r_sender, receiver in self.receivers:
            if r_sender is None or r_sender == sender:
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
