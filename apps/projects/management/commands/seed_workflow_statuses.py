"""
Management command to seed default WorkflowStatuses for EXISTING projects.

NOTE: This command populates default workflow statuses for projects that don't have them.
      These statuses are used in issue status dropdowns and board columns.

Usage:
    python manage.py seed_workflow_statuses                  # Seed all existing projects
    python manage.py seed_workflow_statuses --project=UUID   # Seed specific project
    python manage.py seed_workflow_statuses --force          # Recreate for all projects
"""

from django.core.management.base import BaseCommand

from apps.projects.models import Project, WorkflowStatus


class Command(BaseCommand):
    help = "Seed default workflow statuses for existing projects."

    def add_arguments(self, parser):
        parser.add_argument(
            "--project",
            type=str,
            help="Seed workflow statuses for a specific project UUID",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force recreate workflow statuses even if they exist",
        )

    def handle(self, *args, **options):
        project_id = options.get("project")
        force = options.get("force")

        # Default workflow statuses based on Scrum/Agile best practices
        DEFAULT_WORKFLOW_STATUSES = [
            {
                "name": "To Do",
                "category": "to_do",
                "description": "Work that has not been started",
                "color": "#6B7280",  # Gray
                "order": 0,
                "is_initial": True,
                "is_final": False,
            },
            {
                "name": "In Progress",
                "category": "in_progress",
                "description": "Work that is actively being worked on",
                "color": "#3B82F6",  # Blue
                "order": 1,
                "is_initial": False,
                "is_final": False,
            },
            {
                "name": "Done",
                "category": "done",
                "description": "Work that has been completed",
                "color": "#10B981",  # Green
                "order": 2,
                "is_initial": False,
                "is_final": True,
            },
        ]

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

        for project in projects:
            self.stdout.write(f"\n📁 Project: {project.name} ({project.key})")

            # Check if project already has workflow statuses
            existing_count = WorkflowStatus.objects.filter(project=project).count()

            if existing_count > 0 and not force:
                self.stdout.write(
                    self.style.WARNING(
                        f"   ⏭️  Skipping - already has {existing_count} workflow statuses"
                    )
                )
                skipped_count += 1
                continue

            # Create or update workflow statuses
            for status_data in DEFAULT_WORKFLOW_STATUSES:
                name = status_data["name"]

                if force:
                    # Update existing or create new
                    status, created = WorkflowStatus.objects.update_or_create(
                        project=project,
                        name=name,
                        defaults={
                            "category": status_data["category"],
                            "description": status_data["description"],
                            "color": status_data["color"],
                            "order": status_data["order"],
                            "is_initial": status_data["is_initial"],
                            "is_final": status_data["is_final"],
                            "is_active": True,
                        },
                    )
                else:
                    # Only create if doesn't exist
                    status, created = WorkflowStatus.objects.get_or_create(
                        project=project,
                        name=name,
                        defaults={
                            "category": status_data["category"],
                            "description": status_data["description"],
                            "color": status_data["color"],
                            "order": status_data["order"],
                            "is_initial": status_data["is_initial"],
                            "is_final": status_data["is_final"],
                            "is_active": True,
                        },
                    )

                if created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"   ✅ Created: {status.name} ({status.category})"
                        )
                    )
                    created_count += 1
                else:
                    if force:
                        self.stdout.write(
                            self.style.WARNING(
                                f"   🔄 Updated: {status.name} ({status.category})"
                            )
                        )
                        updated_count += 1
                    else:
                        self.stdout.write(
                            f"   ⏭️  Exists: {status.name} ({status.category})"
                        )

        # Summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("✅ SEEDING COMPLETE"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"Created: {created_count} workflow statuses")
        if force:
            self.stdout.write(f"Updated: {updated_count} workflow statuses")
        self.stdout.write(f"Skipped: {skipped_count} projects")
        self.stdout.write("=" * 60 + "\n")
