"""
Management command to seed default IssueTypes for EXISTING/LEGACY projects.

NOTE: New projects created after signals implementation automatically get
      IssueTypes via post_save signal. This command is only needed for:
      - Existing projects created before signals were implemented
      - Migration/seeding of legacy data
      - Manual recreation with --force flag

Usage:
    python manage.py seed_issue_types                  # Seed all existing projects
    python manage.py seed_issue_types --project=UUID   # Seed specific project
    python manage.py seed_issue_types --force          # Recreate for all projects
"""

from django.core.management.base import BaseCommand

from apps.projects.models import IssueType, Project


class Command(BaseCommand):
    help = (
        "Seed default issue types for EXISTING projects. "
        "New projects automatically get issue types via signals."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--project",
            type=str,
            help="Seed issue types for a specific project UUID",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force recreate issue types even if they exist",
        )

    def handle(self, *args, **options):
        project_id = options.get("project")
        force = options.get("force")

        # Default issue types based on Scrum/Agile best practices
        DEFAULT_ISSUE_TYPES = [
            {
                "name": "Epic",
                "category": "epic",
                "description": "A large user story that can be broken down into smaller stories",
                "icon": "epic",
                "color": "#904EE2",
                "is_default": True,
            },
            {
                "name": "Story",
                "category": "story",
                "description": "A user story representing a feature or requirement",
                "icon": "story",
                "color": "#63BA3C",
                "is_default": True,
            },
            {
                "name": "Task",
                "category": "task",
                "description": "A task that needs to be completed",
                "icon": "task",
                "color": "#0052CC",
                "is_default": True,
            },
            {
                "name": "Bug",
                "category": "bug",
                "description": "A problem that needs to be fixed",
                "icon": "bug",
                "color": "#FF5630",
                "is_default": True,
            },
            {
                "name": "Improvement",
                "category": "improvement",
                "description": "An enhancement to existing functionality",
                "icon": "improvement",
                "color": "#00B8D9",
                "is_default": False,
            },
            {
                "name": "Sub-task",
                "category": "sub_task",
                "description": "A subtask of a parent issue",
                "icon": "subtask",
                "color": "#6554C0",
                "is_default": False,
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

            # Check if project already has issue types
            existing_count = IssueType.objects.filter(project=project).count()

            if existing_count > 0 and not force:
                self.stdout.write(
                    self.style.WARNING(
                        f"   ⏭️  Skipping - already has {existing_count} issue types"
                    )
                )
                skipped_count += 1
                continue

            # Create or update issue types
            for issue_type_data in DEFAULT_ISSUE_TYPES:
                category = issue_type_data["category"]

                if force:
                    # Update existing or create new
                    issue_type, created = IssueType.objects.update_or_create(
                        project=project,
                        category=category,
                        defaults={
                            "name": issue_type_data["name"],
                            "description": issue_type_data["description"],
                            "icon": issue_type_data["icon"],
                            "color": issue_type_data["color"],
                            "is_default": issue_type_data["is_default"],
                            "is_active": True,
                        },
                    )
                else:
                    # Only create if doesn't exist
                    issue_type, created = IssueType.objects.get_or_create(
                        project=project,
                        category=category,
                        defaults={
                            "name": issue_type_data["name"],
                            "description": issue_type_data["description"],
                            "icon": issue_type_data["icon"],
                            "color": issue_type_data["color"],
                            "is_default": issue_type_data["is_default"],
                            "is_active": True,
                        },
                    )

                if created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"   ✅ Created: {issue_type.name} ({issue_type.category})"
                        )
                    )
                    created_count += 1
                else:
                    if force:
                        self.stdout.write(
                            self.style.WARNING(
                                f"   🔄 Updated: {issue_type.name} ({issue_type.category})"
                            )
                        )
                        updated_count += 1
                    else:
                        self.stdout.write(
                            f"   ⏭️  Exists: {issue_type.name} ({issue_type.category})"
                        )

        # Summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("✅ SEEDING COMPLETE"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"Created: {created_count} issue types")
        if force:
            self.stdout.write(f"Updated: {updated_count} issue types")
        self.stdout.write(f"Skipped: {skipped_count} projects")
        self.stdout.write("=" * 60 + "\n")
