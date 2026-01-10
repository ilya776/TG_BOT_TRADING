"""FastAPI application - Copy Trading Backend v2.

Clean Architecture implementation з:
- Domain-Driven Design
- CQRS pattern
- Event-Driven Architecture
- Hexagonal Architecture

Production-ready with:
- Configuration from environment variables
- Health check endpoints (liveness/readiness)
- Structured logging
- CORS configuration
"""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings, setup_logging, get_logger, bind_request_context, clear_request_context
from app.infrastructure.exchanges.factories import ExchangeFactory
from app.infrastructure.persistence.sqlalchemy import Base
from app.presentation.api import dependencies
from app.presentation.api.v1.routes import (
    auth_router,
    balance_router,
    signals_router,
    trades_router,
    trading_router,
    users_router,
    whales_router,
)

# Load settings
settings = get_settings()

# Configure structured logging
setup_logging()
logger = get_logger(__name__)


# ============================================================================
# LIFESPAN EVENTS (startup/shutdown)
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager для FastAPI.

    Startup:
    - Create database engine + session factory
    - Initialize dependencies (UnitOfWork, ExchangeFactory)
    - Create database tables (якщо потрібно)

    Shutdown:
    - Close database connections
    - Cleanup resources
    """
    logger.info("application.startup.started")

    # ===== STARTUP =====
    # Database setup
    engine = create_async_engine(
        settings.database_url,
        echo=settings.db_echo,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
        pool_pre_ping=True,
    )

    # Create tables (for development - в production використовуємо Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("application.database.tables_created")

    # Create session factory
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,  # Важливо для async
    )

    # Exchange factory setup
    exchange_factory = ExchangeFactory()

    # Initialize dependencies
    dependencies.init_dependencies(
        session_factory=session_factory,
        exchange_factory=exchange_factory,
    )

    logger.info("application.startup.completed")

    yield  # Application running

    # ===== SHUTDOWN =====
    logger.info("application.shutdown.started")

    # Close database connections
    await engine.dispose()

    logger.info("application.shutdown.completed")


# ============================================================================
# CREATE FASTAPI APPLICATION
# ============================================================================


app = FastAPI(
    title=settings.app_name,
    description="""
    **Clean Architecture** implementation для автоматичного копіювання трейдів з бірж.

    ## Features
    - Execute copy trades з 2-phase commit (crash-safe)
    - Position management (open/close)
    - Auto-retry + Circuit Breaker для exchange APIs
    - Event-Driven Architecture (domain events)
    - Clean Architecture (Domain → Application → Infrastructure → Presentation)

    ## Architecture
    - **Domain Layer**: Pure business logic (Trade, Position aggregates)
    - **Application Layer**: Use cases (ExecuteCopyTrade, ClosePosition handlers)
    - **Infrastructure Layer**: SQLAlchemy, Exchange adapters, Event Bus
    - **Presentation Layer**: FastAPI REST API
    """,
    version="2.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)

# ============================================================================
# MIDDLEWARE
# ============================================================================


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware to add request correlation ID to all log messages."""

    async def dispatch(self, request: Request, call_next):
        """Process request with correlation context."""
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Bind request context for structured logging
        bind_request_context(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            clear_request_context()


# Add middlewares (order matters - last added is executed first)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# ERROR HANDLERS
# ============================================================================


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors.

    Args:
        request: FastAPI request.
        exc: RequestValidationError з Pydantic.

    Returns:
        JSONResponse з 422 status code + error details.
    """
    logger.warning(
        "api.validation_error",
        path=request.url.path,
        errors=exc.errors(),
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "message": "Request validation failed",
            "details": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Handle unexpected exceptions.

    Args:
        request: FastAPI request.
        exc: Any unexpected exception.

    Returns:
        JSONResponse з 500 status code.
    """
    logger.exception(
        "api.unhandled_exception",
        path=request.url.path,
        error=str(exc),
        error_type=type(exc).__name__,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred. Please try again later.",
        },
    )


# ============================================================================
# ROUTES
# ============================================================================


# Health check - basic liveness
@app.get(
    "/health",
    tags=["Health"],
    summary="Health check (liveness)",
    description="Check if API is running",
)
async def health_check() -> dict:
    """Health check endpoint for liveness probes.

    Returns:
        Basic health status.
    """
    return {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": settings.environment,
    }


# Health check - readiness (with dependency checks)
@app.get(
    "/health/ready",
    tags=["Health"],
    summary="Readiness check",
    description="Check if API and all dependencies are ready",
)
async def readiness_check() -> JSONResponse:
    """Readiness check endpoint for Kubernetes probes.

    Checks:
    - Database connectivity
    - Redis connectivity

    Returns:
        Detailed health status with dependency checks.
    """
    from sqlalchemy import text

    checks = {"database": "unknown", "redis": "unknown"}
    all_healthy = True

    # Check database
    try:
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "healthy"
        await engine.dispose()
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)[:50]}"
        all_healthy = False

    # Check Redis
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        checks["redis"] = "healthy"
        await r.aclose()
    except Exception as e:
        checks["redis"] = f"unhealthy: {str(e)[:50]}"
        all_healthy = False

    response_status = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=response_status,
        content={
            "status": "healthy" if all_healthy else "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": checks,
        },
    )


# Liveness probe
@app.get(
    "/health/live",
    tags=["Health"],
    summary="Liveness probe",
    description="Simple check that application is running",
)
async def liveness_check() -> dict:
    """Liveness probe for Kubernetes.

    Returns:
        Simple alive status.
    """
    return {"status": "alive"}


# Include routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(whales_router, prefix="/api/v1")
app.include_router(signals_router, prefix="/api/v1")
app.include_router(balance_router, prefix="/api/v1")
app.include_router(trades_router, prefix="/api/v1")
app.include_router(trading_router, prefix="/api/v1")


# ============================================================================
# ROOT ENDPOINT
# ============================================================================


@app.get(
    "/",
    tags=["Root"],
    summary="API root",
    description="Welcome message + links to docs",
)
async def root() -> dict:
    """Root endpoint.

    Returns:
        Welcome message + links.
    """
    return {
        "message": "Copy Trading Backend v2 - Clean Architecture",
        "version": "2.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": "/openapi.json",
        "health": "/health",
    }


# ============================================================================
# RUN APPLICATION (for development)
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    # Run with: python -m app.main
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level="info",
    )
