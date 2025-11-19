"""Machine Learning models for storing trained models and predictions."""

import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()


class MLModel(models.Model):
    """Stores trained machine learning models and metadata."""

    MODEL_TYPES = [
        ("effort_prediction", "Effort Prediction"),
        ("sprint_duration", "Sprint Duration Estimation"),
        ("story_points", "Story Points Recommendation"),
        ("task_assignment", "Task Assignment Suggestion"),
        ("risk_detection", "Risk Detection"),
        ("anomaly_detection", "Anomaly Detection"),
    ]

    STATUS_CHOICES = [
        ("training", "Training"),
        ("active", "Active"),
        ("deprecated", "Deprecated"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=200,
        help_text="Human-readable model name",
        blank=True,
    )
    model_type = models.CharField(max_length=50, choices=MODEL_TYPES)
    version = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="training")
    is_active = models.BooleanField(
        default=False,
        help_text="Whether this model is currently active for predictions",
    )

    # Model file storage (S3 paths)
    model_file = models.FileField(upload_to="ml_models/", null=True, blank=True)
    model_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="S3 key path to model file",
    )
    s3_bucket = models.CharField(
        max_length=255,
        blank=True,
        help_text="S3 bucket name where model is stored",
    )
    s3_key = models.CharField(
        max_length=500,
        blank=True,
        help_text="S3 object key for the model file",
    )

    # Training metadata
    training_samples = models.IntegerField(default=0)
    training_date = models.DateTimeField(auto_now_add=True)
    trained_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )

    # Performance metrics
    accuracy_score = models.FloatField(null=True, blank=True)
    precision_score = models.FloatField(null=True, blank=True)
    recall_score = models.FloatField(null=True, blank=True)
    f1_score = models.FloatField(null=True, blank=True)
    mae = models.FloatField(null=True, blank=True, help_text="Mean Absolute Error")
    rmse = models.FloatField(null=True, blank=True, help_text="Root Mean Squared Error")
    r2_score = models.FloatField(null=True, blank=True, help_text="R-squared Score")

    # Additional metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (accuracy, samples_count, project_id, etc.)",
    )
    hyperparameters = models.JSONField(default=dict, blank=True)
    feature_importance = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ml_models"
        ordering = ["-training_date"]
        indexes = [
            models.Index(fields=["model_type", "status"]),
            models.Index(fields=["training_date"]),
        ]

    def __str__(self):
        if self.name:
            return f"{self.name} v{self.version} ({self.status})"
        return f"{self.get_model_type_display()} v{self.version} ({self.status})"

    def get_s3_path(self) -> str:
        """Get full S3 path for the model."""
        if self.s3_key:
            return f"s3://{self.s3_bucket}/{self.s3_key}"
        return ""


class PredictionHistory(models.Model):
    """Stores prediction history for analysis and improvement."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model = models.ForeignKey(
        MLModel, on_delete=models.CASCADE, related_name="predictions"
    )

    # Input data
    input_data = models.JSONField(help_text="Input features used for prediction")

    # Prediction results
    predicted_value = models.FloatField()
    confidence_score = models.FloatField(null=True, blank=True)
    prediction_range_min = models.FloatField(null=True, blank=True)
    prediction_range_max = models.FloatField(null=True, blank=True)

    # Actual outcome (for validation)
    actual_value = models.FloatField(null=True, blank=True)
    outcome_recorded_at = models.DateTimeField(null=True, blank=True)

    # Context
    project_id = models.UUIDField(null=True, blank=True)
    issue_id = models.UUIDField(null=True, blank=True)
    sprint_id = models.UUIDField(null=True, blank=True)
    requested_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ml_prediction_history"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["model", "created_at"]),
            models.Index(fields=["project_id"]),
            models.Index(fields=["issue_id"]),
        ]

    def __str__(self):
        return f"Prediction {self.id} - {self.predicted_value}"

    def calculate_error(self):
        """Calculate prediction error if actual value is available."""
        if self.actual_value is not None:
            return abs(self.predicted_value - self.actual_value)
        return None


class AnomalyDetection(models.Model):
    """Stores detected anomalies and patterns."""

    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    STATUS_CHOICES = [
        ("detected", "Detected"),
        ("investigating", "Investigating"),
        ("resolved", "Resolved"),
        ("false_positive", "False Positive"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Anomaly details
    anomaly_type = models.CharField(
        max_length=100, help_text="Type of anomaly detected"
    )
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="detected")

    # Context
    project_id = models.UUIDField(null=True, blank=True)
    sprint_id = models.UUIDField(null=True, blank=True)
    affected_metric = models.CharField(max_length=100)

    # Detection data
    expected_value = models.FloatField(null=True, blank=True)
    actual_value = models.FloatField()
    deviation_score = models.FloatField(
        help_text="How far from normal (in standard deviations)"
    )

    # Analysis
    description = models.TextField()
    possible_causes = models.JSONField(default=list, blank=True)
    mitigation_suggestions = models.JSONField(default=list, blank=True)

    # Resolution
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_anomalies",
    )
    resolution_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ml_anomaly_detections"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project_id", "status"]),
            models.Index(fields=["severity", "created_at"]),
            models.Index(fields=["anomaly_type"]),
        ]

    def __str__(self):
        return f"{self.anomaly_type} - {self.severity} ({self.status})"

    def mark_resolved(self, user, notes=""):
        """Mark anomaly as resolved."""
        self.status = "resolved"
        self.resolved_at = timezone.now()
        self.resolved_by = user
        self.resolution_notes = notes
        self.save()
