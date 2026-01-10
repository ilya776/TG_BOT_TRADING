#!/bin/bash

# ═══════════════════════════════════════════════════════════════
# 🚀 CLAUDE AGENT LAUNCHER
# Runs claude-agent.sh in Terminal.app with user session
# ═══════════════════════════════════════════════════════════════

SCRIPT_PATH="/Users/illabilous/IdeaProjects/TG_BOT_TRADING/scripts/claude-agent.sh"
LOG_DIR="/Users/illabilous/IdeaProjects/TG_BOT_TRADING/scripts/logs"

# Run in Terminal.app with full user environment
osascript <<EOF
tell application "Terminal"
    activate
    do script "cd /Users/illabilous/IdeaProjects/TG_BOT_TRADING && ./scripts/claude-agent.sh 2>&1 | tee -a $LOG_DIR/terminal-agent.log"
end tell
EOF

echo "$(date): Launched agent in Terminal.app" >> "$LOG_DIR/launcher.log"
