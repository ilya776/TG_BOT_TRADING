"""Base Entity class for domain model.

Entity - об'єкт з унікальною ідентичністю, який відрізняється від інших
не атрибутами, а ID. Два entity з однаковими атрибутами але різними ID -
це різні об'єкти.
"""

from abc import ABC
from typing import Any


class Entity(ABC):
    """Base class for all domain entities.

    Entity має унікальний ідентифікатор (id) і порівнюється за ID, а не за значенням атрибутів.

    Example:
        >>> user1 = User(id=1, name="John")
        >>> user2 = User(id=1, name="Jane")
        >>> user1 == user2  # True (same ID)

        >>> user3 = User(id=2, name="John")
        >>> user1 == user3  # False (different ID)
    """

    def __init__(self, id: int | None = None) -> None:
        """Initialize entity with optional ID.

        Args:
            id: Unique identifier. None для нових entities (ще не збережені в DB).
        """
        self._id = id

    @property
    def id(self) -> int | None:
        """Get entity ID."""
        return self._id

    def __eq__(self, other: object) -> bool:
        """Entities порівнюються за ID, не за атрибутами.

        Args:
            other: Object to compare with.

        Returns:
            True if same ID (or both None), False otherwise.
        """
        if not isinstance(other, Entity):
            return False

        # Якщо обидва ID None (нові entities), вони не рівні
        if self._id is None and other._id is None:
            return self is other

        return self._id == other._id

    def __hash__(self) -> int:
        """Hash based on ID for use in sets/dicts.

        Returns:
            Hash of ID or object id if ID is None.
        """
        if self._id is None:
            return hash(id(self))  # Fallback to object id
        return hash(self._id)

    def __repr__(self) -> str:
        """String representation for debugging.

        Returns:
            String like "User(id=1)" or "User(id=None)".
        """
        return f"{self.__class__.__name__}(id={self._id})"
