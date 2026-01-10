"""Exceptions для Trading bounded context."""

from app.domain.shared import DomainException


class InsufficientBalanceError(DomainException):
    """Raised коли у користувача недостатньо балансу для trade."""

    pass


class InvalidTradeStateError(DomainException):
    """Raised при спробі виконати операцію в невалідному стані trade."""

    pass


class InvalidTradeSizeError(DomainException):
    """Raised коли розмір trade менший за minimum або більший за maximum."""

    pass


class PositionNotFoundError(DomainException):
    """Raised коли позиція не знайдена."""

    pass


class PositionAlreadyClosedError(DomainException):
    """Raised при спробі закрити вже закриту позицію."""

    pass
