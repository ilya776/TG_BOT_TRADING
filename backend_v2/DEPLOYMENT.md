# Production Deployment Guide

Copy Trading Backend v2 - Clean Architecture implementation.

## Prerequisites

- Docker & Docker Compose v2.0+
- PostgreSQL 15+ (or use Docker)
- Redis 7+ (or use Docker)
- Python 3.11+ (for local development)

## Quick Start (Docker)

### 1. Clone and configure

```bash
cd backend_v2
cp .env.example .env
# Edit .env with your values
```

### 2. Generate secrets

```bash
# Generate SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate POSTGRES_PASSWORD
python -c "import secrets; print(secrets.token_urlsafe(16))"
```

### 3. Start services

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Check health
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│   API Server    │────▶│   PostgreSQL    │
│  (FastAPI)      │     │   (Database)    │
│  :8000          │     │   :5432         │
└────────┬────────┘     └─────────────────┘
         │
         │              ┌─────────────────┐
         └─────────────▶│     Redis       │
                        │  (Broker/Cache) │
┌─────────────────┐     │   :6379         │
│ Celery Worker   │────▶└─────────────────┘
│ (Background)    │
└─────────────────┘
         │
         │
┌────────▼────────┐     ┌─────────────────┐
│  Celery Beat    │     │    Flower       │
│  (Scheduler)    │     │  (Monitoring)   │
└─────────────────┘     │   :5555         │
                        └─────────────────┘
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| api | 8000 | FastAPI REST API |
| celery-worker | - | Background task processor |
| celery-beat | - | Periodic task scheduler |
| db | 5432 | PostgreSQL database |
| redis | 6379 | Redis broker/cache |
| flower | 5555 | Celery monitoring UI |

## Environment Configuration

### Required Variables

```bash
# Security (MUST change in production)
SECRET_KEY=<generated-secret>
POSTGRES_PASSWORD=<generated-password>
FLOWER_PASSWORD=<generated-password>

# Database
DATABASE_URL=postgresql+asyncpg://postgres:${POSTGRES_PASSWORD}@db:5432/trading

# Redis
REDIS_URL=redis://redis:6379/0
```

### Production Settings

```bash
ENVIRONMENT=production
DEBUG=false
LOG_FORMAT=json
LOG_LEVEL=INFO

# Tune based on load
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
CELERY_WORKER_CONCURRENCY=8
```

## Deployment Options

### Option 1: Docker Compose (recommended for small/medium scale)

```bash
# Production deployment
docker-compose -f docker-compose.yml up -d

# Scale workers
docker-compose up -d --scale celery-worker=4
```

### Option 2: Kubernetes

Create Kubernetes manifests from docker-compose:

```bash
# Convert to k8s (requires kompose)
kompose convert -f docker-compose.yml

# Or use Helm charts (create separately)
helm install trading ./helm/trading
```

### Option 3: Manual deployment

```bash
# Install dependencies
pip install poetry
poetry install --no-dev

# Run migrations
alembic upgrade head

# Start API
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Start Celery worker (separate terminal)
celery -A app.presentation.workers worker --loglevel=info --concurrency=4

# Start Celery beat (separate terminal)
celery -A app.presentation.workers beat --loglevel=info
```

## Health Checks

### Endpoints

| Endpoint | Purpose | Usage |
|----------|---------|-------|
| `/health` | Basic liveness | Load balancer |
| `/health/live` | Kubernetes liveness | k8s livenessProbe |
| `/health/ready` | Kubernetes readiness | k8s readinessProbe |

### Kubernetes Probes

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

## Monitoring

### Flower Dashboard

Access Celery monitoring at `http://localhost:5555`

```bash
# Login with credentials from .env
FLOWER_USER / FLOWER_PASSWORD
```

### Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f celery-worker

# Production JSON logs (parse with jq)
docker-compose logs api | jq .
```

### Metrics (add Prometheus)

```yaml
# Add to docker-compose.yml
prometheus:
  image: prom/prometheus
  ports:
    - "9090:9090"
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
```

## Database Management

### Migrations

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Backup

```bash
# Backup database
docker-compose exec db pg_dump -U postgres trading > backup.sql

# Restore
docker-compose exec -T db psql -U postgres trading < backup.sql
```

## Scaling

### Horizontal Scaling

```bash
# Scale Celery workers
docker-compose up -d --scale celery-worker=4

# Multiple API instances (behind load balancer)
docker-compose up -d --scale api=3
```

### Performance Tuning

```bash
# Increase connection pool
DB_POOL_SIZE=50
DB_MAX_OVERFLOW=100

# More Celery workers
CELERY_WORKER_CONCURRENCY=16

# Redis memory
redis-server --maxmemory 1gb --maxmemory-policy allkeys-lru
```

## Troubleshooting

### Common Issues

**API won't start**
```bash
# Check logs
docker-compose logs api

# Verify database connection
docker-compose exec api python -c "from app.config import get_settings; print(get_settings().database_url)"
```

**Celery tasks not running**
```bash
# Check worker status
docker-compose exec celery-worker celery -A app.presentation.workers inspect active

# Check beat schedule
docker-compose logs celery-beat
```

**Database connection errors**
```bash
# Test connection
docker-compose exec db psql -U postgres -c "SELECT 1"

# Check pool exhaustion (increase DB_POOL_SIZE)
docker-compose logs api | grep "pool"
```

### Debug Mode

```bash
# Enable debug logging
DEBUG=true
LOG_LEVEL=DEBUG
DB_ECHO=true

# Restart
docker-compose up -d
```

## Security Checklist

- [ ] Change all default passwords
- [ ] Set `DEBUG=false` in production
- [ ] Use HTTPS (configure reverse proxy)
- [ ] Set `CORS_ORIGINS` to your domains only
- [ ] Disable `/docs` and `/redoc` in production
- [ ] Use secrets management (Vault, AWS Secrets Manager)
- [ ] Enable database SSL (`?sslmode=require`)
- [ ] Regular security updates
