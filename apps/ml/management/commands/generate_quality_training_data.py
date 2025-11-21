"""
Django management command to generate high-quality, coherent training data for ML models.  # noqa: E501

This command creates realistic software development scenarios with temporal coherence,
skill-task matching, and authentic variance to enable ML models to learn meaningful patterns.  # noqa: E501

Usage:
    python manage.py generate_quality_training_data \\
        --workspace 933607a1-36a8-49e1-991c-fe06350cba26 \\
        --user 11 \\
        --preserve-project 23b6e5cf-2de5-4d7d-b420-0d6ee9f47cce \\
        --confirm
"""

import random
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.projects.models import (
    Issue,
    IssueType,
    Project,
    Sprint,
    WorkflowStatus,
)
from apps.workspaces.models import Workspace

# Import generation helper functions
from .generation_helpers import (
    create_dependencies_impl,
    create_projects_impl,
    generate_issues_impl,
    generate_sprints_impl,
    generate_team_members_impl,
    inject_anomalies_impl,
    log_effort_data_impl,
)

User = get_user_model()

# Realistic project archetypes for a software organization
PROJECT_ARCHETYPES = [
    {
        "name": "Admin Dashboard",
        "key": "ADMIN",
        "description": "Internal administration and management dashboard for system operators",  # noqa: E501
        "team_size": 5,
        "duration_weeks": 12,
        "complexity": "medium",
        "issue_count": 80,
    },
    {
        "name": "Mobile Application",
        "key": "MOBILE",
        "description": "Cross-platform mobile app for iOS and Android",
        "team_size": 6,
        "duration_weeks": 16,
        "complexity": "high",
        "issue_count": 120,
    },
    {
        "name": "Payment Integration",
        "key": "PAYMENT",
        "description": "Secure payment gateway integration and processing system",
        "team_size": 4,
        "duration_weeks": 8,
        "complexity": "high",
        "issue_count": 60,
    },
    {
        "name": "Analytics Platform",
        "key": "ANALYTICS",
        "description": "Data analytics and reporting dashboard for business metrics",
        "team_size": 5,
        "duration_weeks": 14,
        "complexity": "medium",
        "issue_count": 90,
    },
    {
        "name": "API Gateway",
        "key": "API",
        "description": "RESTful API gateway for microservices architecture",
        "team_size": 4,
        "duration_weeks": 10,
        "complexity": "high",
        "issue_count": 70,
    },
]

# Realistic team roles with primary skills
TEAM_ROLES = [
    {
        "role": "Senior Backend Engineer",
        "skills": ["backend", "database", "api"],
        "velocity_factor": 1.3,
        "estimation_accuracy": 0.85,
    },
    {
        "role": "Frontend Developer",
        "skills": ["frontend", "ui", "design"],
        "velocity_factor": 1.1,
        "estimation_accuracy": 0.80,
    },
    {
        "role": "Full Stack Developer",
        "skills": ["backend", "frontend", "api"],
        "velocity_factor": 1.0,
        "estimation_accuracy": 0.75,
    },
    {
        "role": "QA Engineer",
        "skills": ["testing", "qa", "automation"],
        "velocity_factor": 0.9,
        "estimation_accuracy": 0.90,
    },
    {
        "role": "DevOps Engineer",
        "skills": ["devops", "infrastructure", "deployment"],
        "velocity_factor": 1.2,
        "estimation_accuracy": 0.88,
    },
    {
        "role": "UI/UX Designer",
        "skills": ["design", "ui", "frontend"],
        "velocity_factor": 0.8,
        "estimation_accuracy": 0.70,
    },
    {
        "role": "Junior Developer",
        "skills": ["backend", "frontend"],
        "velocity_factor": 0.7,
        "estimation_accuracy": 0.60,
    },
]

# Issue templates with realistic effort distributions
ISSUE_TEMPLATES = {
    "epic": {
        "story_points_range": (13, 21),
        "hours_per_point": 8.0,
        "variance": 0.4,
        "subtask_count": (4, 8),
    },
    "story": {
        "story_points_range": (3, 8),
        "hours_per_point": 6.0,
        "variance": 0.3,
        "subtask_count": (2, 5),
    },
    "task": {
        "story_points_range": (1, 5),
        "hours_per_point": 4.0,
        "variance": 0.25,
        "subtask_count": (0, 3),
    },
    "bug": {
        "story_points_range": (1, 3),
        "hours_per_point": 3.0,
        "variance": 0.5,  # Bugs have high variance
        "subtask_count": (0, 2),
    },
}


class Command(BaseCommand):
    help = "Generate high-quality, coherent training data for ML models"

    def __init__(self):
        super().__init__()
        self.workspace: Optional[Workspace] = None
        self.user: Optional[User] = None
        self.preserve_project: Optional[Project] = None
        self.generated_projects: List[Project] = []
        self.generated_sprints: List[Sprint] = []
        self.generated_issues: List[Issue] = []
        self.team_members: Dict[str, Any] = {}
        self.issue_types: Dict[str, IssueType] = {}
        self.workflow_statuses: Dict[str, WorkflowStatus] = {}
        self.verbose_logging = False

    def add_arguments(self, parser):
        parser.add_argument(
            "--workspace",
            type=str,
            required=True,
            help="Workspace UUID (must be 933607a1-36a8-49e1-991c-fe06350cba26)",
        )
        parser.add_argument(
            "--user",
            type=int,
            required=True,
            help="User ID (must be 11)",
        )
        parser.add_argument(
            "--preserve-project",
            type=str,
            required=True,
            help="Project UUID to preserve (must be 23b6e5cf-2de5-4d7d-b420-0d6ee9f47cce)",  # noqa: E501
        )
        parser.add_argument(
            "--num-projects",
            type=int,
            default=5,
            help="Number of new projects to generate (default: 5)",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Required flag to execute (without it, runs in dry-run mode)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Enable verbose logging",
        )
        parser.add_argument(
            "--skip-vectorization",
            action="store_true",
            default=True,
            help="Skip Pinecone vectorization during generation (recommended for training data). "  # noqa: E501
            "Vectorization is for semantic search, not ML training. Default: True",
        )

    def handle(self, *args, **options):
        """Main command execution."""
        self.verbose_logging = options["verbose"]
        skip_vectorization = options["skip_vectorization"]

        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("ML TRAINING DATA GENERATION"))
        self.stdout.write("=" * 80)
        self.stdout.write()

        # Phase 1: Validation
        self._validate_constraints(options)

        # Phase 2: Analysis
        self._analyze_current_state()

        # Phase 3: Planning
        generation_plan = self._create_generation_plan(options["num_projects"])

        # Phase 4: Confirmation
        if not options["confirm"]:
            self._show_dry_run_summary(generation_plan)
            return

        # Disable Pinecone auto-indexing if requested (default for training data)
        disconnected_signals = []
        if skip_vectorization:
            self.stdout.write()
            self.stdout.write(
                self.style.WARNING(
                    "[INFO] Vectorization disabled (--skip-vectorization=True)"
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    "[INFO] ML training uses PostgreSQL data, not vector embeddings"
                )
            )
            self.stdout.write()
            disconnected_signals = self._disconnect_vectorization_signals()

        # Phase 5: Execution
        try:
            with transaction.atomic():
                self._execute_generation(generation_plan)
                self._validate_training_data_quality()

            self.stdout.write()
            self.stdout.write(self.style.SUCCESS("=" * 80))
            self.stdout.write(
                self.style.SUCCESS("DATA GENERATION COMPLETED SUCCESSFULLY")
            )
            self.stdout.write(self.style.SUCCESS("=" * 80))
            self._show_post_generation_guide()

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\nERROR: {str(e)}"))
            self.stdout.write(self.style.ERROR("All changes have been rolled back."))
            raise CommandError(f"Data generation failed: {str(e)}")
        finally:
            # Reconnect signals if they were disconnected
            if disconnected_signals:
                self._reconnect_vectorization_signals(disconnected_signals)

    def _validate_constraints(self, options: Dict[str, Any]) -> None:
        """Validate all preservation constraints."""
        self.stdout.write("PHASE 1: VALIDATING CONSTRAINTS")
        self.stdout.write("-" * 80)

        # Validate workspace
        workspace_uuid = options["workspace"]
        expected_workspace = "933607a1-36a8-49e1-991c-fe06350cba26"
        if workspace_uuid != expected_workspace:
            raise CommandError(
                f"Invalid workspace UUID. Expected: {expected_workspace}, Got: {workspace_uuid}"  # noqa: E501
            )

        try:
            self.workspace = Workspace.objects.get(id=workspace_uuid)
            self.stdout.write(f"[OK] Workspace: {self.workspace.name}")
        except Workspace.DoesNotExist:
            raise CommandError(f"Workspace {workspace_uuid} not found")

        # Validate user
        user_id = options["user"]
        if user_id != 11:
            raise CommandError(f"Invalid user ID. Expected: 11, Got: {user_id}")

        try:
            self.user = User.objects.get(id=user_id)
            self.stdout.write(f"[OK] User: {self.user.email}")
        except User.DoesNotExist:
            raise CommandError(f"User {user_id} not found")

        # Validate preserve project
        preserve_uuid = options["preserve_project"]
        expected_preserve = "23b6e5cf-2de5-4d7d-b420-0d6ee9f47cce"
        if preserve_uuid != expected_preserve:
            raise CommandError(
                f"Invalid preserve project UUID. Expected: {expected_preserve}, Got: {preserve_uuid}"  # noqa: E501
            )

        try:
            self.preserve_project = Project.objects.get(id=preserve_uuid)
            if str(self.preserve_project.workspace.id) != workspace_uuid:
                raise CommandError(
                    "Preserve project does not belong to specified workspace"
                )
            self.stdout.write(f"[OK] Preserve project: {self.preserve_project.name}")
        except Project.DoesNotExist:
            raise CommandError(f"Project {preserve_uuid} not found")

        self.stdout.write()

    def _analyze_current_state(self) -> None:
        """Analyze current database state."""
        self.stdout.write("PHASE 2: ANALYZING CURRENT STATE")
        self.stdout.write("-" * 80)

        # Count existing data
        existing_projects = Project.objects.filter(workspace=self.workspace).count()
        existing_sprints = Sprint.objects.filter(
            project__workspace=self.workspace
        ).count()
        existing_issues = Issue.objects.filter(
            project__workspace=self.workspace
        ).count()

        self.stdout.write(f"Existing projects: {existing_projects}")
        self.stdout.write(f"Existing sprints: {existing_sprints}")
        self.stdout.write(f"Existing issues: {existing_issues}")
        self.stdout.write()

        # Check for other projects
        other_projects = Project.objects.filter(workspace=self.workspace).exclude(
            id=self.preserve_project.id
        )

        if other_projects.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"WARNING: Found {other_projects.count()} other project(s) in workspace"  # noqa: E501
                )
            )
            for project in other_projects:
                self.stdout.write(f"  - {project.name} ({project.key})")
            self.stdout.write()
        else:
            self.stdout.write("[OK] No other projects found - workspace is clean")
            self.stdout.write()

    def _create_generation_plan(self, num_projects: int) -> Dict[str, Any]:
        """Create detailed generation plan."""
        self.stdout.write("PHASE 3: CREATING GENERATION PLAN")
        self.stdout.write("-" * 80)

        # Select project archetypes
        selected_archetypes = random.sample(
            PROJECT_ARCHETYPES, min(num_projects, len(PROJECT_ARCHETYPES))
        )

        plan = {
            "projects": selected_archetypes,
            "total_sprints": sum(p["duration_weeks"] // 2 for p in selected_archetypes),
            "total_issues": sum(p["issue_count"] for p in selected_archetypes),
            "timeline_start": timezone.now() - timedelta(weeks=20),
            "timeline_end": timezone.now() + timedelta(weeks=4),
        }

        self.stdout.write(f"Projects to generate: {len(selected_archetypes)}")
        self.stdout.write(f"Estimated sprints: {plan['total_sprints']}")
        self.stdout.write(f"Estimated issues: {plan['total_issues']}")
        self.stdout.write(
            f"Timeline: {plan['timeline_start'].date()} to {plan['timeline_end'].date()}"  # noqa: E501
        )
        self.stdout.write()

        return plan

    def _show_dry_run_summary(self, plan: Dict[str, Any]) -> None:
        """Show what would be generated without --confirm flag."""
        self.stdout.write(self.style.WARNING("=" * 80))
        self.stdout.write(self.style.WARNING("DRY RUN MODE (use --confirm to execute)"))
        self.stdout.write(self.style.WARNING("=" * 80))
        self.stdout.write()

        self.stdout.write("PRESERVATION:")
        self.stdout.write(f"  [OK] {self.preserve_project.name} will be PRESERVED")
        self.stdout.write()

        self.stdout.write("GENERATION:")
        for archetype in plan["projects"]:
            self.stdout.write(f"  - {archetype['name']} ({archetype['key']})")
            self.stdout.write(f"      Complexity: {archetype['complexity']}")
            self.stdout.write(f"      Issues: ~{archetype['issue_count']}")
            self.stdout.write(f"      Duration: {archetype['duration_weeks']} weeks")
        self.stdout.write()

        self.stdout.write("To execute, add --confirm flag:")
        self.stdout.write(
            self.style.SUCCESS("  python manage.py generate_quality_training_data \\")
        )
        self.stdout.write(self.style.SUCCESS(f"    --workspace {self.workspace.id} \\"))
        self.stdout.write(self.style.SUCCESS(f"    --user {self.user.id} \\"))
        self.stdout.write(
            self.style.SUCCESS(f"    --preserve-project {self.preserve_project.id} \\")
        )
        self.stdout.write(self.style.SUCCESS("    --confirm"))

    def _execute_generation(self, plan: Dict[str, Any]) -> None:
        """Execute complete data generation within transaction."""
        self.stdout.write("PHASE 4: GENERATING DATA")
        self.stdout.write("-" * 80)

        try:
            # Step 1: Generate/Setup Team Members
            self._generate_team_members()
            self.stdout.write("[OK] Team members generated")

            # Step 2: Create Projects
            self._create_projects(plan)
            self.stdout.write(f"[OK] Created {len(self.generated_projects)} projects")

            # Step 3: Generate Sprints
            self._generate_sprints(plan)
            self.stdout.write(f"[OK] Created {len(self.generated_sprints)} sprints")

            # Step 4: Generate Issues
            self._generate_issues(plan)
            self.stdout.write(f"[OK] Created {len(self.generated_issues)} issues")

            # Step 5: Log Effort for Completed Issues
            self._log_effort_data()
            self.stdout.write("[OK] Logged effort for completed issues")

            # Step 6: Create Dependencies
            self._create_dependencies()
            self.stdout.write("[OK] Created issue dependencies")

            # Step 7: Inject Anomalies
            self._inject_anomalies()
            self.stdout.write("[OK] Injected realistic anomalies")

            self.stdout.write()
            self.stdout.write(
                self.style.SUCCESS("Data generation completed successfully")
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Generation failed: {str(e)}"))
            raise

    def _generate_team_members(self) -> None:
        """Wrapper for team member generation."""
        generate_team_members_impl(self)

    def _create_projects(self, plan: Dict[str, Any]) -> None:
        """Wrapper for project creation."""
        create_projects_impl(self, plan)

    def _generate_sprints(self, plan: Dict[str, Any]) -> None:
        """Wrapper for sprint generation."""
        generate_sprints_impl(self, plan)

    def _generate_issues(self, plan: Dict[str, Any]) -> None:
        """Wrapper for issue generation."""
        generate_issues_impl(self, plan)

    def _log_effort_data(self) -> None:
        """Wrapper for effort logging."""
        log_effort_data_impl(self)

    def _create_dependencies(self) -> None:
        """Wrapper for dependency creation."""
        create_dependencies_impl(self)

    def _inject_anomalies(self) -> None:
        """Wrapper for anomaly injection."""
        inject_anomalies_impl(self)

    def _validate_training_data_quality(self) -> None:
        """Validate that generated data meets ML training requirements."""
        self.stdout.write()
        self.stdout.write("PHASE 5: VALIDATING TRAINING DATA QUALITY")
        self.stdout.write("-" * 80)

        # Check effort prediction dataset
        effort_issues = Issue.objects.filter(
            project__workspace=self.workspace,
            status__is_final=True,
            actual_hours__isnull=False,
        ).count()

        self.stdout.write(f"Effort Prediction Dataset: {effort_issues} issues")
        if effort_issues >= 100:
            self.stdout.write(self.style.SUCCESS("  [OK] Sufficient for training"))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"  [WARNING] Need {100 - effort_issues} more issues"
                )
            )

        # Check story points dataset
        story_point_issues = Issue.objects.filter(
            project__workspace=self.workspace,
            story_points__isnull=False,
            actual_hours__isnull=False,
        ).count()

        self.stdout.write(f"Story Points Dataset: {story_point_issues} issues")
        if story_point_issues >= 60:
            self.stdout.write(self.style.SUCCESS("  [OK] Sufficient for training"))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"  [WARNING] Need {60 - story_point_issues} more issues"
                )
            )

        # Check sprint duration dataset
        completed_sprints = Sprint.objects.filter(
            project__workspace=self.workspace,
            status="completed",
        ).count()

        self.stdout.write(f"Sprint Duration Dataset: {completed_sprints} sprints")
        if completed_sprints >= 15:
            self.stdout.write(self.style.SUCCESS("  [OK] Sufficient for training"))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"  [WARNING] Need {15 - completed_sprints} more sprints"
                )
            )

    def _show_post_generation_guide(self) -> None:
        """Show step-by-step guide for training models after generation."""
        self.stdout.write()
        self.stdout.write("=" * 80)
        self.stdout.write("POST-GENERATION TRAINING GUIDE")
        self.stdout.write("=" * 80)
        self.stdout.write()

        self.stdout.write(self.style.SUCCESS("Step 1: Verify Data Quality"))
        self.stdout.write("  Run analysis script to confirm data integrity:")
        self.stdout.write("  Copy-paste command:")
        self.stdout.write(
            self.style.SUCCESS("  .venv\\Scripts\\python.exe analyze_workspace_data.py")
        )
        self.stdout.write()
        self.stdout.write("  Expected output:")
        self.stdout.write("    - Effort Prediction: [SUFFICIENT]")
        self.stdout.write("    - Story Points: [SUFFICIENT]")
        self.stdout.write("    - Sprint Duration: [SUFFICIENT]")
        self.stdout.write()

        self.stdout.write(self.style.SUCCESS("Step 2: List Generated Projects"))
        self.stdout.write("  Verify projects were created:")
        self.stdout.write(self.style.SUCCESS("  python manage.py shell"))
        self.stdout.write("  >>> from apps.projects.models import Project")
        self.stdout.write(
            f"  >>> projects = Project.objects.filter(workspace_id='{self.workspace.id}')"  # noqa: E501
        )
        self.stdout.write(
            "  >>> for p in projects: print(f'{p.key}: {p.name} - {p.issues.count()} issues')"  # noqa: E501
        )
        self.stdout.write()

        self.stdout.write(
            self.style.SUCCESS("Step 3: Check Completed Issues with Effort")
        )
        self.stdout.write("  Verify effort data was logged:")
        self.stdout.write(self.style.SUCCESS("  python manage.py shell"))
        self.stdout.write("  >>> from apps.projects.models import Issue")
        self.stdout.write(
            f"  >>> completed = Issue.objects.filter(project__workspace_id='{self.workspace.id}', status__is_final=True, actual_hours__isnull=False)"  # noqa: E501
        )
        self.stdout.write(
            "  >>> print(f'Completed issues with effort: {completed.count()}')"
        )
        self.stdout.write(
            '  >>> print(f\'Average effort: {completed.aggregate(avg=models.Avg("actual_hours"))["avg"]:.2f} hours\')'  # noqa: E501
        )
        self.stdout.write()

        self.stdout.write(self.style.SUCCESS("Step 4: Train Effort Prediction Model"))
        self.stdout.write("  Copy-paste command:")
        self.stdout.write(
            self.style.SUCCESS("  python manage.py train_ml_model effort_prediction")
        )
        self.stdout.write()
        self.stdout.write("  Expected output:")
        self.stdout.write("    - Training samples: >= 100")
        self.stdout.write("    - MAE: < 5 hours")
        self.stdout.write("    - RMSE: < 8 hours")
        self.stdout.write("    - R² Score: > 0.70")
        self.stdout.write("    - S3 upload: success")
        self.stdout.write()

        self.stdout.write(self.style.SUCCESS("Step 5: Train Story Points Model"))
        self.stdout.write("  Copy-paste command:")
        self.stdout.write(
            self.style.SUCCESS("  python manage.py train_ml_model story_points")
        )
        self.stdout.write()
        self.stdout.write("  Expected output:")
        self.stdout.write("    - Training samples: >= 60")
        self.stdout.write("    - Accuracy: > 65%")
        self.stdout.write("    - F1-score: > 0.60")
        self.stdout.write()

        self.stdout.write(self.style.SUCCESS("Step 6: List Trained Models"))
        self.stdout.write("  Copy-paste command:")
        self.stdout.write(
            self.style.SUCCESS("  python manage.py list_ml_models --active-only")
        )
        self.stdout.write()
        self.stdout.write(
            "  Expected: See effort_prediction and story_points models with 'active' status"  # noqa: E501
        )
        self.stdout.write()

        self.stdout.write(self.style.SUCCESS("Step 7: Test Prediction"))
        self.stdout.write("  Run a test prediction to verify model works:")
        self.stdout.write(self.style.SUCCESS("  python manage.py shell"))
        self.stdout.write(
            "  >>> from apps.ml.services.prediction_service import PredictionService"
        )
        self.stdout.write("  >>> service = PredictionService()")
        # Get first generated project
        if self.generated_projects:
            project = self.generated_projects[0]
            self.stdout.write("  >>> result = service.predict_effort(")
            self.stdout.write("  ...     title='Implement user authentication',")
            self.stdout.write("  ...     description='Add JWT-based authentication',")
            self.stdout.write("  ...     issue_type='story',")
            self.stdout.write(f"  ...     project_id='{project.id}'")
            self.stdout.write("  ... )")
            self.stdout.write(
                "  >>> print(f\"Predicted: {result['predicted_hours']} hours\")"
            )
            self.stdout.write(
                "  >>> print(f\"Confidence: {result['confidence']:.2%}\")"
            )
            self.stdout.write("  >>> print(f\"Method: {result['method']}\")")
        self.stdout.write()

        self.stdout.write(self.style.SUCCESS("Step 8: Run Anomaly Detection"))
        self.stdout.write("  Test anomaly detection on generated projects:")
        self.stdout.write(
            self.style.SUCCESS("  python manage.py detect_anomalies --all")
        )
        self.stdout.write()
        self.stdout.write("  Expected: Detect the injected anomalies:")
        self.stdout.write("    - Behind-schedule project (low velocity)")
        self.stdout.write("    - Scope creep sprint (added issues)")
        self.stdout.write("    - Bottleneck developer (overloaded)")
        self.stdout.write()

        self.stdout.write("=" * 80)
        self.stdout.write("VERIFICATION COMPLETE")
        self.stdout.write("=" * 80)
        self.stdout.write()
        self.stdout.write("Your ML subsystem is now ready with quality training data!")
        self.stdout.write()
        self.stdout.write("Next steps:")
        self.stdout.write("  1. Train additional model types as needed")
        self.stdout.write("  2. Test ML API endpoints via REST API")
        self.stdout.write("  3. Integrate with frontend application")
        self.stdout.write()
        self.stdout.write("Documentation:")
        self.stdout.write("  - apps/ml/README.md (Local Testing section)")
        self.stdout.write("  - ML_IMPLEMENTATION_SUMMARY.md (Complete reference)")
        self.stdout.write("  - DATA_GENERATION_SUMMARY.md (Generation details)")

    def _disconnect_vectorization_signals(self) -> List[Tuple]:
        """
        Temporarily disconnect Pinecone auto-indexing signals.

        Returns list of disconnected signals for later reconnection.
        """
        from django.db.models.signals import post_delete, post_save, pre_save

        disconnected = []

        try:
            # Import signal handlers
            from apps.ai_assistant import signals as ai_signals

            # Disconnect Issue signals
            post_save.disconnect(ai_signals.auto_index_issue, sender=Issue)
            disconnected.append(("post_save", ai_signals.auto_index_issue, Issue))

            pre_save.disconnect(ai_signals.store_issue_old_values, sender=Issue)
            disconnected.append(("pre_save", ai_signals.store_issue_old_values, Issue))

            post_delete.disconnect(ai_signals.remove_issue_from_index, sender=Issue)
            disconnected.append(
                ("post_delete", ai_signals.remove_issue_from_index, Issue)
            )

            # Disconnect Sprint signals
            post_save.disconnect(ai_signals.auto_index_sprint, sender=Sprint)
            disconnected.append(("post_save", ai_signals.auto_index_sprint, Sprint))

            pre_save.disconnect(ai_signals.store_sprint_old_values, sender=Sprint)
            disconnected.append(
                ("pre_save", ai_signals.store_sprint_old_values, Sprint)
            )

            post_delete.disconnect(ai_signals.remove_sprint_from_index, sender=Sprint)
            disconnected.append(
                ("post_delete", ai_signals.remove_sprint_from_index, Sprint)
            )

            if self.verbose_logging:
                self.stdout.write(
                    "[DEBUG] Disconnected 6 Pinecone auto-indexing signals"
                )

        except Exception as e:
            self.stdout.write(
                self.style.WARNING(
                    f"[WARNING] Could not disconnect vectorization signals: {e}"
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    "[WARNING] Generation will continue but may trigger Pinecone calls"
                )
            )

        return disconnected

    def _reconnect_vectorization_signals(self, disconnected: List[Tuple]) -> None:
        """
        Reconnect previously disconnected signals.

        Args:
            disconnected: List of (signal_type, handler, sender) tuples
        """
        from django.db.models.signals import post_delete, post_save, pre_save

        signal_map = {
            "post_save": post_save,
            "pre_save": pre_save,
            "post_delete": post_delete,
        }

        for signal_type, handler, sender in disconnected:
            try:
                signal = signal_map[signal_type]
                signal.connect(handler, sender=sender)
                if self.verbose_logging:
                    self.stdout.write(
                        f"[DEBUG] Reconnected {signal_type} signal for {sender.__name__}"  # noqa: E501
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"[ERROR] Failed to reconnect {signal_type} for {sender.__name__}: {e}"  # noqa: E501
                    )
                )
