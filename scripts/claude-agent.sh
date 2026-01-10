#!/bin/bash

# ═══════════════════════════════════════════════════════════════
# 🤖 CLAUDE AUTONOMOUS AGENT
# Runs every hour to fix bugs and improve the codebase
# ═══════════════════════════════════════════════════════════════

set -e

# Set PATH and environment for cron
export PATH="/Users/illabilous/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export HOME="/Users/illabilous"
export CLAUDE_CONFIG_DIR="/Users/illabilous/.claude"

# Authentication token for non-interactive use
export ANTHROPIC_AUTH_TOKEN="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"

# Claude CLI path
CLAUDE_BIN="/Users/illabilous/.local/bin/claude"

# Verify Claude exists
if [ ! -x "$CLAUDE_BIN" ]; then
    echo "❌ ERROR: Claude CLI not found at $CLAUDE_BIN"
    exit 1
fi

# Configuration
PROJECT_DIR="/Users/illabilous/IdeaProjects/TG_BOT_TRADING"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
LOGS_DIR="$SCRIPTS_DIR/logs"
GUIDELINES_FILE="$SCRIPTS_DIR/claude-guidelines.md"
SERVER="ubuntu@34.147.107.174"
REMOTE_PATH="/home/ubuntu/TG_BOT_TRADING"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_FILE="$LOGS_DIR/report-$TIMESTAMP.txt"

# Ensure logs directory exists
mkdir -p "$LOGS_DIR"

# Start logging
exec > >(tee -a "$LOGS_DIR/agent-$TIMESTAMP.log") 2>&1

echo "═══════════════════════════════════════════════════════════════"
echo "🤖 CLAUDE AGENT STARTED - $TIMESTAMP"
echo "═══════════════════════════════════════════════════════════════"

# Step 1: Navigate to project
cd "$PROJECT_DIR"
echo "📁 Working directory: $(pwd)"

# Step 2: Switch to develop branch and pull latest
echo ""
echo "🔄 Switching to develop branch..."
git checkout develop 2>/dev/null || git checkout -b develop
git pull origin develop 2>/dev/null || echo "⚠️ Could not pull from origin"

# Step 3: Collect logs from server
echo ""
echo "📊 Collecting logs from server..."
mkdir -p /tmp/whale_logs

ssh -o ConnectTimeout=10 "$SERVER" "docker logs whale_backend --since 1h 2>&1" > /tmp/whale_logs/backend.txt 2>/dev/null || echo "No backend logs"
ssh -o ConnectTimeout=10 "$SERVER" "docker logs whale_celery_worker --since 1h 2>&1" > /tmp/whale_logs/celery.txt 2>/dev/null || echo "No celery logs"
ssh -o ConnectTimeout=10 "$SERVER" "docker logs whale_frontend --since 1h 2>&1" > /tmp/whale_logs/frontend.txt 2>/dev/null || echo "No frontend logs"
ssh -o ConnectTimeout=10 "$SERVER" "docker logs whale_caddy --since 1h 2>&1" > /tmp/whale_logs/caddy.txt 2>/dev/null || echo "No caddy logs"

echo "✅ Logs collected"

# Step 4: Build the prompt for Claude
PROMPT=$(cat <<'PROMPT_END'
You are an autonomous AI agent for the Whale Copy Trading platform.
Your PRIMARY MISSION is monitoring and improving the trading flow.

## 🎯 EXECUTE THIS WORKFLOW IN ORDER:

### PHASE 1: EXPLORE LOGIC (15-20 min)
Read and understand the trading flow BEFORE making changes:

1. **Signal Parsing Flow**
   - Read: backend/app/services/trader_signals.py
   - Read: backend/app/workers/tasks/whale_tasks.py
   - Understand: How whales are polled, how signals are generated

2. **Auto Trade Flow**
   - Read: backend/app/services/copy_trade_engine.py
   - Read: backend/app/services/risk_manager.py
   - Read: backend/app/workers/tasks/trade_tasks.py
   - Understand: How trades are executed, 2-phase commit

3. **Auto Close Flow**
   - Read: backend/app/workers/tasks/trade_tasks.py (monitor_positions)
   - Understand: SL/TP triggers, whale exit auto-close

4. **Telegram Notifications**
   - Read: backend/app/workers/tasks/notification_tasks.py
   - Read: backend/app/telegram/handlers/
   - Understand: What notifications are sent and when

### PHASE 2: ANALYZE LOGS (10 min)
Read collected server logs:
- /tmp/whale_logs/backend.txt (API errors)
- /tmp/whale_logs/celery.txt (task execution, trade errors) <- MOST IMPORTANT
- /tmp/whale_logs/frontend.txt
- /tmp/whale_logs/caddy.txt

Find: Exceptions, Errors, Failed trades, Skipped signals, Timeouts

### PHASE 3: FIX & IMPROVE (20-30 min)
Priority order:
1. Critical trading flow bugs (signals, trades, closes, notifications)
2. Error handling & resilience (retry logic, circuit breakers)
3. Architecture improvements (type hints, logging, code quality)
4. UI/UX improvements (use frontend-design skill for beautiful UI)

### PHASE 4: DEPLOY (5 min)
1. git add . && git commit -m "🤖 Auto: [changes]" && git push origin develop
2. rsync to ubuntu@34.147.107.174:/home/ubuntu/TG_BOT_TRADING/
3. ssh rebuild: docker-compose up -d --build
4. Verify containers running

### PHASE 5: VERIFY MONITORING (5 min)
After deploy, check:
- Signals being generated?
- Trades executing?
- Positions monitored?
- Notifications sending?

## 📋 GUIDELINES
Read FULL guidelines: /Users/illabilous/IdeaProjects/TG_BOT_TRADING/scripts/claude-guidelines.md

## 📝 REPORT
Write detailed report to: /Users/illabilous/IdeaProjects/TG_BOT_TRADING/scripts/logs/report-TIMESTAMP.txt
Include: Trading flow status, bugs fixed, improvements, deploy status, verification results

## RULES
- Only modify develop branch
- Commit with Auto: prefix
- Do NOT break working code
- Verify after deploy

## 🚀 START NOW
First, read the guidelines file completely. Then follow the 5-phase workflow.
Be thorough - you are Opus, the smartest model. Make meaningful improvements!
PROMPT_END
)

# Step 5: Run Claude Code
echo ""
echo "🚀 Starting Claude Code session..."
echo "─────────────────────────────────────────────────────────────"

# Run Claude Code with the prompt
# Pipe prompt to stdin (simulates manual input)

echo "$PROMPT" | "$CLAUDE_BIN" --model opus

CLAUDE_EXIT_CODE=$?

echo "─────────────────────────────────────────────────────────────"
echo "Claude Code session ended with exit code: $CLAUDE_EXIT_CODE"

# Step 6: Final status
echo ""
echo "═══════════════════════════════════════════════════════════════"
if [ $CLAUDE_EXIT_CODE -eq 0 ]; then
    echo "✅ AGENT COMPLETED SUCCESSFULLY"
else
    echo "⚠️ AGENT COMPLETED WITH WARNINGS (exit code: $CLAUDE_EXIT_CODE)"
fi
echo "📄 Check report at: $REPORT_FILE"
echo "📋 Full log at: $LOGS_DIR/agent-$TIMESTAMP.log"
echo "═══════════════════════════════════════════════════════════════"
