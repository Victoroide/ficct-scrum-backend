"""
Management command to activate ML models.

Usage:
    python manage.py activate_ml_model --model-id <uuid>
    python manage.py activate_ml_model --type effort_prediction --latest
    python manage.py activate_ml_model --type effort_prediction --all
"""

from django.core.management.base import BaseCommand, CommandError

from apps.ml.models import MLModel


class Command(BaseCommand):
    help = "Activate ML models for predictions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--model-id",
            type=str,
            help="Specific model UUID to activate",
        )
        parser.add_argument(
            "--type",
            type=str,
            choices=[
                "effort_prediction",
                "sprint_duration",
                "story_points",
                "task_assignment",
                "risk_detection",
                "anomaly_detection",
            ],
            help="Model type to activate",
        )
        parser.add_argument(
            "--latest",
            action="store_true",
            help="Activate the latest model of the specified type",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Activate all models of the specified type",
        )
        parser.add_argument(
            "--deactivate-others",
            action="store_true",
            help="Deactivate other models of the same type",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="List all models without activating",
        )

    def handle(self, *args, **options):
        """Execute command."""
        model_id = options.get("model_id")
        model_type = options.get("type")
        latest = options.get("latest")
        all_models = options.get("all")
        deactivate_others = options.get("deactivate_others")
        list_only = options.get("list")

        # List mode
        if list_only:
            self._list_models(model_type)
            return

        # Validation
        if not model_id and not model_type:
            raise CommandError(
                "You must specify either --model-id or --type (with --latest or --all)"
            )

        if model_id and (latest or all_models or model_type):
            raise CommandError(
                "--model-id cannot be used with --type, --latest, or --all"
            )

        if model_type and not (latest or all_models):
            raise CommandError("--type requires either --latest or --all")

        # Activate by ID
        if model_id:
            self._activate_by_id(model_id, deactivate_others)
            return

        # Activate by type
        if model_type:
            if latest:
                self._activate_latest(model_type, deactivate_others)
            elif all_models:
                self._activate_all(model_type)

    def _list_models(self, model_type=None):
        """List all models."""
        if model_type:
            models = MLModel.objects.filter(model_type=model_type).order_by(
                "-training_date"
            )
            self.stdout.write(f"\n{model_type.upper()} Models:")
        else:
            models = MLModel.objects.all().order_by("model_type", "-training_date")
            self.stdout.write("\nAll ML Models:")

        self.stdout.write("-" * 80)

        if not models.exists():
            self.stdout.write(self.style.WARNING("No models found."))
            return

        for model in models:
            status_icon = "✓" if model.is_active else "✗"
            status_color = self.style.SUCCESS if model.is_active else self.style.ERROR

            project_id = model.metadata.get("project_id", "global")

            self.stdout.write(
                f"{status_color(status_icon)} {model.id} | "
                f"Type: {model.model_type} | "
                f"Version: {model.version} | "
                f"Status: {model.status} | "
                f"Active: {model.is_active} | "
                f"Project: {project_id} | "
                f"R²: {model.r2_score or 'N/A'} | "
                f"Trained: {model.training_date.strftime('%Y-%m-%d %H:%M')}"
            )

        self.stdout.write("-" * 80)
        self.stdout.write(
            f"Total: {models.count()} models "
            f"({models.filter(is_active=True).count()} active)"
        )

    def _activate_by_id(self, model_id, deactivate_others):
        """Activate specific model by ID."""
        try:
            model = MLModel.objects.get(id=model_id)
        except MLModel.DoesNotExist:
            raise CommandError(f"Model with ID {model_id} not found")

        # Deactivate others if requested
        if deactivate_others:
            deactivated = MLModel.objects.filter(
                model_type=model.model_type, is_active=True
            ).exclude(id=model_id)

            count = deactivated.count()
            if count > 0:
                deactivated.update(is_active=False, status="deprecated")
                self.stdout.write(
                    self.style.WARNING(
                        f"Deactivated {count} other {model.model_type} model(s)"
                    )
                )

        # Activate the model
        model.is_active = True
        model.status = "active"
        model.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Model activated successfully!\n"
                f"  ID: {model.id}\n"
                f"  Type: {model.model_type}\n"
                f"  Version: {model.version}\n"
                f"  R² Score: {model.r2_score or 'N/A'}\n"
                f"  Training Samples: {model.training_samples}\n"
                f"  Project: {model.metadata.get('project_id', 'global')}\n"
                f"  S3 Path: {model.s3_key}\n"
            )
        )

    def _activate_latest(self, model_type, deactivate_others):
        """Activate the latest model of a type."""
        model = (
            MLModel.objects.filter(model_type=model_type)
            .order_by("-training_date")
            .first()
        )

        if not model:
            raise CommandError(f"No models found for type: {model_type}")

        # Deactivate others if requested
        if deactivate_others:
            deactivated = MLModel.objects.filter(
                model_type=model_type, is_active=True
            ).exclude(id=model.id)

            count = deactivated.count()
            if count > 0:
                deactivated.update(is_active=False, status="deprecated")
                self.stdout.write(
                    self.style.WARNING(f"Deactivated {count} older model(s)")
                )

        # Activate the model
        model.is_active = True
        model.status = "active"
        model.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Latest model activated!\n"
                f"  ID: {model.id}\n"
                f"  Type: {model.model_type}\n"
                f"  Version: {model.version}\n"
                f"  R² Score: {model.r2_score or 'N/A'}\n"
                f"  Trained: {model.training_date}\n"
            )
        )

    def _activate_all(self, model_type):
        """Activate all models of a type."""
        models = MLModel.objects.filter(model_type=model_type)

        if not models.exists():
            raise CommandError(f"No models found for type: {model_type}")

        count = models.update(is_active=True, status="active")

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Activated {count} {model_type} model(s) successfully!"
            )
        )
