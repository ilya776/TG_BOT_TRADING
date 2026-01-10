"""Pytest fixtures for SQLAlchemy integration tests."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.persistence.sqlalchemy import Base


@pytest.fixture
async def engine():
    """Create async SQLite engine for testing.

    Returns:
        Async SQLAlchemy engine.
    """
    # In-memory SQLite database для швидких tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,  # Set to True для debug
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    await engine.dispose()


@pytest.fixture
async def session_factory(engine):
    """Create async session factory.

    Args:
        engine: SQLAlchemy async engine.

    Returns:
        Async session factory.
    """
    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,  # Важливо для testing
    )

    return factory


@pytest.fixture
async def session(session_factory):
    """Create async session for testing.

    Args:
        session_factory: Async session factory.

    Returns:
        AsyncSession instance.

    Note:
        Автоматично rollback після кожного тесту.
    """
    async with session_factory() as session:
        yield session
        await session.rollback()  # Cleanup
