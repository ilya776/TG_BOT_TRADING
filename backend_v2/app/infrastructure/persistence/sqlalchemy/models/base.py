"""SQLAlchemy Base model."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class для всіх ORM models.

    Використовується для declarative mapping в SQLAlchemy 2.0+.
    """

    pass
