# ===========================================
# WHALE COPY TRADING - Makefile
# ===========================================
# Usage:
#   make setup     - First time setup
#   make up        - Start all services
#   make down      - Stop all services
#   make logs      - View logs
#   make restart   - Restart all services
# ===========================================

.PHONY: help setup up down restart logs build clean secrets dev

# Default target
help:
	@echo "╔═══════════════════════════════════════════════════════════╗"
	@echo "║         🐋 Whale Copy Trading Bot - Commands              ║"
	@echo "╠═══════════════════════════════════════════════════════════╣"
	@echo "║  make setup      - First time setup (generate secrets)   ║"
	@echo "║  make up         - Start all services                    ║"
	@echo "║  make down       - Stop all services                     ║"
	@echo "║  make restart    - Restart all services                  ║"
	@echo "║  make logs       - View all logs                         ║"
	@echo "║  make logs-f     - Follow all logs                       ║"
	@echo "║  make build      - Rebuild all images                    ║"
	@echo "║  make clean      - Remove all containers and volumes     ║"
	@echo "║  make dev        - Start in development mode             ║"
	@echo "║  make monitoring - Start with Flower monitoring          ║"
	@echo "║  make secrets    - Generate new secrets                  ║"
	@echo "║  make status     - Show container status                 ║"
	@echo "║  make shell-api  - Open shell in backend container       ║"
	@echo "║  make shell-db   - Open PostgreSQL shell                 ║"
	@echo "╚═══════════════════════════════════════════════════════════╝"

# First time setup
setup:
	@echo "🐋 Setting up Whale Copy Trading Bot..."
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✅ Created .env from .env.example"; \
	fi
	@echo ""
	@echo "🔐 Generating secrets..."
	@make secrets
	@echo ""
	@echo "📝 Next steps:"
	@echo "   1. Edit .env file and fill in your API keys"
	@echo "   2. Get Telegram Bot token from @BotFather"
	@echo "   3. Get Exchange API keys (Binance/OKX/Bybit)"
	@echo "   4. Get Alchemy API key for blockchain RPC"
	@echo "   5. Run: make up"

# Generate secrets and update .env
secrets:
	@echo "Generating SECRET_KEY..."
	@SECRET=$$(python3 -c "import secrets; print(secrets.token_urlsafe(64))") && \
		sed -i.bak "s|^SECRET_KEY=.*|SECRET_KEY=$$SECRET|" .env
	@echo "Generating DB_PASSWORD..."
	@DBPASS=$$(python3 -c "import secrets; print(secrets.token_urlsafe(32))") && \
		sed -i.bak "s|^DB_PASSWORD=.*|DB_PASSWORD=$$DBPASS|" .env
	@echo "Generating REDIS_PASSWORD..."
	@REDISPASS=$$(python3 -c "import secrets; print(secrets.token_urlsafe(32))") && \
		sed -i.bak "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=$$REDISPASS|" .env
	@echo "Generating ENCRYPTION_KEY..."
	@ENCKEY=$$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") && \
		sed -i.bak "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$$ENCKEY|" .env
	@echo "Generating FLOWER_PASSWORD..."
	@FLOWERPASS=$$(python3 -c "import secrets; print(secrets.token_urlsafe(16))") && \
		sed -i.bak "s|^FLOWER_PASSWORD=.*|FLOWER_PASSWORD=$$FLOWERPASS|" .env
	@rm -f .env.bak
	@echo "✅ All secrets generated!"

# Build images
build:
	@echo "🔨 Building Docker images..."
	docker-compose build --no-cache

# Start all services
up:
	@echo "🚀 Starting Whale Copy Trading Bot..."
	docker-compose up -d
	@echo ""
	@echo "✅ Services started!"
	@echo "   Frontend: http://localhost"
	@echo "   API Docs: http://localhost/api/docs (if DEBUG=true)"
	@make status

# Start with monitoring (Flower)
monitoring:
	@echo "🚀 Starting with monitoring..."
	docker-compose --profile monitoring up -d
	@echo ""
	@echo "   Flower: http://localhost:5555"

# Stop all services
down:
	@echo "🛑 Stopping services..."
	docker-compose down

# Restart all services
restart:
	@echo "🔄 Restarting services..."
	docker-compose restart

# View logs
logs:
	docker-compose logs

logs-f:
	docker-compose logs -f

logs-backend:
	docker-compose logs -f backend

logs-whale:
	docker-compose logs -f whale_monitor

logs-celery:
	docker-compose logs -f celery_worker celery_beat

# Show status
status:
	@echo ""
	@echo "📊 Container Status:"
	@docker-compose ps

# Development mode
dev:
	@echo "🔧 Starting in development mode..."
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
	@echo ""
	@echo "   Frontend: http://localhost:5173"
	@echo "   Backend:  http://localhost:8000"
	@echo "   API Docs: http://localhost:8000/docs"

# Clean up everything
clean:
	@echo "🧹 Cleaning up..."
	docker-compose down -v --remove-orphans
	docker system prune -f
	@echo "✅ Cleanup complete!"

# Shell access
shell-api:
	docker-compose exec backend bash

shell-db:
	docker-compose exec postgres psql -U postgres -d whale_copy_trading

shell-redis:
	docker-compose exec redis redis-cli -a $${REDIS_PASSWORD}

# Database operations
db-migrate:
	docker-compose exec backend alembic upgrade head

db-rollback:
	docker-compose exec backend alembic downgrade -1

db-reset:
	@echo "⚠️  This will DELETE all data! Press Ctrl+C to cancel..."
	@sleep 5
	docker-compose down -v
	docker-compose up -d postgres redis
	@sleep 5
	docker-compose up -d

# Health check
health:
	@echo "🏥 Health Check:"
	@curl -s http://localhost/health | python3 -m json.tool || echo "❌ Frontend/API not responding"
	@echo ""
	@docker-compose ps --format "table {{.Name}}\t{{.Status}}"
