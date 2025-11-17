"""
Django admin for ML app.
"""

from django.contrib import admin

from apps.ml.models import AnomalyDetection, MLModel, PredictionHistory


@admin.register(MLModel)
class MLModelAdmin(admin.ModelAdmin):
    """Admin for MLModel."""

    list_display = ["id", "model_type", "version", "status", "training_date"]
    list_filter = ["model_type", "status", "training_date"]
    search_fields = ["model_type", "version"]
    readonly_fields = ["training_date"]
    ordering = ["-training_date"]

    fieldsets = (
        ("Basic Information", {"fields": ("model_type", "version", "status")}),
        (
            "Model Details",
            {"fields": ("model_file", "model_path", "training_samples", "trained_by")},
        ),
        (
            "Performance Metrics",
            {
                "fields": (
                    "accuracy_score",
                    "precision_score",
                    "recall_score",
                    "f1_score",
                    "mae",
                    "rmse",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Timestamps", {"fields": ("training_date",), "classes": ("collapse",)}),
    )


@admin.register(PredictionHistory)
class PredictionHistoryAdmin(admin.ModelAdmin):
    """Admin for PredictionHistory."""

    list_display = ["model", "predicted_value", "actual_value", "created_at"]
    list_filter = ["model", "created_at"]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        """Prevent adding prediction history manually."""
        return False


@admin.register(AnomalyDetection)
class AnomalyDetectionAdmin(admin.ModelAdmin):
    """Admin for AnomalyDetection."""

    list_display = [
        "id",
        "anomaly_type",
        "severity",
        "status",
        "created_at",
    ]
    list_filter = [
        "anomaly_type",
        "severity",
        "status",
        "created_at",
    ]
    search_fields = ["description", "anomaly_type"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]

    actions = ["mark_as_resolved", "mark_as_false_positive"]

    def mark_as_resolved(self, request, queryset):
        """Mark selected anomalies as resolved."""
        count = queryset.update(status="resolved")
        self.message_user(request, f"{count} anomalies marked as resolved.")

    mark_as_resolved.short_description = "Mark selected as resolved"

    def mark_as_false_positive(self, request, queryset):
        """Mark selected anomalies as false positives."""
        count = queryset.update(status="false_positive")
        self.message_user(request, f"{count} anomalies marked as false positive.")

    mark_as_false_positive.short_description = "Mark as false positive"
