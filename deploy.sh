#!/bin/bash

# ===========================================
# Whale Copy Trading Bot - Deployment Script
# ===========================================
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh
# ===========================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║         🐋 Whale Copy Trading Bot - Deployment            ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Installing Docker...${NC}"
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo -e "${GREEN}Docker installed. Please log out and back in, then run this script again.${NC}"
    exit 0
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}Installing Docker Compose...${NC}"
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file from template...${NC}"
    cp .env.example .env
fi

# Check for required Python packages
if ! python3 -c "from cryptography.fernet import Fernet" 2>/dev/null; then
    echo -e "${YELLOW}Installing cryptography for key generation...${NC}"
    pip3 install cryptography
fi

# Generate secrets if they are empty
echo -e "${CYAN}Checking/generating secrets...${NC}"

# Function to check if a value is set in .env
check_and_set() {
    local key=$1
    local value

    current=$(grep "^${key}=" .env | cut -d'=' -f2)

    if [ -z "$current" ]; then
        case $key in
            "SECRET_KEY")
                value=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
                ;;
            "DB_PASSWORD"|"REDIS_PASSWORD")
                value=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
                ;;
            "ENCRYPTION_KEY")
                value=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
                ;;
            "FLOWER_PASSWORD")
                value=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
                ;;
        esac

        if [ -n "$value" ]; then
            # Use | as delimiter to avoid issues with special chars
            sed -i "s|^${key}=.*|${key}=${value}|" .env
            echo -e "  ${GREEN}✓${NC} Generated ${key}"
        fi
    else
        echo -e "  ${GREEN}✓${NC} ${key} already set"
    fi
}

check_and_set "SECRET_KEY"
check_and_set "DB_PASSWORD"
check_and_set "REDIS_PASSWORD"
check_and_set "ENCRYPTION_KEY"
check_and_set "FLOWER_PASSWORD"

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Please ensure these values are set in your .env file:${NC}"
echo ""
echo "  TELEGRAM_BOT_TOKEN     - From @BotFather"
echo "  TELEGRAM_WEBHOOK_URL   - https://your-domain.com"
echo "  TELEGRAM_WEBAPP_URL    - https://your-domain.com"
echo ""
echo "  ETH_RPC_URL           - From Alchemy/Infura"
echo "  ETH_RPC_WS_URL        - WebSocket URL"
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Ask if user wants to continue
read -p "Have you configured the .env file? (y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo -e "${YELLOW}Please edit .env file and run this script again.${NC}"
    echo "nano .env"
    exit 0
fi

# Update domain in Caddyfile if needed
read -p "Enter your domain (e.g., bot.example.com) or press Enter to skip: " domain
if [ -n "$domain" ]; then
    echo -e "${CYAN}Updating Caddyfile for domain: ${domain}${NC}"
    sed -i "s|snippetly.codes|${domain}|g" Caddyfile
    sed -i "s|www.snippetly.codes|www.${domain}|g" Caddyfile

    # Update webhook URL in .env
    sed -i "s|^TELEGRAM_WEBHOOK_URL=.*|TELEGRAM_WEBHOOK_URL=https://${domain}|" .env
    sed -i "s|^TELEGRAM_WEBAPP_URL=.*|TELEGRAM_WEBAPP_URL=https://${domain}|" .env
fi

# Build and start containers
echo ""
echo -e "${CYAN}Building Docker images...${NC}"
docker-compose build

echo ""
echo -e "${CYAN}Starting services...${NC}"
docker-compose up -d

# Wait for services to be healthy
echo -e "${CYAN}Waiting for services to start...${NC}"
sleep 10

# Check status
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}                    DEPLOYMENT COMPLETE!                    ${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
docker-compose ps
echo ""
echo -e "${CYAN}Useful commands:${NC}"
echo "  docker-compose logs -f           # View all logs"
echo "  docker-compose logs -f backend   # View backend logs"
echo "  docker-compose ps                # Check status"
echo "  docker-compose restart           # Restart services"
echo ""
if [ -n "$domain" ]; then
    echo -e "${GREEN}Your bot should be accessible at:${NC}"
    echo "  Mini App:    https://${domain}"
    echo "  Webhook:     https://${domain}/webhook/telegram"
    echo "  API Health:  https://${domain}/health"
fi
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Wait 2-3 minutes for SSL certificate"
echo "  2. Set Telegram webhook: curl -X POST 'https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook?url=https://${domain:-your-domain}/webhook/telegram'"
echo "  3. Open your bot in Telegram and send /start"
echo ""
