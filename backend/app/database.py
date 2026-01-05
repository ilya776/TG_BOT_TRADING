"""
Database Configuration and Session Management
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

# Create async engine with statement timeout
# statement_timeout: 30 seconds max for any query (prevents long-running queries)
engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args={
        "server_settings": {
            "statement_timeout": "30000",  # 30 seconds in milliseconds
            "lock_timeout": "10000",  # 10 seconds for lock acquisition
        }
    },
)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Sync engine for Celery tasks (convert async URL to sync)
sync_database_url = settings.database_url.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
).replace(
    "postgresql://", "postgresql+psycopg2://"
)

sync_engine = create_engine(
    sync_database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
    pool_size=15,  # Increased for Celery workers (was 5)
    max_overflow=15,  # Increased for peak load (was 10)
    pool_recycle=3600,  # Recycle connections every hour
    connect_args={
        "options": "-c statement_timeout=30000 -c lock_timeout=10000"
    },
)

# Sync session factory for Celery
sync_session_factory = sessionmaker(
    sync_engine,
    class_=Session,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database sessions.
    Use with FastAPI's Depends().
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for getting database sessions outside of FastAPI.
    Use for background tasks, workers, etc.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@contextmanager
def get_sync_db() -> Generator[Session, None, None]:
    """
    Sync context manager for getting database sessions in Celery tasks.
    Use for synchronous background workers.
    """
    session = sync_session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
