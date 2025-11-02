"""
Celery tasks for ML app.

Scheduled tasks for model retraining and anomaly detection.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="apps.ml.tasks.retrain_ml_models")
def retrain_ml_models(self):
    """
    Retrain ML models when sufficient new data is available.

    This task runs weekly (Monday 2 AM) and checks if models need retraining
    based on the number of new completed issues since last training.

    Returns:
        dict: Training results summary
    """
    try:
        from apps.ml.models import MLModel, PredictionHistory
        from apps.ml.services import ModelTrainer
        from apps.projects.models import Issue

        logger.info("Starting ML model retraining task")

        model_trainer = ModelTrainer()
        results = {
            "models_retrained": 0,
            "models_skipped": 0,
            "errors": [],
        }

        # Get all active ML models
        active_models = MLModel.objects.filter(is_active=True)

        for ml_model in active_models:
            try:
                # Check if retraining is needed
                if not model_trainer.should_retrain(ml_model):
                    results["models_skipped"] += 1
                    logger.info(f"Skipping retraining for {ml_model.name} - insufficient new data")
                    continue

                # Get training data based on model type
                project_id = ml_model.metadata.get("project_id") if ml_model.metadata else None

                if ml_model.model_type == "effort_prediction":
                    # Query completed issues with actual hours
                    queryset = Issue.objects.filter(
                        status__is_final=True,
                        actual_hours__isnull=False,
                    )
                    if project_id:
                        queryset = queryset.filter(project_id=project_id)

                    training_data_count = queryset.count()

                    if training_data_count < 100:  # Minimum threshold
                        logger.warning(f"Insufficient training data for {ml_model.name}: {training_data_count} samples")
                        results["models_skipped"] += 1
                        continue

                    # Train the model
                    logger.info(f"Retraining {ml_model.name} with {training_data_count} samples")
                    new_model = model_trainer.train_model(
                        model_type=ml_model.model_type,
                        project_id=project_id,
                    )

                    if new_model:
                        # Evaluate against current model
                        evaluation = model_trainer.evaluate_model(new_model.id)

                        # Only replace if new model is better
                        if evaluation.get("accuracy", 0) > ml_model.metadata.get("accuracy", 0):
                            ml_model.is_active = False
                            ml_model.save()

                            new_model.is_active = True
                            new_model.save()

                            results["models_retrained"] += 1
                            logger.info(f"Successfully retrained {ml_model.name} - New accuracy: {evaluation.get('accuracy')}")
                        else:
                            new_model.delete()
                            results["models_skipped"] += 1
                            logger.info(f"New model for {ml_model.name} not better than current, keeping existing")

            except Exception as e:
                error_msg = f"Error retraining {ml_model.name}: {str(e)}"
                logger.exception(error_msg)
                results["errors"].append(error_msg)

        logger.info(f"ML retraining task completed: {results}")
        return results

    except Exception as e:
        logger.exception(f"Critical error in retrain_ml_models task: {str(e)}")
        raise


@shared_task(bind=True, name="apps.ml.tasks.detect_project_anomalies_periodic")
def detect_project_anomalies_periodic(self):
    """
    Detect anomalies in all active projects.

    This task runs every 6 hours and identifies unusual patterns like velocity drops,
    excessive reassignments, stale issues, and bottlenecks.

    Returns:
        dict: Detection results summary
    """
    try:
        from apps.ml.models import AnomalyDetection
        from apps.ml.services import AnomalyDetectionService
        from apps.notifications.services import NotificationService
        from apps.projects.models import Project

        logger.info("Starting periodic anomaly detection task")

        anomaly_service = AnomalyDetectionService()
        notification_service = NotificationService()

        results = {
            "projects_checked": 0,
            "anomalies_detected": 0,
            "notifications_sent": 0,
            "errors": [],
        }

        # Get active projects (has activity in last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        active_projects = Project.objects.filter(
            is_active=True,
            updated_at__gte=thirty_days_ago,
        ).select_related("workspace__organization")

        for project in active_projects:
            try:
                results["projects_checked"] += 1

                # Detect anomalies
                anomalies = anomaly_service.detect_project_anomalies(str(project.id))

                if not anomalies:
                    continue

                # Filter out already reported anomalies (within last 24 hours)
                for anomaly_data in anomalies:
                    # Check if this anomaly was already detected recently
                    recent_detection = AnomalyDetection.objects.filter(
                        project=project,
                        anomaly_type=anomaly_data["anomaly_type"],
                        created_at__gte=timezone.now() - timedelta(hours=24),
                        resolution_status="unresolved",
                    ).exists()

                    if recent_detection:
                        logger.debug(f"Skipping duplicate anomaly {anomaly_data['anomaly_type']} for project {project.key}")
                        continue

                    # New anomaly - notify project leads
                    try:
                        notification_service.notify_anomaly_detected(
                            project_id=str(project.id),
                            anomaly_type=anomaly_data["anomaly_type"],
                            description=anomaly_data["description"],
                            severity=anomaly_data["severity"],
                        )
                        results["anomalies_detected"] += 1
                        results["notifications_sent"] += 1

                        logger.info(f"Detected and notified {anomaly_data['severity']} anomaly in project {project.key}")

                    except Exception as e:
                        error_msg = f"Error notifying anomaly for project {project.key}: {str(e)}"
                        logger.exception(error_msg)
                        results["errors"].append(error_msg)

            except Exception as e:
                error_msg = f"Error detecting anomalies for project {project.key}: {str(e)}"
                logger.exception(error_msg)
                results["errors"].append(error_msg)

        logger.info(f"Anomaly detection task completed: {results}")
        return results

    except Exception as e:
        logger.exception(f"Critical error in detect_project_anomalies_periodic task: {str(e)}")
        raise


@shared_task(bind=True, name="apps.ml.tasks.cleanup_old_prediction_history")
def cleanup_old_prediction_history(self):
    """
    Clean up old prediction history records (older than 1 year).

    This maintenance task prevents unbounded growth of prediction history.

    Returns:
        dict: Cleanup results
    """
    try:
        from apps.ml.models import PredictionHistory

        logger.info("Starting prediction history cleanup task")

        one_year_ago = timezone.now() - timedelta(days=365)
        deleted_count, _ = PredictionHistory.objects.filter(
            created_at__lt=one_year_ago
        ).delete()

        logger.info(f"Deleted {deleted_count} old prediction history records")
        return {"deleted_count": deleted_count}

    except Exception as e:
        logger.exception(f"Error in cleanup_old_prediction_history task: {str(e)}")
        raise
