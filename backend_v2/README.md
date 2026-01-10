# Copy Trading Backend v2 - Clean Architecture

Enterprise-level rewrite of the copy trading backend using Clean Architecture and Domain-Driven Design principles.

## Architecture

```
┌─────────────────────────────────────────────┐
│         PRESENTATION LAYER                  │
│    (FastAPI Routes, Celery Workers)         │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│         APPLICATION LAYER                   │
│  (Use Cases, Commands, Queries, Handlers)   │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│           DOMAIN LAYER                      │
│    (Pure Business Logic, Zero Dependencies) │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│       INFRASTRUCTURE LAYER                  │
│  (Database, External APIs, Message Queue)   │
└─────────────────────────────────────────────┘
```

## Key Design Patterns

- **Domain-Driven Design**: Bounded Contexts (Trading, Signals, Exchanges, Users, Risk, Whales)
- **Repository Pattern**: Clean separation between domain and data access
- **Unit of Work**: Transaction management
- **Strategy Pattern**: Exchange executors
- **Factory Pattern**: Exchange creation
- **Domain Events**: Decoupled event handling
- **Circuit Breaker**: Exchange API protection
- **Retry with Exponential Backoff**: Resilient API calls

## Project Structure

```
backend_v2/
├── app/
│   ├── domain/              # Pure business logic (no dependencies)
│   ├── application/         # Use cases and orchestration
│   ├── infrastructure/      # External concerns (DB, APIs)
│   ├── presentation/        # API routes, workers
│   └── config/              # Configuration
└── tests/
    ├── unit/                # Domain logic tests
    ├── integration/         # Infrastructure tests
    └── e2e/                 # End-to-end tests
```

## Getting Started

### Prerequisites

- Python 3.11+
- Poetry
- PostgreSQL 14+
- Redis 7+

### Installation

```bash
cd backend_v2
poetry install
```

### Running Tests

```bash
# All tests
poetry run pytest

# Unit tests only
poetry run pytest -m unit

# Integration tests
poetry run pytest -m integration

# With coverage
poetry run pytest --cov=app --cov-report=html
```

### Development

```bash
# Format code
poetry run black app tests

# Lint
poetry run ruff check app tests

# Type checking
poetry run mypy app
```

## Migration Strategy

This project uses **Branch by Abstraction** for gradual migration from the legacy codebase:

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | ✅ Complete | Foundation - Domain layer, entities, value objects |
| Phase 2 | ✅ Complete | Exchange Integration - Adapters with retry/circuit breaker |
| Phase 3 | ✅ Complete | Trading Core - Trade/Position aggregates, handlers |
| Phase 4 | ✅ Complete | Signal Processing - Signal entity, SignalQueue |
| Phase 5 | ✅ Complete | Application Layer - Handlers, commands, DTOs |
| Phase 6 | ✅ Complete | Integration - Celery workers, Alembic, tests |

### Test Coverage

| Layer | Tests | Coverage |
|-------|-------|----------|
| Domain (Trading) | 60+ | ~95% |
| Domain (Signals) | 29 | ~95% |
| Infrastructure | 30+ | ~90% |
| E2E | 8+ | Key paths |
| **Total** | **127+** | **~90%** |

## Features

- ✅ Clean separation of concerns (Domain, Application, Infrastructure)
- ✅ Pure domain logic with zero external dependencies
- ✅ Comprehensive test coverage (unit, integration, e2e)
- ✅ Type-safe with mypy strict mode
- ✅ Async/await throughout
- ✅ Circuit breakers and retry logic for external APIs
- ✅ Event-driven architecture with domain events
- ✅ Optimistic locking for concurrent updates
- ✅ Structured logging and observability

## Documentation

See [/docs](/docs) for detailed architecture documentation.
