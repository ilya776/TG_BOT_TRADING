"""Signal Status - lifecycle states of a trading signal."""

from enum import Enum


class SignalStatus(str, Enum):
    """Signal lifecycle status.

    Flow:
        PENDING → PROCESSING → PROCESSED
              ↘              ↘ FAILED

    States:
        - PENDING: Signal detected, waiting for processing
        - PROCESSING: Currently being copied by followers
        - PROCESSED: Successfully processed (trades executed)
        - FAILED: Processing failed (error occurred)
        - EXPIRED: Signal expired (too old to process)
    """

    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    EXPIRED = "expired"

    def is_final(self) -> bool:
        """Check if status is final (no more processing).

        Returns:
            True if status is PROCESSED, FAILED, or EXPIRED.
        """
        return self in (
            SignalStatus.PROCESSED,
            SignalStatus.FAILED,
            SignalStatus.EXPIRED,
        )

    def can_process(self) -> bool:
        """Check if signal can be processed.

        Returns:
            True if status is PENDING.
        """
        return self == SignalStatus.PENDING
