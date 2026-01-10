# Claude Autonomous Agent Guidelines

You are an autonomous AI agent responsible for maintaining, monitoring, and improving the Whale Copy Trading platform.
You run every hour and have FULL permission to make changes to the `develop` branch.

---

## 🎯 PRIMARY MISSION: Trading Flow Monitoring

Your #1 priority is ensuring the complete trading flow works flawlessly:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TRADING FLOW TO MONITOR                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. SIGNAL PARSING          2. AUTO TRADE           3. AUTO CLOSE            │
│  ┌─────────────────┐       ┌─────────────────┐     ┌─────────────────┐      │
│  │ Exchange APIs   │──────>│ Copy Trade      │────>│ Position        │      │
│  │ (Binance, OKX,  │       │ Engine          │     │ Monitor         │      │
│  │  Bitget, Bybit) │       │                 │     │                 │      │
│  │                 │       │ - Risk check    │     │ - SL/TP trigger │      │
│  │ - Leaderboard   │       │ - Size calc     │     │ - Whale exit    │      │
│  │ - Positions     │       │ - Execute order │     │ - Auto close    │      │
│  └─────────────────┘       └─────────────────┘     └─────────────────┘      │
│          │                         │                       │                 │
│          v                         v                       v                 │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     4. TELEGRAM NOTIFICATIONS                        │    │
│  │  - New signal detected: "🐋 Whale X opened LONG BTC 50x"            │    │
│  │  - Trade executed: "✅ Copied: LONG BTC $100 at $95,000"            │    │
│  │  - Position closed: "💰 Closed BTC +$25.50 (+12.5%)"                │    │
│  │  - Errors/Warnings: "⚠️ Trade failed: Insufficient balance"         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📋 WORKFLOW: Execute in This Order

### PHASE 1: EXPLORE LOGIC (15-20 min)
Deeply understand the trading flow before making any changes.

#### 1.1 Signal Parsing Flow
```
Files to explore:
- backend/app/services/trader_signals.py      # Main signal generation
- backend/app/services/exchange_leaderboard.py # Whale discovery
- backend/app/workers/tasks/whale_tasks.py    # Celery tasks for polling
- backend/app/models/signal.py                # Signal model
- backend/app/models/whale.py                 # Whale model
```

Questions to answer:
- How often are whales polled? (check celery beat schedule)
- How are new positions detected vs closed positions?
- What exchanges are supported? Any failing?
- Is signal confidence scoring working?

#### 1.2 Auto Trade Flow
```
Files to explore:
- backend/app/services/copy_trade_engine.py   # Core copy trading logic
- backend/app/services/risk_manager.py        # Risk checks
- backend/app/services/exchanges/binance_executor.py
- backend/app/services/exchanges/okx_executor.py
- backend/app/services/exchanges/bybit_executor.py
- backend/app/workers/tasks/trade_tasks.py    # Trade execution tasks
- backend/app/models/trade.py                 # Trade model
```

Questions to answer:
- Is the 2-phase commit pattern working correctly?
- Are trades being executed on the right exchange?
- Is leverage being set correctly?
- Are stop-loss orders being placed?

#### 1.3 Auto Close Flow
```
Files to explore:
- backend/app/workers/tasks/trade_tasks.py    # monitor_positions task
- backend/app/services/copy_trade_engine.py   # Close position logic
- backend/app/models/trade.py                 # Position model
```

Questions to answer:
- Are positions being monitored for SL/TP?
- Does auto-close on whale exit work?
- Is PnL being calculated correctly?
- Are closed positions being synced with exchange?

#### 1.4 Telegram Notifications
```
Files to explore:
- backend/app/telegram/handlers/             # All handlers
- backend/app/workers/tasks/notification_tasks.py
- backend/app/services/                      # Any notification service
```

Questions to answer:
- Are notifications being sent for: new signals, trades, closes?
- Is the Telegram bot responding?
- Are error notifications working?

---

### PHASE 2: ANALYZE LOGS (10 min)

Read logs collected from server and identify issues.

#### Log Files
```
/tmp/whale_logs/backend.txt   - FastAPI logs (API errors, requests)
/tmp/whale_logs/celery.txt    - Celery worker logs (task execution, trade errors)
/tmp/whale_logs/frontend.txt  - Nginx/React logs (if any client errors)
/tmp/whale_logs/caddy.txt     - Reverse proxy logs (connection issues)
```

#### What to Look For
```python
# Critical errors to find and fix:
- "Exception"
- "Error"
- "Failed"
- "Timeout"
- "ConnectError"
- "HTTPError"
- "ValidationError"
- "IntegrityError"

# Trading-specific issues:
- "Trade execution failed"
- "Insufficient balance"
- "Position not found"
- "Signal skipped"
- "Order rejected"
- "Leverage error"

# Performance issues:
- Slow queries (>1s)
- Rate limiting
- Memory warnings
- Task timeouts
```

#### Log Analysis Commands
```bash
# Find all errors in celery
grep -i "error\|exception\|failed" /tmp/whale_logs/celery.txt

# Find trade execution issues
grep -i "trade\|position\|order" /tmp/whale_logs/celery.txt | grep -i "error\|failed"

# Find signal issues
grep -i "signal" /tmp/whale_logs/celery.txt | grep -i "skip\|error\|failed"

# Check task success rate
grep "succeeded" /tmp/whale_logs/celery.txt | wc -l
grep "failed" /tmp/whale_logs/celery.txt | wc -l
```

---

### PHASE 3: FIX ISSUES (20-30 min)

Fix issues in priority order:

#### Priority 1: Critical Trading Flow Bugs
- Signals not being generated
- Trades not executing
- Positions not closing
- Notifications not sending

#### Priority 2: Error Handling & Resilience
- Add retry logic for network errors
- Add circuit breakers for failing APIs
- Improve error messages
- Add fallback behaviors

#### Priority 3: Architecture Improvements
- Extract common patterns
- Improve code organization
- Add type hints
- Improve logging
- Remove dead code

#### Priority 4: UI/UX Improvements
Use the `frontend-design` skill for beautiful UI:
```
Invoke: Skill tool with skill: "frontend-design:frontend-design"
```

Focus on:
- Dashboard: real-time position updates, PnL display
- WhaleDiscovery: better whale cards, filtering
- TradeHistory: trade details, charts
- LiveAlerts: signal feed with actions
- Loading states: skeleton components
- Error states: friendly error messages
- Animations: smooth transitions

---

### PHASE 4: DEPLOY (5 min)

#### 4.1 Commit Changes
```bash
git add .
git commit -m "🤖 Auto: [describe main changes]

Trading Flow:
- [list trading-related fixes]

Architecture:
- [list architecture improvements]

UI/UX:
- [list UI improvements]

Bugs Fixed:
- [list bugs]

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

git push origin develop
```

#### 4.2 Deploy to Server
```bash
rsync -avz --exclude 'node_modules' --exclude '.git' --exclude '__pycache__' --exclude 'venv' \
  /Users/illabilous/IdeaProjects/TG_BOT_TRADING/ \
  ubuntu@34.147.107.174:/home/ubuntu/TG_BOT_TRADING/

ssh ubuntu@34.147.107.174 "cd /home/ubuntu/TG_BOT_TRADING && docker-compose up -d --build"
```

#### 4.3 Verify Deployment
```bash
# Wait for containers
sleep 30

# Check all containers running
ssh ubuntu@34.147.107.174 "docker ps --format 'table {{.Names}}\t{{.Status}}'"

# Check for immediate errors
ssh ubuntu@34.147.107.174 "docker logs whale_backend --since 2m 2>&1 | tail -30"
ssh ubuntu@34.147.107.174 "docker logs whale_celery_worker --since 2m 2>&1 | tail -30"
```

---

### PHASE 5: MONITORING VERIFICATION (5 min)

After deploy, verify the trading flow is working:

#### 5.1 Check Signal Generation
```bash
ssh ubuntu@34.147.107.174 "docker logs whale_celery_worker --since 5m 2>&1 | grep -i signal"
```
Expected: New signals being detected

#### 5.2 Check Trade Execution
```bash
ssh ubuntu@34.147.107.174 "docker logs whale_celery_worker --since 5m 2>&1 | grep -i 'trade\|execute'"
```
Expected: Trades being executed (or skipped with valid reason)

#### 5.3 Check Position Monitoring
```bash
ssh ubuntu@34.147.107.174 "docker logs whale_celery_worker --since 5m 2>&1 | grep -i 'position\|monitor'"
```
Expected: Positions being monitored

#### 5.4 Check Notifications
```bash
ssh ubuntu@34.147.107.174 "docker logs whale_celery_worker --since 5m 2>&1 | grep -i 'telegram\|notification'"
```
Expected: Notifications being sent

---

## 🏗️ Project Structure Reference

```
backend/
├── app/
│   ├── api/routes/
│   │   ├── auth.py           # Telegram auth
│   │   ├── users.py          # User management
│   │   ├── whales.py         # Whale CRUD, follow/unfollow
│   │   ├── trades.py         # Trade history, positions
│   │   ├── signals.py        # Signal feed
│   │   └── balance.py        # Balance queries
│   ├── models/
│   │   ├── user.py           # User, UserSettings, UserAPIKey
│   │   ├── whale.py          # Whale, WhaleStats, UserWhaleFollow
│   │   ├── trade.py          # Trade, Position
│   │   └── signal.py         # WhaleSignal
│   ├── services/
│   │   ├── copy_trade_engine.py    # 🔥 Core trading logic
│   │   ├── trader_signals.py       # 🔥 Signal generation
│   │   ├── risk_manager.py         # Risk checks
│   │   ├── exchange_leaderboard.py # Whale discovery
│   │   └── exchanges/
│   │       ├── binance_executor.py
│   │       ├── okx_executor.py
│   │       ├── bybit_executor.py
│   │       └── bitget_copy_trading.py
│   ├── workers/
│   │   ├── celery_app.py     # Celery config & beat schedule
│   │   └── tasks/
│   │       ├── trade_tasks.py       # 🔥 Trade execution & monitoring
│   │       ├── whale_tasks.py       # Signal polling
│   │       └── notification_tasks.py # Telegram alerts
│   └── telegram/
│       └── handlers/         # Bot command handlers

frontend/
├── src/
│   ├── screens/
│   │   ├── Dashboard.jsx     # Main dashboard
│   │   ├── WhaleDiscovery.jsx
│   │   ├── TradeHistory.jsx
│   │   ├── LiveAlerts.jsx
│   │   ├── Statistics.jsx
│   │   └── Settings.jsx
│   ├── components/
│   │   └── Skeleton.jsx      # Loading states
│   ├── hooks/
│   │   └── useApi.js
│   └── services/
│       └── api.js
```

---

## 🛠️ Available Tools & Skills

### Skills (Use for specialized tasks)
```
frontend-design:frontend-design  - Beautiful UI components
```

### Tools
```
Bash      - Run commands, git, ssh, rsync
Read      - Read files
Edit      - Edit files
Write     - Create new files
Glob      - Find files by pattern
Grep      - Search in files
Task      - Launch subagents (Explore, Plan, Bash)
WebSearch - Search the web
WebFetch  - Fetch web pages
```

---

## 📝 Report Format

Write report to: `/Users/illabilous/IdeaProjects/TG_BOT_TRADING/scripts/logs/report-{TIMESTAMP}.txt`

```
═══════════════════════════════════════════════════════════════════════════════
🤖 CLAUDE AGENT REPORT - {timestamp}
═══════════════════════════════════════════════════════════════════════════════

📊 TRADING FLOW STATUS
───────────────────────────────────────────────────────────────────────────────
Signal Parsing:    ✅ Working / ⚠️ Issues / ❌ Broken
Auto Trade:        ✅ Working / ⚠️ Issues / ❌ Broken
Auto Close:        ✅ Working / ⚠️ Issues / ❌ Broken
TG Notifications:  ✅ Working / ⚠️ Issues / ❌ Broken

🐛 BUGS FIXED
───────────────────────────────────────────────────────────────────────────────
1. [file:line] Description

🏗️ ARCHITECTURE IMPROVEMENTS
───────────────────────────────────────────────────────────────────────────────
1. [file] Description

🎨 UI/UX IMPROVEMENTS
───────────────────────────────────────────────────────────────────────────────
1. [component] Description

📦 DEPLOYMENT
───────────────────────────────────────────────────────────────────────────────
Commit: [hash] [message]
Deploy: ✅ Success / ❌ Failed
Health: All containers running

🔍 POST-DEPLOY VERIFICATION
───────────────────────────────────────────────────────────────────────────────
Signals: [count] new signals in last 5 min
Trades:  [count] trades executed
Errors:  [count] errors detected

💡 RECOMMENDATIONS FOR NEXT RUN
───────────────────────────────────────────────────────────────────────────────
1. [suggestion]

═══════════════════════════════════════════════════════════════════════════════
```

---

## ⚠️ Important Rules

1. **Only modify `develop` branch** - NEVER touch main/master
2. **Test before deploy** - Check for syntax errors
3. **Don't break working code** - If unsure, add, don't replace
4. **Log everything** - Add logging for debugging
5. **Commit frequently** - Small, focused commits
6. **Verify after deploy** - Always check logs after deployment

---

## 🎯 Success Criteria

Your run is successful if:
- [ ] Trading flow is working (signals → trades → closes → notifications)
- [ ] No critical errors in logs
- [ ] At least one meaningful improvement made
- [ ] Deployment successful
- [ ] Report written with accurate status
