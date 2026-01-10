-- ============================================
-- Fix Auto-Copy Not Executing Trades
-- ============================================
-- Problem: Signals are created but no trades execute because auto_copy_enabled is FALSE
--
-- This script:
-- 1. Checks current auto_copy_enabled status
-- 2. Enables auto_copy for all active follows
-- 3. Verifies the fix
-- ============================================

-- STEP 1: Check current status
\echo '=== Current Follow Status ==='
SELECT
    uwf.id,
    uwf.user_id,
    uwf.whale_id,
    w.name as whale_name,
    uwf.auto_copy_enabled,
    uwf.notify_on_trade,
    uwf.trade_size_percent,
    uwf.created_at,
    u.available_balance,
    u.is_active as user_active
FROM user_whale_follows uwf
JOIN whales w ON uwf.whale_id = w.id
JOIN users u ON uwf.user_id = u.id
WHERE u.is_active = true
ORDER BY uwf.created_at DESC;

-- STEP 2: Count signals that couldn't be executed
\echo ''
\echo '=== Signals Without Followers ==='
SELECT
    COUNT(*) as total_signals,
    COUNT(*) FILTER (WHERE ws.status = 'PROCESSED') as processed,
    COUNT(*) FILTER (WHERE ws.status = 'PENDING') as pending
FROM whale_signals ws
WHERE ws.cex_available = true
  AND ws.cex_symbol IS NOT NULL;

-- STEP 3: Check recent signals from whales user is following
\echo ''
\echo '=== Recent Signals from Followed Whales ==='
SELECT
    ws.id,
    ws.whale_id,
    w.name as whale_name,
    ws.cex_symbol,
    ws.amount_usd,
    ws.action,
    ws.status,
    ws.detected_at,
    uwf.auto_copy_enabled as user_has_auto_copy
FROM whale_signals ws
JOIN whales w ON ws.whale_id = w.id
LEFT JOIN user_whale_follows uwf ON uwf.whale_id = ws.whale_id AND uwf.user_id = 1
WHERE ws.cex_available = true
ORDER BY ws.detected_at DESC
LIMIT 10;

-- STEP 4: Enable auto_copy for all active follows
\echo ''
\echo '=== FIXING: Enabling auto_copy for all follows ==='
UPDATE user_whale_follows
SET
    auto_copy_enabled = true,
    notify_on_trade = true,
    trade_size_percent = COALESCE(trade_size_percent, 100)  -- Default to 100% if null
WHERE auto_copy_enabled = false
  AND user_id IN (SELECT id FROM users WHERE is_active = true);

-- Show updated count
SELECT
    COUNT(*) as total_follows,
    COUNT(*) FILTER (WHERE auto_copy_enabled = true) as auto_copy_enabled,
    COUNT(*) FILTER (WHERE auto_copy_enabled = false) as auto_copy_disabled
FROM user_whale_follows uwf
JOIN users u ON uwf.user_id = u.id
WHERE u.is_active = true;

-- STEP 5: Verify the fix
\echo ''
\echo '=== After Fix: User 1 Follows ==='
SELECT
    uwf.id,
    uwf.whale_id,
    w.name as whale_name,
    uwf.auto_copy_enabled,
    uwf.trade_size_percent,
    w.followers_count,
    w.score as whale_score
FROM user_whale_follows uwf
JOIN whales w ON uwf.whale_id = w.id
WHERE uwf.user_id = 1;

\echo ''
\echo '=== Fix Complete ==='
\echo 'All active follows now have auto_copy_enabled = true'
\echo 'New signals will now execute copy trades automatically'
\echo ''
\echo 'Next: Restart celery workers to process pending signals:'
\echo '  docker compose restart celery backend'
