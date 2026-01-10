"""Celery Application Configuration.

Production-ready Celery setup with:
- Redis broker and result backend
- Task retry policies
- Beat scheduler for periodic tasks
- Structured logging

Usage:
    # Start worker
    celery -A app.presentation.workers worker --loglevel=info

    # Start beat scheduler
    celery -A app.presentation.workers beat --loglevel=info

    # Start both (development only)
    celery -A app.presentation.workers worker --beat --loglevel=info
"""

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "trading_workers",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.presentation.workers.tasks.signal_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    # ==================== Task Settings ====================
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_acks_late=settings.celery_task_acks_late,
    task_reject_on_worker_lost=settings.celery_task_reject_on_worker_lost,
    task_time_limit=300,  # 5 minutes max per task
    task_soft_time_limit=240,  # Soft limit 4 minutes

    # Result backend
    result_expires=3600,  # Results expire after 1 hour

    # ==================== Worker Settings ====================
    worker_prefetch_multiplier=1,  # One task at a time for fair distribution
    worker_concurrency=settings.celery_worker_concurrency,
    worker_max_tasks_per_child=1000,  # Restart worker after N tasks (memory leaks)
    worker_disable_rate_limits=False,

    # ==================== Broker Settings ====================
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,

    # ==================== Beat Scheduler ====================
    beat_schedule={
        # Process signals every 5 seconds
        "process-signals-batch": {
            "task": "app.presentation.workers.tasks.signal_tasks.process_signals_batch",
            "schedule": settings.signal_processing_interval,
            "kwargs": {
                "max_signals": settings.max_signals_per_batch,
                "min_priority": "low",
            },
        },
        # Cleanup expired signals every 5 minutes
        "cleanup-expired-signals": {
            "task": "app.presentation.workers.tasks.signal_tasks.cleanup_expired_signals",
            "schedule": settings.signal_cleanup_interval,
            "kwargs": {
                "expiry_seconds": settings.signal_expiry_seconds,
            },
        },
        # Health check every minute
        "queue-status-check": {
            "task": "app.presentation.workers.tasks.signal_tasks.get_queue_status",
            "schedule": 60.0,
        },
    },

    # ==================== Task Routes ====================
    task_routes={
        "app.presentation.workers.tasks.signal_tasks.*": {"queue": "signals"},
        # Future: trade tasks
        # "app.presentation.workers.tasks.trade_tasks.*": {"queue": "trades"},
    },

    # ==================== Default Queue ====================
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
)

# Task error handling
celery_app.conf.task_annotations = {
    "app.presentation.workers.tasks.signal_tasks.process_signals_batch": {
        "rate_limit": "20/m",  # Max 20 batches per minute
    },
}


# Signals for logging
@celery_app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery connection."""
    print(f"Request: {self.request!r}")
    return {"status": "ok", "worker": self.request.hostname}
