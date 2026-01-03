# Whale Copy Trading Bot - Deployment Guide

## Quick Start

### 1. Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for secret generation)
- Domain with SSL certificate (for Telegram webhook)

### 2. Initial Setup

```bash
# Clone repository
git clone <your-repo>
cd TG_BOT_TRADING

# Run setup (creates .env and generates secrets)
make setup
```

### 3. Configure Environment

Edit `.env` file:

```bash
nano .env
```

**Required Configuration:**

| Variable | Description | How to Get |
|----------|-------------|------------|
| `TELEGRAM_BOT_TOKEN` | Bot token | [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_WEBHOOK_URL` | `https://your-domain.com/webhook` | Your server |
| `TELEGRAM_WEBAPP_URL` | `https://your-domain.com` | Your server |
| `BINANCE_API_KEY/SECRET` | Exchange API | [Binance](https://www.binance.com/en/my/settings/api-management) |
| `ETH_RPC_URL` | Ethereum RPC | [Alchemy](https://www.alchemy.com/) |

### 4. Start Services

```bash
# Production mode
make up

# Check status
make status

# View logs
make logs-f
```

### 5. Verify Deployment

```bash
# Health check
curl http://localhost/health

# All services running
docker-compose ps
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        NGINX (Frontend)                      │
│                    Port 80/443 (external)                    │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
┌─────────────────────┐    ┌─────────────────────┐
│   FastAPI Backend   │    │   Whale Monitor     │
│     (Port 8000)     │    │   (Blockchain)      │
└──────────┬──────────┘    └──────────┬──────────┘
           │                          │
           └────────────┬─────────────┘
                        │
              ┌─────────┴─────────┐
              │                   │
              ▼                   ▼
     ┌─────────────┐      ┌─────────────┐
     │  PostgreSQL │      │    Redis    │
     │   (Data)    │      │   (Cache)   │
     └─────────────┘      └─────────────┘
```

---

## Services

| Service | Container | Port | Description |
|---------|-----------|------|-------------|
| Frontend | `whale_frontend` | 80, 443 | Telegram Mini App (nginx) |
| Backend | `whale_backend` | 8000* | FastAPI REST API |
| Postgres | `whale_postgres` | 5432* | Database |
| Redis | `whale_redis` | 6379* | Cache & Message Broker |
| Celery Worker | `whale_celery_worker` | - | Background tasks |
| Celery Beat | `whale_celery_beat` | - | Scheduled tasks |
| Whale Monitor | `whale_monitor` | - | Blockchain listener |
| Flower | `whale_flower` | 5555* | Celery monitoring |

*Internal ports, not exposed externally in production

---

## Commands Reference

```bash
# Start/Stop
make up              # Start all services
make down            # Stop all services
make restart         # Restart all services

# Logs
make logs            # View all logs
make logs-f          # Follow logs (live)
make logs-backend    # Backend logs only
make logs-whale      # Whale monitor logs
make logs-celery     # Celery worker logs

# Development
make dev             # Development mode with hot reload
make monitoring      # Start with Flower UI

# Database
make db-migrate      # Run migrations
make db-rollback     # Rollback last migration
make shell-db        # PostgreSQL shell

# Maintenance
make build           # Rebuild images
make clean           # Remove all containers and volumes
make health          # Health check
make status          # Container status
```

---

## SSL Setup (Production)

### Option 1: Caddy (Recommended)

Create `docker-compose.override.yml`:

```yaml
services:
  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
    depends_on:
      - frontend

volumes:
  caddy_data:
```

Create `Caddyfile`:

```
your-domain.com {
    reverse_proxy frontend:80
}
```

### Option 2: Nginx + Certbot

```bash
# Install certbot
apt install certbot python3-certbot-nginx

# Get certificate
certbot --nginx -d your-domain.com
```

---

## Telegram Bot Setup

1. **Create Bot:**
   - Message [@BotFather](https://t.me/BotFather)
   - `/newbot` - follow instructions
   - Copy token to `TELEGRAM_BOT_TOKEN`

2. **Set Webhook:**
   ```bash
   curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
     -d "url=https://your-domain.com/webhook"
   ```

3. **Configure Mini App:**
   - Message @BotFather
   - `/mybots` → Select your bot
   - `Bot Settings` → `Menu Button`
   - Set URL: `https://your-domain.com`

---

## Security Checklist

- [ ] All secrets generated (`make setup`)
- [ ] `.env` file NOT committed to git
- [ ] Exchange API keys have NO withdrawal permission
- [ ] Exchange API keys have IP whitelist set
- [ ] SSL certificate configured
- [ ] Flower UI password changed
- [ ] PostgreSQL/Redis ports NOT exposed externally
- [ ] Firewall configured (only 80/443 open)

---

## Troubleshooting

### Services won't start
```bash
# Check logs
docker-compose logs

# Rebuild
make build
make up
```

### Database connection error
```bash
# Wait for postgres to be ready
docker-compose up -d postgres
sleep 10
docker-compose up -d
```

### Webhook not working
```bash
# Check webhook status
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"

# Re-register webhook
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://your-domain.com/webhook"
```

### Reset everything
```bash
make clean
make setup
# Edit .env
make up
```

---

## Monitoring

### Flower (Celery Dashboard)
```bash
make monitoring
# Open http://localhost:5555
# Login: admin / <FLOWER_PASSWORD from .env>
```

### Logs
```bash
# All services
make logs-f

# Specific service
docker-compose logs -f backend
docker-compose logs -f whale_monitor
```

### Health Check
```bash
make health
```

---

## Backup & Restore

### Backup Database
```bash
docker-compose exec postgres pg_dump -U postgres whale_copy_trading > backup.sql
```

### Restore Database
```bash
docker-compose exec -T postgres psql -U postgres whale_copy_trading < backup.sql
```

---

## Support

- Issues: [GitHub Issues](https://github.com/your-repo/issues)
- Telegram: [@YourSupportBot](https://t.me/YourSupportBot)
