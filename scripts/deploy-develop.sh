#!/bin/bash

# ═══════════════════════════════════════════════════════════════
# 🚀 DEPLOY TO DEVELOP SERVER
# Syncs code and rebuilds containers
# ═══════════════════════════════════════════════════════════════

set -e

# Configuration
PROJECT_DIR="/Users/illabilous/IdeaProjects/TG_BOT_TRADING"
SERVER="ubuntu@34.147.107.174"
REMOTE_PATH="/home/ubuntu/TG_BOT_TRADING"

echo "🚀 Starting deployment to develop server..."
echo "─────────────────────────────────────────────────────────────"

# Step 1: Sync files
echo "📦 Syncing files to server..."
rsync -avz --progress \
  --exclude 'node_modules' \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude 'venv' \
  --exclude '.env.local' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  --exclude 'scripts/logs/*' \
  "$PROJECT_DIR/" \
  "$SERVER:$REMOTE_PATH/"

echo "✅ Files synced"

# Step 2: Build and restart containers
echo ""
echo "🐳 Rebuilding Docker containers..."
ssh "$SERVER" "cd $REMOTE_PATH && docker-compose down && docker-compose up -d --build"

echo "✅ Containers rebuilt"

# Step 3: Wait for startup
echo ""
echo "⏳ Waiting for services to start (30s)..."
sleep 30

# Step 4: Health check
echo ""
echo "🔍 Running health check..."
echo ""

# Check container status
echo "Container status:"
ssh "$SERVER" "docker ps --format 'table {{.Names}}\t{{.Status}}' | grep whale"

# Check for immediate errors
echo ""
echo "Recent backend logs:"
ssh "$SERVER" "docker logs whale_backend --since 1m 2>&1 | tail -20"

# Step 5: Done
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "✅ DEPLOYMENT COMPLETE"
echo "═══════════════════════════════════════════════════════════════"
