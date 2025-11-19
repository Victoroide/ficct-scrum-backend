"""
Serializers for ML models and API responses.

Provides serialization for database models and API endpoint responses.
"""

from rest_framework import serializers

from apps.ml.models import AnomalyDetection, MLModel, PredictionHistory


class MLModelSerializer(serializers.ModelSerializer):
    """Serializer for MLModel."""

    s3_path = serializers.SerializerMethodField()
    trained_by_name = serializers.SerializerMethodField()

    class Meta:
        model = MLModel
        fields = [
            "id",
            "name",
            "model_type",
            "version",
            "status",
            "is_active",
            "s3_bucket",
            "s3_key",
            "s3_path",
            "training_samples",
            "training_date",
            "trained_by",
            "trained_by_name",
            "accuracy_score",
            "precision_score",
            "recall_score",
            "f1_score",
            "mae",
            "rmse",
            "r2_score",
            "metadata",
            "hyperparameters",
            "feature_importance",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "training_date",
            "created_at",
            "updated_at",
            "s3_path",
            "trained_by_name",
        ]

    def get_s3_path(self, obj):
        """Get full S3 path for the model."""
        return obj.get_s3_path()

    def get_trained_by_name(self, obj):
        """Get name of user who trained the model."""
        if obj.trained_by:
            return obj.trained_by.get_full_name() or obj.trained_by.username
        return None


class PredictionHistorySerializer(serializers.ModelSerializer):
    """Serializer for PredictionHistory."""

    model_name = serializers.CharField(source="model.name", read_only=True)
    model_version = serializers.CharField(source="model.version", read_only=True)
    prediction_error = serializers.SerializerMethodField()

    class Meta:
        model = PredictionHistory
        fields = [
            "id",
            "model",
            "model_name",
            "model_version",
            "input_data",
            "predicted_value",
            "confidence_score",
            "prediction_range_min",
            "prediction_range_max",
            "actual_value",
            "outcome_recorded_at",
            "prediction_error",
            "project_id",
            "issue_id",
            "sprint_id",
            "requested_by",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "model_name", "model_version"]

    def get_prediction_error(self, obj):
        """Calculate prediction error if actual value is available."""
        return obj.calculate_error()


class AnomalyDetectionSerializer(serializers.ModelSerializer):
    """Serializer for AnomalyDetection."""

    resolved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = AnomalyDetection
        fields = [
            "id",
            "anomaly_type",
            "severity",
            "status",
            "project_id",
            "sprint_id",
            "affected_metric",
            "expected_value",
            "actual_value",
            "deviation_score",
            "description",
            "possible_causes",
            "mitigation_suggestions",
            "resolved_at",
            "resolved_by",
            "resolved_by_name",
            "resolution_notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "resolved_by_name"]

    def get_resolved_by_name(self, obj):
        """Get name of user who resolved the anomaly."""
        if obj.resolved_by:
            return obj.resolved_by.get_full_name() or obj.resolved_by.username
        return None


class EffortPredictionResponseSerializer(serializers.Serializer):
    """Serializer for effort prediction API response."""

    predicted_hours = serializers.FloatField()
    confidence = serializers.FloatField()
    prediction_range = serializers.DictField(required=False)
    similar_issues = serializers.ListField(required=False)
    method = serializers.CharField()
    reasoning = serializers.CharField()
    model_id = serializers.UUIDField(required=False)
    model_version = serializers.CharField(required=False)


class SprintDurationEstimateSerializer(serializers.Serializer):
    """Serializer for sprint duration estimate API response."""

    estimated_days = serializers.IntegerField()
    planned_days = serializers.IntegerField()
    confidence = serializers.FloatField()
    risk_factors = serializers.ListField(child=serializers.CharField())
    method = serializers.CharField()
    average_velocity = serializers.FloatField(required=False)
    total_story_points = serializers.IntegerField(required=False)
    total_estimated_hours = serializers.FloatField(required=False)
    hours_per_day = serializers.IntegerField(required=False)


class StoryPointsRecommendationSerializer(serializers.Serializer):
    """Serializer for story points recommendation API response."""

    recommended_points = serializers.IntegerField()
    confidence = serializers.FloatField()
    probability_distribution = serializers.DictField()
    reasoning = serializers.CharField()
    similar_issues = serializers.ListField(required=False)
    method = serializers.CharField()


class TaskAssignmentSuggestionSerializer(serializers.Serializer):
    """Serializer for task assignment suggestion."""

    user_id = serializers.UUIDField()
    user_name = serializers.CharField()
    user_email = serializers.EmailField()
    total_score = serializers.FloatField()
    skill_score = serializers.FloatField()
    workload_score = serializers.FloatField()
    performance_score = serializers.FloatField()
    availability_score = serializers.FloatField()
    reasoning = serializers.ListField(child=serializers.CharField())


class SprintRiskSerializer(serializers.Serializer):
    """Serializer for sprint risk detection."""

    risk_type = serializers.CharField()
    severity = serializers.CharField()
    description = serializers.CharField()
    mitigation_suggestions = serializers.ListField(child=serializers.CharField())
    # Optional fields depending on risk type
    expected_completion = serializers.FloatField(required=False)
    actual_completion = serializers.FloatField(required=False)
    unassigned_count = serializers.IntegerField(required=False)
    total_count = serializers.IntegerField(required=False)
    estimated_hours = serializers.FloatField(required=False)
    actual_hours = serializers.FloatField(required=False)
    drift_percentage = serializers.FloatField(required=False)


class ProjectAnomalySerializer(serializers.Serializer):
    """Serializer for project anomaly detection."""

    anomaly_type = serializers.CharField()
    severity = serializers.CharField()
    description = serializers.CharField()
    possible_causes = serializers.ListField(child=serializers.CharField())
    mitigation_suggestions = serializers.ListField(child=serializers.CharField())
    current_velocity = serializers.FloatField(required=False)
    average_velocity = serializers.FloatField(required=False)
    deviation_score = serializers.FloatField(required=False)
    stale_count = serializers.IntegerField(required=False)
    recent_count = serializers.IntegerField(required=False)
    average_count = serializers.FloatField(required=False)


class ModelTrainingRequestSerializer(serializers.Serializer):
    """Serializer for model training request."""

    model_type = serializers.ChoiceField(
        choices=[
            "effort_prediction",
            "sprint_duration",
            "story_points",
            "task_assignment",
            "risk_detection",
            "anomaly_detection",
        ]
    )
    project_id = serializers.UUIDField(required=False, allow_null=True)
    force_retrain = serializers.BooleanField(default=False)


class ModelTrainingResponseSerializer(serializers.Serializer):
    """Serializer for model training response."""

    success = serializers.BooleanField()
    model_id = serializers.UUIDField(required=False)
    model_type = serializers.CharField()
    version = serializers.CharField(required=False)
    training_samples = serializers.IntegerField(required=False)
    metrics = serializers.DictField(required=False)
    message = serializers.CharField()
