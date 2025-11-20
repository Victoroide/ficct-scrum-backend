"""
Management command to train ML models.

Usage:
    python manage.py train_ml_model effort_prediction
    python manage.py train_ml_model effort_prediction --project=<uuid>
    python manage.py train_ml_model story_points --project=<uuid>
"""

import logging

from django.core.management.base import BaseCommand, CommandError

from apps.ml.services import ModelTrainer

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Train ML models for predictions"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "model_type",
            type=str,
            choices=[
                "effort_prediction",
                "story_points",
                "sprint_duration",
                "task_assignment",
            ],
            help="Type of model to train",
        )
        parser.add_argument(
            "--project",
            type=str,
            default=None,
            help="Project UUID for project-specific model (optional for global model)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force retraining even if model is recent",
        )

    def handle(self, *args, **options):
        """Execute command."""
        model_type = options["model_type"]
        project_id = options.get("project")
        force = options.get("force", False)

        self.stdout.write(
            self.style.WARNING(f"\nStarting training for {model_type} model...")
        )

        if project_id:
            self.stdout.write(f"  Project ID: {project_id}")
        else:
            self.stdout.write("  Scope: Global model")

        try:
            trainer = ModelTrainer()

            # Check if retraining is needed (unless forced)
            if not force and project_id:
                from apps.ml.models import MLModel

                existing_model = MLModel.objects.filter(
                    model_type=model_type,
                    is_active=True,
                    metadata__project_id=project_id,
                ).first()

                if existing_model and not trainer.should_retrain(existing_model):
                    self.stdout.write(
                        self.style.WARNING(
                            f"\nModel {existing_model.name} is recent and has "
                            f"sufficient accuracy. Use --force to retrain anyway."
                        )
                    )
                    return

            # Train the model
            if model_type == "effort_prediction":
                ml_model = trainer.train_effort_prediction_model(
                    project_id=project_id,
                    user=None,
                )
            elif model_type == "story_points":
                ml_model = trainer.train_story_points_model(
                    project_id=project_id,
                    user=None,
                )
            else:
                raise CommandError(f"Training for {model_type} not yet implemented")

            if ml_model:
                self.stdout.write(
                    self.style.SUCCESS(f"\n✓ Successfully trained {ml_model.name}:")
                )
                self.stdout.write(f"  Model ID: {ml_model.id}")
                self.stdout.write(f"  Version: {ml_model.version}")
                self.stdout.write(f"  Training samples: {ml_model.training_samples}")

                if ml_model.mae:
                    self.stdout.write(f"  MAE: {ml_model.mae:.2f}")
                if ml_model.rmse:
                    self.stdout.write(f"  RMSE: {ml_model.rmse:.2f}")
                if ml_model.r2_score:
                    self.stdout.write(f"  R² Score: {ml_model.r2_score:.3f}")

                self.stdout.write(
                    f"  S3 Path: s3://{ml_model.s3_bucket}/{ml_model.s3_key}"
                )
                self.stdout.write(
                    self.style.SUCCESS("\n✓ Model training completed successfully!")
                )
            else:
                self.stdout.write(
                    self.style.ERROR("\n✗ Training failed: Insufficient training data")
                )
                self.stdout.write(
                    "  Minimum required samples: " f"{trainer.min_samples}"
                )

        except Exception as e:
            logger.exception(f"Error training model: {str(e)}")
            raise CommandError(f"Training failed: {str(e)}")
