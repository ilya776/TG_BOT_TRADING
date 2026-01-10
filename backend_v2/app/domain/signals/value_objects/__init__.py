"""Signal value objects.

Re-exports TradeSide and TradeType (as SignalType) from trading
for API convenience - signals use these types.
"""

from .signal_priority import SignalPriority
from .signal_source import SignalSource
from .signal_status import SignalStatus

# Re-export from trading for convenience (signals use these types)
from app.domain.trading.value_objects import TradeSide, TradeType

# Alias for semantic clarity in signal context
SignalType = TradeType

__all__ = [
    "SignalStatus",
    "SignalPriority",
    "SignalSource",
    "TradeSide",
    "SignalType",
    "TradeType",
]
