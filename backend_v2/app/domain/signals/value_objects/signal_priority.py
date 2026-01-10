"""Signal Priority - processing priority levels."""

from enum import Enum


class SignalPriority(str, Enum):
    """Signal processing priority.

    Priority determines queue order:
    - HIGH: Process first (VIP whales, large moves)
    - MEDIUM: Normal priority (regular whales)
    - LOW: Process last (small whales, low volume)

    Priority calculation factors:
    - Whale tier (VIP > Premium > Regular)
    - Position size (large > medium > small)
    - Historical win rate (high > medium > low)
    - Time sensitivity (breakout > swing > position)
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    def __lt__(self, other: "SignalPriority") -> bool:
        """Compare priorities for sorting (HIGH < MEDIUM < LOW).

        Args:
            other: Other priority to compare.

        Returns:
            True if self has higher priority than other.

        Note:
            HIGH < MEDIUM < LOW для використання в priority queue.
        """
        priority_order = {
            SignalPriority.HIGH: 1,
            SignalPriority.MEDIUM: 2,
            SignalPriority.LOW: 3,
        }
        return priority_order[self] < priority_order[other]

    @classmethod
    def from_whale_tier(cls, tier: str) -> "SignalPriority":
        """Calculate priority від whale tier.

        Args:
            tier: Whale tier (vip, premium, regular).

        Returns:
            SignalPriority based on tier.
        """
        tier_map = {
            "vip": cls.HIGH,
            "premium": cls.MEDIUM,
            "regular": cls.LOW,
        }
        return tier_map.get(tier.lower(), cls.MEDIUM)
