"""
Management command to list ML models.

Usage:
    python manage.py list_ml_models
    python manage.py list_ml_models --type=effort_prediction
    python manage.py list_ml_models --active-only
"""

from django.core.management.base import BaseCommand

from apps.ml.models import MLModel


class Command(BaseCommand):
    help = "List ML models in database and S3"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--type",
            type=str,
            default=None,
            help="Filter by model type",
        )
        parser.add_argument(
            "--active-only",
            action="store_true",
            help="Show only active models",
        )
        parser.add_argument(
            "--project",
            type=str,
            default=None,
            help="Filter by project ID",
        )

    def handle(self, *args, **options):
        """Execute command."""
        model_type = options.get("type")
        active_only = options.get("active_only", False)
        project_id = options.get("project")

        # Build queryset
        queryset = MLModel.objects.all()

        if model_type:
            queryset = queryset.filter(model_type=model_type)

        if active_only:
            queryset = queryset.filter(is_active=True, status="active")

        if project_id:
            queryset = queryset.filter(metadata__project_id=project_id)

        queryset = queryset.order_by("-training_date")

        # Display results
        self.stdout.write(
            self.style.WARNING(f"\nML Models ({queryset.count()} found):")
        )
        self.stdout.write("-" * 100)

        if not queryset.exists():
            self.stdout.write(self.style.WARNING("  No models found."))
            self.stdout.write(
                "\n  Train a model with: python manage.py train_ml_model effort_prediction"  # noqa: E501
            )
            return

        for model in queryset:
            # Status indicator
            if model.is_active and model.status == "active":
                status_str = self.style.SUCCESS("● ACTIVE")
            elif model.status == "training":
                status_str = self.style.WARNING("◐ TRAINING")
            elif model.status == "deprecated":
                status_str = self.style.ERROR("○ DEPRECATED")
            else:
                status_str = self.style.ERROR("✗ FAILED")

            self.stdout.write(f"\n{status_str}")
            self.stdout.write(f"  ID: {model.id}")
            self.stdout.write(f"  Name: {model.name}")
            self.stdout.write(f"  Type: {model.get_model_type_display()}")
            self.stdout.write(f"  Version: {model.version}")
            self.stdout.write(
                f"  Training Date: {model.training_date.strftime('%Y-%m-%d %H:%M')}"
            )
            self.stdout.write(f"  Training Samples: {model.training_samples}")

            # Project scope
            project_id_from_metadata = (
                model.metadata.get("project_id") if model.metadata else None
            )
            if project_id_from_metadata:
                self.stdout.write(
                    f"  Scope: Project-specific ({project_id_from_metadata})"
                )
            else:
                self.stdout.write("  Scope: Global")

            # Performance metrics
            if model.mae is not None:
                self.stdout.write(f"  MAE: {model.mae:.2f}")
            if model.rmse is not None:
                self.stdout.write(f"  RMSE: {model.rmse:.2f}")
            if model.r2_score is not None:
                self.stdout.write(f"  R² Score: {model.r2_score:.3f}")

            # S3 location
            if model.s3_key:
                self.stdout.write(f"  S3: s3://{model.s3_bucket}/{model.s3_key}")

            # Trained by
            if model.trained_by:
                self.stdout.write(
                    f"  Trained By: {model.trained_by.get_full_name() or model.trained_by.username}"  # noqa: E501
                )

        self.stdout.write("\n" + "-" * 100)
        self.stdout.write(self.style.SUCCESS(f"\nTotal: {queryset.count()} model(s)"))
