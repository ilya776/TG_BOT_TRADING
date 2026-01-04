"""
Celery Application Configuration
"""
import os
from celery import Celery

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
        # Monitor positions for SL/TP every 30 seconds
        "monitor-positions": {
            "task": "app.workers.tasks.trade_tasks.monitor_positions",
            "schedule": 30.0,
        },
        # Sync user balances every 5 minutes
        "sync-user-balances": {
            "task": "app.workers.tasks.trade_tasks.sync_all_user_balances",
            "schedule": 300.0,
        },
        # Update whale follower counts every 5 minutes
        "update-follower-counts": {
            "task": "app.workers.tasks.whale_tasks.update_whale_followers_count",
            "schedule": 300.0,
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
