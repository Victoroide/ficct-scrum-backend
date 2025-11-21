"""
Management command to create personal resources for existing users.

This command backfills personal organizations, workspaces, and projects for users
who were created before the automatic resource creation signal was implemented.

Usage:
    python manage.py create_personal_resources
    python manage.py create_personal_resources --user email@example.com
    python manage.py create_personal_resources --dry-run
"""

import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.authentication.models import User
from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project, ProjectTeamMember
from apps.workspaces.models import Workspace, WorkspaceMember

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Create personal resources (organization, workspace, project) "
        "for existing users"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            help="Email of specific user to create resources for",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without actually creating anything",
        )
        parser.add_argument(
            "--skip-superusers",
            action="store_true",
            help="Skip superuser accounts",
        )

    def handle(self, *args, **options):
        user_email = options.get("user")
        dry_run = options.get("dry_run", False)
        skip_superusers = options.get("skip_superusers", False)

        if dry_run:
            self.stdout.write(
                self.style.WARNING("🔍 DRY RUN MODE - No changes will be made\n")
            )

        # Get users to process
        if user_email:
            users = User.objects.filter(email=user_email)
            if not users.exists():
                self.stdout.write(
                    self.style.ERROR(f"❌ User with email '{user_email}' not found")
                )
                return
        else:
            users = User.objects.filter(is_active=True)
            if skip_superusers:
                users = users.filter(is_superuser=False)

        total_users = users.count()
        self.stdout.write(f"Found {total_users} user(s) to process\n")

        created_count = 0
        skipped_count = 0
        error_count = 0

        for user in users:
            try:
                result = self._create_personal_resources_for_user(user, dry_run)
                if result == "created":
                    created_count += 1
                elif result == "skipped":
                    skipped_count += 1
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f"❌ Error processing {user.email}: {str(e)}")
                )
                logger.error(
                    f"Error creating resources for {user.email}", exc_info=True
                )

        # Print summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("📊 SUMMARY"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"Total users processed: {total_users}")
        self.stdout.write(self.style.SUCCESS(f"✅ Resources created: {created_count}"))
        self.stdout.write(
            self.style.WARNING(f"⏭️  Skipped (already exists): {skipped_count}")
        )
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"❌ Errors: {error_count}"))
        self.stdout.write("=" * 60 + "\n")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "This was a DRY RUN. Run without --dry-run to actually "
                    "create resources."
                )
            )

    @transaction.atomic
    def _create_personal_resources_for_user(self, user, dry_run=False):
        """
        Create personal resources for a single user.

        Returns:
            "created" if resources were created
            "skipped" if user already has resources
        """
        # Check if user already has ANY organization as owner
        existing_org = Organization.objects.filter(owner=user).first()

        if existing_org:
            self.stdout.write(
                self.style.WARNING(
                    f"⏭️  Skipping {user.email}: Already has an organization"
                )
            )
            return "skipped"

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Would create personal resources for: {user.email} "
                    f"({user.full_name})"
                )
            )
            return "created"

        # Generate unique slugs and keys
        base_slug = slugify(f"{user.first_name}-{user.last_name}".strip())
        if not base_slug:
            base_slug = slugify(user.username)

        # Ensure unique organization slug
        org_slug = base_slug
        counter = 1
        while Organization.objects.filter(slug=org_slug).exists():
            org_slug = f"{base_slug}-{counter}"
            counter += 1

        # Workspace slug (unique within organization, but we'll make it globally unique)
        workspace_slug = "personal"

        # Generate project key from user initials
        first_initial = user.first_name[0].upper() if user.first_name else "P"
        last_initial = user.last_name[0].upper() if user.last_name else "P"
        project_key = f"{first_initial}{last_initial}"

        # 1. CREATE PERSONAL ORGANIZATION
        organization = Organization.objects.create(
            name=f"{user.full_name}'s Organization"
            if user.full_name
            else "Personal Organization",
            slug=org_slug,
            description="Personal workspace for individual projects",
            organization_type="other",
            subscription_plan="free",
            owner=user,
            is_active=True,
        )

        # Create organization membership
        OrganizationMembership.objects.create(
            organization=organization,
            user=user,
            role="owner",
            status="active",
            joined_at=timezone.now(),
            is_active=True,
        )

        # 2. CREATE PERSONAL WORKSPACE
        workspace = Workspace.objects.create(
            organization=organization,
            name="Personal Workspace",
            slug=workspace_slug,
            description="Personal workspace for your projects",
            workspace_type="general",
            visibility="private",
            created_by=user,
            is_active=True,
        )

        # Create workspace membership
        WorkspaceMember.objects.create(
            workspace=workspace,
            user=user,
            role="admin",
            is_active=True,
        )

        # 3. CREATE PERSONAL PROJECT
        # Ensure project key is unique within the workspace
        counter = 1
        unique_project_key = project_key
        while Project.objects.filter(
            workspace=workspace, key=unique_project_key
        ).exists():
            unique_project_key = f"{project_key}{counter}"
            counter += 1

        project = Project.objects.create(
            workspace=workspace,
            name="My First Project",
            key=unique_project_key,
            description="Your personal project to get started",
            methodology="scrum",
            status="active",
            priority="medium",
            lead=user,
            created_by=user,
            is_active=True,
        )

        # Create project team membership
        ProjectTeamMember.objects.create(
            project=project,
            user=user,
            role="project_manager",
            is_active=True,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Created personal resources for {user.email}:\n"
                f"   - Organization: {organization.name} (slug: {org_slug})\n"
                f"   - Workspace: {workspace.name}\n"
                f"   - Project: {project.key} - {project.name}"
            )
        )

        return "created"
