"""Signal domain exceptions."""

from app.domain.shared import DomainException


class SignalError(DomainException):
    """Base exception для signal errors."""

    pass


class SignalNotFoundError(SignalError):
    """Signal not found."""

    def __init__(self, signal_id: int) -> None:
        """Initialize exception.

        Args:
            signal_id: Signal ID that was not found.
        """
        super().__init__(f"Signal {signal_id} not found")
        self.signal_id = signal_id


class SignalExpiredError(SignalError):
    """Signal has expired and cannot be processed."""

    def __init__(self, signal_id: int, age_seconds: float) -> None:
        """Initialize exception.

        Args:
            signal_id: Signal ID.
            age_seconds: Signal age in seconds.
        """
        super().__init__(
            f"Signal {signal_id} expired (age: {age_seconds:.1f}s)"
        )
        self.signal_id = signal_id
        self.age_seconds = age_seconds


class InvalidSignalStatusError(SignalError):
    """Invalid signal status transition."""

    def __init__(self, signal_id: int, current_status: str, target_status: str) -> None:
        """Initialize exception.

        Args:
            signal_id: Signal ID.
            current_status: Current signal status.
            target_status: Target status (invalid transition).
        """
        super().__init__(
            f"Signal {signal_id} cannot transition from {current_status} to {target_status}"
        )
        self.signal_id = signal_id
        self.current_status = current_status
        self.target_status = target_status
