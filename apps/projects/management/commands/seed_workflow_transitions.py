"""
Management command to seed default WorkflowTransitions for EXISTING projects.

NOTE: This command creates the transition rules between workflow statuses.
      Without these transitions, users cannot change issue status in the UI.

Usage:
    python manage.py seed_workflow_transitions                  # Seed all existing projects
    python manage.py seed_workflow_transitions --project=UUID   # Seed specific project
    python manage.py seed_workflow_transitions --force          # Recreate for all projects
"""

from django.core.management.base import BaseCommand

from apps.projects.models import Project, WorkflowStatus, WorkflowTransition


class Command(BaseCommand):
    help = "Seed default workflow transitions for existing projects."

    def add_arguments(self, parser):
        parser.add_argument(
            "--project",
            type=str,
            help="Seed workflow transitions for a specific project UUID",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force recreate workflow transitions even if they exist",
        )

    def handle(self, *args, **options):
        project_id = options.get("project")
        force = options.get("force")

        # Get projects to seed
        if project_id:
            try:
                projects = [Project.objects.get(id=project_id)]
                self.stdout.write(
                    self.style.SUCCESS(f"Processing project: {projects[0].name}")
                )
            except Project.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"Project with ID {project_id} not found")
                )
                return
        else:
            projects = Project.objects.all()
            self.stdout.write(
                self.style.SUCCESS(f"Processing {projects.count()} projects")
            )

        created_count = 0
        updated_count = 0
        skipped_count = 0
        error_count = 0

        for project in projects:
            self.stdout.write(f"\n📁 Project: {project.name} ({project.key})")

            # Get workflow statuses for this project
            try:
                to_do = WorkflowStatus.objects.get(
                    project=project, category="to_do", is_active=True
                )
                in_progress = WorkflowStatus.objects.get(
                    project=project, category="in_progress", is_active=True
                )
                done = WorkflowStatus.objects.get(
                    project=project, category="done", is_active=True
                )
            except WorkflowStatus.DoesNotExist as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"   ❌ Error: Missing workflow statuses. "
                        f"Run 'python manage.py seed_workflow_statuses' first."
                    )
                )
                error_count += 1
                continue

            # Check if project already has workflow transitions
            existing_count = WorkflowTransition.objects.filter(
                project=project
            ).count()

            if existing_count > 0 and not force:
                self.stdout.write(
                    self.style.WARNING(
                        f"   ⏭️  Skipping - already has {existing_count} workflow transitions"
                    )
                )
                skipped_count += 1
                continue

            # Default workflow transitions based on Scrum/Agile best practices
            transitions_to_create = [
                {
                    "name": "Start Work",
                    "from_status": to_do,
                    "to_status": in_progress,
                    "description": "Move task to in progress when work begins",
                },
                {
                    "name": "Complete",
                    "from_status": in_progress,
                    "to_status": done,
                    "description": "Mark task as done when work is completed",
                },
                {
                    "name": "Reopen",
                    "from_status": in_progress,
                    "to_status": to_do,
                    "description": "Move task back to to do if work cannot continue",
                },
                {
                    "name": "Reopen from Done",
                    "from_status": done,
                    "to_status": in_progress,
                    "description": "Reopen completed task if issues are found",
                },
                {
                    "name": "Reopen to Backlog",
                    "from_status": done,
                    "to_status": to_do,
                    "description": "Move completed task back to backlog",
                },
            ]

            # Create or update workflow transitions
            for transition_data in transitions_to_create:
                name = transition_data["name"]
                from_status = transition_data["from_status"]
                to_status = transition_data["to_status"]

                if force:
                    # Update existing or create new
                    transition, created = WorkflowTransition.objects.update_or_create(
                        project=project,
                        from_status=from_status,
                        to_status=to_status,
                        defaults={
                            "name": name,
                            "is_active": True,
                            "conditions": {},
                            "validators": {},
                            "post_functions": {},
                        },
                    )
                else:
                    # Only create if doesn't exist
                    transition, created = WorkflowTransition.objects.get_or_create(
                        project=project,
                        from_status=from_status,
                        to_status=to_status,
                        defaults={
                            "name": name,
                            "is_active": True,
                            "conditions": {},
                            "validators": {},
                            "post_functions": {},
                        },
                    )

                if created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"   ✅ Created: {transition.name} "
                            f"({from_status.name} → {to_status.name})"
                        )
                    )
                    created_count += 1
                else:
                    if force:
                        self.stdout.write(
                            self.style.WARNING(
                                f"   🔄 Updated: {transition.name} "
                                f"({from_status.name} → {to_status.name})"
                            )
                        )
                        updated_count += 1
                    else:
                        self.stdout.write(
                            f"   ⏭️  Exists: {transition.name} "
                            f"({from_status.name} → {to_status.name})"
                        )

        # Summary
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("✅ WORKFLOW TRANSITIONS SEEDING COMPLETE"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"Created: {created_count} workflow transitions")
        if force:
            self.stdout.write(f"Updated: {updated_count} workflow transitions")
        self.stdout.write(f"Skipped: {skipped_count} projects")
        if error_count > 0:
            self.stdout.write(
                self.style.ERROR(
                    f"Errors: {error_count} projects (missing workflow statuses)"
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    "  💡 Run: python manage.py seed_workflow_statuses"
                )
            )
        self.stdout.write("=" * 70 + "\n")
