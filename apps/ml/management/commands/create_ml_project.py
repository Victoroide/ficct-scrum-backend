"""Create project with REAL ML correlations."""
from django.core.management.base import BaseCommand
import random
from datetime import datetime, timedelta

from apps.projects.models import Project, Issue, WorkflowStatus, IssueType, Sprint
from apps.organizations.models import Organization
from apps.workspaces.models import Workspace
from apps.authentication.models import User


class Command(BaseCommand):
    help = "Create project with real ML correlations"

    def handle(self, *args, **options):
        user = User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR("No users found"))
            return

        org = Organization.objects.first()
        workspace = Workspace.objects.filter(organization=org).first()

        # Get or create project
        project, created = Project.objects.get_or_create(
            key="MLTEST",
            workspace=workspace,
            defaults={"name": "ML Training Project", "created_by": user},
        )

        if not created:
            self.stdout.write(f"Using existing project: {project.name}")
            # Delete old issues
            Issue.objects.filter(project=project).delete()
            self.stdout.write("Deleted old issues")

        # Use auto-created statuses
        done = WorkflowStatus.objects.get(project=project, is_final=True)

        # Use auto-created issue types
        bug_type = IssueType.objects.filter(
            project=project, name__icontains="bug"
        ).first()
        story_type = IssueType.objects.filter(
            project=project, name__icontains="story"
        ).first()
        task_type = IssueType.objects.filter(
            project=project, name__icontains="task"
        ).first()
        epic_type = IssueType.objects.filter(
            project=project, name__icontains="epic"
        ).first()

        # Get or create sprint
        sprint, _ = Sprint.objects.get_or_create(
            name="Sprint 1",
            project=project,
            defaults={
                "start_date": datetime.now().date(),
                "end_date": (datetime.now() + timedelta(days=14)).date(),
                "status": "completed",
                "created_by": user,
            },
        )

        self.stdout.write(f"Created project: {project.name} ({project.key})")
        self.stdout.write(f"Project ID: {project.id}")

        # Generate 200 issues with REAL correlations
        for i in range(200):
            story_points = random.choice([1, 2, 3, 5, 8, 13])

            type_choice = random.choices(
                [bug_type, story_type, task_type, epic_type], weights=[40, 35, 20, 5]
            )[0]

            # REAL correlation
            base_effort = story_points * 3.5

            if type_choice == bug_type:
                type_factor = 0.7
            elif type_choice == story_type:
                type_factor = 1.0
            elif type_choice == epic_type:
                type_factor = 2.5
            else:
                type_factor = 0.9

            variance = random.uniform(0.8, 1.2)
            actual_hours = round(base_effort * type_factor * variance, 1)

            words_count = max(3, int(actual_hours / 4) + random.randint(-2, 2))
            title_words = [
                "Fix",
                "Implement",
                "Add",
                "Update",
                "Create",
                "bug",
                "feature",
                "auth",
                "database",
                "API",
            ]
            title = " ".join(random.choices(title_words, k=words_count))

            desc_sentences = max(1, int(actual_hours / 8))
            description = " ".join(["This is a description."] * desc_sentences)

            Issue.objects.create(
                project=project,
                title=title,
                description=description,
                issue_type=type_choice,
                status=done,
                story_points=story_points,
                actual_hours=actual_hours,
                sprint=sprint,
                reporter=user,
                key=f"{project.key}-{i+1}",
            )

        self.stdout.write(self.style.SUCCESS("Created 200 issues"))
        self.stdout.write("\nTrain with:")
        self.stdout.write(
            f"python manage.py train_ml_model effort_prediction "
            f"--project={project.id}"
        )
