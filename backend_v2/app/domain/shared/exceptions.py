"""Base domain exceptions.

Domain exceptions представляють порушення бізнес-правил.
Вони частина domain layer і не залежать від infrastructure.
"""

from typing import Any


class DomainException(Exception):
    """Base exception for all domain errors.

    Domain exceptions - це business rule violations, не technical errors.

    Example:
        >>> raise DomainException("User cannot execute trade: insufficient balance")
    """

    def __init__(self, message: str, **context: Any) -> None:
        """Initialize domain exception.

        Args:
            message: Human-readable error message.
            **context: Additional context (user_id, trade_id, etc).
        """
        super().__init__(message)
        self.message = message
        self.context = context

    def __str__(self) -> str:
        """String representation with context.

        Returns:
            Error message with context if available.
        """
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({context_str})"
        return self.message


class BusinessRuleViolation(DomainException):
    """Exception raised when business rule is violated.

    Example:
        >>> if trade.status != TradeStatus.PENDING:
        ...     raise BusinessRuleViolation(
        ...         "Cannot execute trade: invalid status",
        ...         trade_id=trade.id,
        ...         current_status=trade.status
        ...     )
    """

    pass


class AggregateNotFound(DomainException):
    """Exception raised when aggregate is not found.

    Example:
        >>> trade = await trade_repo.get_by_id(123)
        >>> if not trade:
        ...     raise AggregateNotFound(
        ...         "Trade not found",
        ...         trade_id=123
        ...     )
    """

    pass


class InvalidStateTransition(DomainException):
    """Exception raised for invalid state transitions.

    Example:
        >>> # Trade FAILED -> FILLED is invalid
        >>> if self.status == TradeStatus.FAILED:
        ...     raise InvalidStateTransition(
        ...         "Cannot transition from FAILED to FILLED",
        ...         from_status=TradeStatus.FAILED,
        ...         to_status=TradeStatus.FILLED
        ...     )
    """

    pass


class ConcurrencyException(DomainException):
    """Exception raised when optimistic locking fails.

    Example:
        >>> # Version mismatch during update
        >>> if trade.version != expected_version:
        ...     raise ConcurrencyException(
        ...         "Trade was modified by another transaction",
        ...         trade_id=trade.id,
        ...         expected_version=expected_version,
        ...         actual_version=trade.version
        ...     )
    """

    pass
