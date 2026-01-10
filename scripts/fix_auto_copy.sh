#!/bin/bash
# ============================================
# Fix Auto-Copy Not Executing Trades
# ============================================
# This script enables auto_copy for all user follows
# Run this on your GCP VM or wherever Docker is running
# ============================================

set -e

echo "=== Fixing Auto-Copy Issue ==="
echo ""

# Check if docker compose is available
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker not found. Make sure you're running this on the GCP VM."
    exit 1
fi

# Run the SQL fix script
echo "Running SQL fix script..."
docker compose exec -T postgres psql -U postgres -d trading_bot -f - < scripts/fix_auto_copy.sql

echo ""
echo "=== Restarting services ==="
docker compose restart celery backend

echo ""
echo "=== Checking logs ==="
echo "Watching for new trade executions (Ctrl+C to stop)..."
docker compose logs -f --tail=50 celery | grep -E "(Processing signal|Trade.*complete|copy trade)"
