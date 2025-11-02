"""
Celery configuration for FICCT-SCRUM.

This module configures Celery for asynchronous task processing and scheduled jobs.
"""

import os

from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "base.settings")

app = Celery("ficct_scrum")

# Load configuration from Django settings with CELERY namespace
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()


# Configure periodic tasks
app.conf.beat_schedule = {
    # ML Model Retraining (Weekly, Monday 2 AM)
    "retrain-ml-models": {
        "task": "apps.ml.tasks.retrain_ml_models",
        "schedule": crontab(hour=2, minute=0, day_of_week=1),
    },
    # Deadline Monitoring (Daily, 9 AM)
    "check-upcoming-deadlines": {
        "task": "apps.notifications.tasks.check_upcoming_deadlines",
        "schedule": crontab(hour=9, minute=0),
    },
    # Anomaly Detection (Every 6 hours)
    "detect-project-anomalies": {
        "task": "apps.ml.tasks.detect_project_anomalies_periodic",
        "schedule": crontab(hour="*/6"),
    },
    # Database Backup (Daily, 1 AM)
    "backup-database": {
        "task": "apps.admin_tools.tasks.backup_database",
        "schedule": crontab(hour=1, minute=0),
    },
    # Summary Cache Cleanup (Daily, 3 AM)
    "cleanup-old-summaries": {
        "task": "apps.ai_assistant.tasks.cleanup_old_summaries",
        "schedule": crontab(hour=3, minute=0),
    },
    # Reindex Stale Issues (Daily, 4 AM)
    "reindex-stale-issues": {
        "task": "apps.ai_assistant.tasks.reindex_stale_issues",
        "schedule": crontab(hour=4, minute=0),
    },
}

# Celery configuration
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3300,  # 55 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery configuration."""
    print(f"Request: {self.request!r}")
