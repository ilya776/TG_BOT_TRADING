"""Celery workers for background processing.

Usage:
    # Start worker
    celery -A app.presentation.workers worker --loglevel=info

    # Start beat scheduler
    celery -A app.presentation.workers beat --loglevel=info

    # Start flower (monitoring)
    celery -A app.presentation.workers flower --port=5555
"""

from .celery_app import celery_app

__all__ = ["celery_app"]
