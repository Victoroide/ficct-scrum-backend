"""
Management command to diagnose ML model issues.

Usage:
    python manage.py diagnose_ml_model --model-id <uuid>
    python manage.py diagnose_ml_model --type effort_prediction
"""

import io

from django.core.management.base import BaseCommand, CommandError

import joblib

from apps.ml.models import MLModel
from apps.ml.services.s3_model_storage import S3ModelStorageService


class Command(BaseCommand):
    help = "Diagnose ML model configuration and accessibility"

    def add_arguments(self, parser):
        parser.add_argument(
            "--model-id",
            type=str,
            help="Specific model UUID to diagnose",
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
            help="Model type to diagnose",
        )

    def handle(self, *args, **options):
        """Execute command."""
        model_id = options.get("model_id")
        model_type = options.get("type")

        if not model_id and not model_type:
            raise CommandError("You must specify either --model-id or --type")

        if model_id:
            self._diagnose_by_id(model_id)
        else:
            self._diagnose_by_type(model_type)

    def _diagnose_by_id(self, model_id):
        """Diagnose specific model by ID."""
        self.stdout.write(self.style.HTTP_INFO(f"\n{'='*80}"))
        self.stdout.write(
            self.style.HTTP_INFO(f"DIAGNOSING MODEL: {model_id}".center(80))
        )
        self.stdout.write(self.style.HTTP_INFO(f"{'='*80}\n"))

        # Step 1: Check if model exists in database
        self.stdout.write(self.style.WARNING("Step 1: Database Record Check"))
        self.stdout.write("-" * 80)

        try:
            model = MLModel.objects.get(id=model_id)
            self.stdout.write(self.style.SUCCESS("✓ Model found in database"))
        except MLModel.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"✗ Model {model_id} NOT FOUND in database")
            )
            return

        # Step 2: Display model details
        self.stdout.write(f"\n{self.style.WARNING('Step 2: Model Details')}")
        self.stdout.write("-" * 80)

        self.stdout.write(f"ID:                {model.id}")
        self.stdout.write(f"Name:              {model.name or 'N/A'}")
        self.stdout.write(f"Type:              {model.model_type}")
        self.stdout.write(f"Version:           {model.version}")
        self.stdout.write(f"Status:            {model.status}")

        # Critical fields
        if model.is_active:
            self.stdout.write(
                f"Is Active:         {self.style.SUCCESS('✓ True (GOOD)')}"
            )
        else:
            self.stdout.write(
                f"Is Active:         {self.style.ERROR('✗ False (PROBLEM!)')}"
            )

        self.stdout.write(f"Training Samples:  {model.training_samples}")
        self.stdout.write(
            f"Training Date:     {model.training_date.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        # Step 3: Performance metrics
        self.stdout.write(f"\n{self.style.WARNING('Step 3: Performance Metrics')}")
        self.stdout.write("-" * 80)

        if model.r2_score:
            if model.r2_score >= 0.9:
                quality = self.style.SUCCESS("Excellent")
            elif model.r2_score >= 0.7:
                quality = self.style.WARNING("Good")
            else:
                quality = self.style.ERROR("Poor")
            self.stdout.write(f"R² Score:          {model.r2_score:.4f} ({quality})")
        else:
            self.stdout.write("R² Score:          N/A")

        if model.mae:
            self.stdout.write(f"MAE:               {model.mae:.4f}")
        if model.rmse:
            self.stdout.write(f"RMSE:              {model.rmse:.4f}")

        # Step 4: Metadata analysis
        self.stdout.write(f"\n{self.style.WARNING('Step 4: Metadata Analysis')}")
        self.stdout.write("-" * 80)

        project_id = model.metadata.get("project_id")
        if project_id:
            self.stdout.write(
                f"Project ID:        {project_id} (Project-specific model)"
            )
        else:
            self.stdout.write("Project ID:        None (Global model)")

        if model.metadata.get("feature_names"):
            self.stdout.write(
                f"Features:          {len(model.metadata['feature_names'])} features"
            )
            self.stdout.write(f"                   {model.metadata['feature_names']}")

        # Step 5: S3 configuration
        self.stdout.write(f"\n{self.style.WARNING('Step 5: S3 Storage Check')}")
        self.stdout.write("-" * 80)

        if model.s3_bucket:
            self.stdout.write(f"S3 Bucket:         {model.s3_bucket}")
        else:
            self.stdout.write(
                self.style.ERROR("S3 Bucket:         ✗ NOT SET (PROBLEM!)")
            )

        if model.s3_key:
            self.stdout.write(f"S3 Key:            {model.s3_key}")
        else:
            self.stdout.write(self.style.ERROR("S3 Key:            ✗ NOT SET (PROBLEM!)"))

        # Step 6: Try to download from S3
        if model.s3_key:
            self.stdout.write(f"\n{self.style.WARNING('Step 6: S3 Download Test')}")
            self.stdout.write("-" * 80)

            try:
                s3_service = S3ModelStorageService()
                model_bytes = s3_service.download_model(model.s3_key)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Model downloaded successfully ({len(model_bytes)} bytes)"
                    )
                )

                # Try to deserialize
                try:
                    model_bundle = joblib.load(io.BytesIO(model_bytes))
                    self.stdout.write(
                        self.style.SUCCESS("✓ Model deserialized successfully")
                    )

                    if "model" in model_bundle:
                        self.stdout.write(
                            self.style.SUCCESS("✓ Model object found in bundle")
                        )
                    else:
                        self.stdout.write(
                            self.style.ERROR(
                                "✗ Model object NOT FOUND in bundle (PROBLEM!)"
                            )
                        )

                    if "feature_names" in model_bundle:
                        self.stdout.write(
                            f"  Features: {model_bundle['feature_names']}"
                        )

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"✗ Deserialization failed: {str(e)}")
                    )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ S3 download failed: {str(e)}")
                )

        # Step 7: Recommendation
        self.stdout.write(f"\n{self.style.WARNING('Step 7: Recommendations')}")
        self.stdout.write("-" * 80)

        problems = []
        solutions = []

        if not model.is_active:
            problems.append("Model is NOT active (is_active=False)")
            solutions.append(
                f"python manage.py activate_ml_model --model-id {model.id}"
            )

        if model.status != "active":
            problems.append(f"Model status is '{model.status}' instead of 'active'")
            solutions.append("Update model.status = 'active' and model.save()")

        if not model.s3_key:
            problems.append("Model has no S3 key (model not uploaded)")
            solutions.append("Retrain the model to upload to S3")

        if problems:
            self.stdout.write(self.style.ERROR("\n⚠️  PROBLEMS FOUND:"))
            for i, problem in enumerate(problems, 1):
                self.stdout.write(f"  {i}. {problem}")

            self.stdout.write(self.style.SUCCESS("\n💡 SOLUTIONS:"))
            for i, solution in enumerate(solutions, 1):
                self.stdout.write(f"  {i}. {solution}")
        else:
            self.stdout.write(
                self.style.SUCCESS("\n✓ Model configuration looks good!")
            )

        self.stdout.write(f"\n{self.style.HTTP_INFO('='*80)}\n")

    def _diagnose_by_type(self, model_type):
        """Diagnose all models of a type."""
        self.stdout.write(self.style.HTTP_INFO(f"\n{'='*80}"))
        self.stdout.write(
            self.style.HTTP_INFO(f"DIAGNOSING {model_type.upper()} MODELS".center(80))
        )
        self.stdout.write(self.style.HTTP_INFO(f"{'='*80}\n"))

        models = MLModel.objects.filter(model_type=model_type).order_by(
            "-training_date"
        )

        if not models.exists():
            self.stdout.write(
                self.style.ERROR(f"✗ No {model_type} models found in database")
            )
            return

        self.stdout.write(f"Found {models.count()} {model_type} model(s):\n")

        active_count = 0
        for i, model in enumerate(models, 1):
            status_icon = "✓" if model.is_active else "✗"
            status_style = self.style.SUCCESS if model.is_active else self.style.ERROR

            self.stdout.write(
                f"{status_style(status_icon)} Model {i}: {model.id}"
            )
            self.stdout.write(f"   Version:    {model.version}")
            self.stdout.write(f"   Status:     {model.status}")
            self.stdout.write(f"   Is Active:  {model.is_active}")
            self.stdout.write(
                f"   R² Score:   {model.r2_score if model.r2_score else 'N/A'}"
            )
            self.stdout.write(
                f"   Trained:    {model.training_date.strftime('%Y-%m-%d %H:%M')}"
            )
            self.stdout.write(
                f"   S3 Key:     {'✓' if model.s3_key else '✗ MISSING'}"
            )
            self.stdout.write("")

            if model.is_active:
                active_count += 1

        self.stdout.write("-" * 80)
        self.stdout.write(f"Active models: {active_count} / {models.count()}")

        if active_count == 0:
            self.stdout.write(
                self.style.ERROR(
                    "\n⚠️  NO ACTIVE MODELS! Predictions will fail."
                )
            )
            latest = models.first()
            if latest:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n💡 To activate the latest model, run:\n"
                        f"   python manage.py activate_ml_model --model-id {latest.id}"
                    )
                )
        elif active_count > 1:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠️  Multiple active models ({active_count}). "
                    f"This may cause confusion."
                )
            )
            self.stdout.write(
                "\n💡 Consider deactivating old models:\n"
                "   python manage.py activate_ml_model --type "
                f"{model_type} --latest --deactivate-others"
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "\n✓ Configuration looks good! One active model found."
                )
            )

        self.stdout.write(f"\n{self.style.HTTP_INFO('='*80)}\n")
