"""
Celery Application Configuration
"""
import os
import json
import logging
from datetime import datetime
from celery import Celery
from celery.signals import task_failure, task_success, task_retry

logger = logging.getLogger(__name__)

# Redis URL from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create Celery app
celery_app = Celery(
    "whale_trading",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.workers.tasks.trade_tasks",
        "app.workers.tasks.notification_tasks",
        "app.workers.tasks.whale_tasks",
    ],
)


# ==============================================================================
# Dead Letter Queue (DLQ) - Captures all failed tasks for later analysis
# ==============================================================================

DLQ_KEY = "whale_trading:dead_letter_queue"
DLQ_MAX_SIZE = 1000  # Keep last 1000 failed tasks


def _get_redis_client():
    """Get Redis client for DLQ operations."""
    import redis
    return redis.from_url(REDIS_URL)


@task_failure.connect
def handle_task_failure(sender=None, task_id=None, exception=None, args=None,
                        kwargs=None, traceback=None, einfo=None, **kw):
    """
    Handle failed tasks by storing them in Dead Letter Queue.
    This allows for later analysis, retry, or alerting.
    """
    try:
        failed_task = {
            "task_id": task_id,
            "task_name": sender.name if sender else "unknown",
            "args": str(args)[:500],  # Truncate to avoid huge payloads
            "kwargs": str(kwargs)[:500],
            "exception": str(exception)[:1000],
            "traceback": str(traceback)[-2000:] if traceback else None,  # Last 2000 chars
            "failed_at": datetime.utcnow().isoformat(),
            "retries": sender.request.retries if sender else 0,
        }

        # Log the failure
        logger.error(
            f"Task FAILED: {failed_task['task_name']} (id={task_id})",
            extra={
                "task_id": task_id,
                "exception": str(exception),
            }
        )

        # Store in Redis DLQ
        redis_client = _get_redis_client()
        redis_client.lpush(DLQ_KEY, json.dumps(failed_task))
        redis_client.ltrim(DLQ_KEY, 0, DLQ_MAX_SIZE - 1)  # Keep only last N

        # Alert for trade-related failures (critical)
        if "trade" in failed_task["task_name"].lower():
            logger.critical(
                f"TRADE TASK FAILED: {failed_task['task_name']} - {exception}",
                extra=failed_task,
            )

    except Exception as e:
        logger.error(f"Failed to store task in DLQ: {e}")


@task_retry.connect
def handle_task_retry(sender=None, request=None, reason=None, einfo=None, **kw):
    """Log task retries for monitoring."""
    logger.warning(
        f"Task RETRYING: {sender.name if sender else 'unknown'} "
        f"(attempt {request.retries + 1 if request else '?'}): {reason}"
    )


@task_success.connect
def handle_task_success(sender=None, result=None, **kw):
    """Log successful trade tasks for auditing."""
    if sender and "trade" in sender.name.lower():
        logger.info(f"Trade task SUCCESS: {sender.name}")

# Celery Configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes

    # Worker settings
    worker_prefetch_multiplier=1,
    worker_concurrency=4,

    # Result backend settings
    result_expires=3600,  # 1 hour

    # Beat schedule for periodic tasks
    beat_schedule={
        # Check whale positions every 30 seconds
        "check-whale-positions": {
            "task": "app.workers.tasks.whale_tasks.check_whale_positions",
            "schedule": 30.0,
        },
        # Update position prices every 10 seconds
        "update-position-prices": {
            "task": "app.workers.tasks.trade_tasks.update_position_prices",
            "schedule": 10.0,
        },
        # Monitor positions for SL/TP every 10 seconds (same as price updates for fresher data)
        "monitor-positions": {
            "task": "app.workers.tasks.trade_tasks.monitor_positions",
            "schedule": 10.0,
        },
        # Sync user balances every 30 seconds (reduced from 5s to prevent API rate limits)
        "sync-user-balances": {
            "task": "app.workers.tasks.trade_tasks.sync_all_user_balances",
            "schedule": 30.0,
        },
        # Update whale follower counts every 5 minutes
        "update-follower-counts": {
            "task": "app.workers.tasks.whale_tasks.update_whale_followers_count",
            "schedule": 300.0,
        },
        # Sync exchange leaderboards every 60 seconds (fetches real top traders from Binance/Bybit)
        # Note: 60s is minimum to avoid exchange rate limits while keeping data fresh
        "sync-exchange-leaderboards": {
            "task": "app.workers.tasks.whale_tasks.sync_exchange_leaderboards",
            "schedule": 60.0,
        },
        # Generate trading signals from trader positions every 60 seconds
        # Note: Each run checks 20 traders via Binance API - must be spaced to avoid 429 rate limits
        "generate-trader-signals": {
            "task": "app.workers.tasks.whale_tasks.generate_trader_signals",
            "schedule": 60.0,
        },
        # Update whale statistics every hour
        "update-whale-stats": {
            "task": "app.workers.tasks.whale_tasks.update_whale_statistics",
            "schedule": 3600.0,
        },
        # Clean up old signals daily
        "cleanup-old-signals": {
            "task": "app.workers.tasks.whale_tasks.cleanup_old_signals",
            "schedule": 86400.0,
        },
        # Clean up old notifications daily
        "cleanup-notifications": {
            "task": "app.workers.tasks.notification_tasks.cleanup_old_notifications",
            "schedule": 86400.0,
        },
    },

    # Task routes
    task_routes={
        "app.workers.tasks.trade_tasks.*": {"queue": "trades"},
        "app.workers.tasks.notification_tasks.*": {"queue": "notifications"},
        "app.workers.tasks.whale_tasks.*": {"queue": "whales"},
    },
)

# Create task directories if tasks don't exist yet
import os
tasks_dir = os.path.join(os.path.dirname(__file__), "tasks")
os.makedirs(tasks_dir, exist_ok=True)
