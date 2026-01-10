"""ProcessSignalCommand - process next signal from queue.

Command для обробки наступного signal з priority queue.
Handler викличе ExecuteCopyTradeHandler для кожного follower whale'а.
"""

from dataclasses import dataclass

from app.application.shared import Command
from app.domain.signals.value_objects import SignalPriority


@dataclass(frozen=True)
class ProcessSignalCommand(Command):
    """Process next signal from queue.

    Args:
        min_priority: Minimum priority to process (default LOW = all signals).

    Usage:
        >>> command = ProcessSignalCommand(min_priority=SignalPriority.HIGH)
        >>> result = await handler.handle(command)
        >>> print(f"Processed signal {result.signal_id}, executed {result.trades_count} trades")
    """

    min_priority: SignalPriority = SignalPriority.LOW
