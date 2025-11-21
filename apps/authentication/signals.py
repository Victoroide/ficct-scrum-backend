import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify

from apps.authentication.models import User, UserProfile

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
@transaction.atomic
def create_user_profile(sender, instance, created, **kwargs):
    """Create user profile automatically when user is created."""
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
@transaction.atomic
def save_user_profile(sender, instance, **kwargs):
    """
    Save user profile when user is saved.
    Handles cases where profile might not exist gracefully.
    """
    try:
        # Try to access and save the profile if it exists
        if hasattr(instance, 'profile'):
            profile = instance.profile
            profile.save()
    except UserProfile.DoesNotExist:
        # Profile doesn't exist yet, which is fine
        # It will be created by create_user_profile signal for new users
        pass
    except Exception as e:
        # Log other errors but don't break the user save
        logger.error(
            f"Error saving profile for user {instance.email}: {str(e)}",
            exc_info=True
        )


@receiver(post_save, sender=User)
def create_personal_resources(sender, instance, created, **kwargs):
    """
    Automatically create personal resources for new users:
    - Personal Organization (with owner membership)
    - Personal Workspace (with admin membership)
    - Personal Project (with project_manager membership)

    This ensures new users have a starting point and can immediately
    begin using the application.
    
    NOTE: Removed @transaction.atomic decorator to prevent signal from
    blocking user creation if personal resources fail to create.
    """
    # Only run for newly created users
    if not created:
        return

    # if instance.is_superuser:
    #     return

    user = instance

    try:
        # Import models here to avoid circular import issues
        from apps.organizations.models import Organization, OrganizationMembership
        from apps.projects.models import Project, ProjectTeamMember
        from apps.workspaces.models import Workspace, WorkspaceMember

        # Check if user already has ANY organization as owner (idempotency)
        # This prevents creating duplicate organizations if signal fires multiple times
        existing_org = Organization.objects.filter(owner=user).first()

        if existing_org:
            logger.info(
                f"User {user.email} already has an organization. "
                f"Skipping personal resource creation."
            )
            return

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

        # Ensure unique workspace slug
        workspace_slug = "personal"
        counter = 1
        # Note: Workspace slug only needs to be unique within an organization
        # But we'll make it unique anyway for safety

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

        # Create organization membership for the user (owner role)
        OrganizationMembership.objects.create(
            organization=organization,
            user=user,
            role="owner",
            status="active",
            joined_at=timezone.now(),
            is_active=True,
        )

        logger.info(
            f"[SUCCESS] Created personal organization '{organization.name}' "
            f"for user: {user.email}"
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

        # Create workspace membership for the user (admin role)
        WorkspaceMember.objects.create(
            workspace=workspace, user=user, role="admin", is_active=True
        )

        logger.info(
            f"[SUCCESS] Created personal workspace '{workspace.name}' for user: {user.email}"
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

        # Create project team membership for the user (project_manager role)
        ProjectTeamMember.objects.create(
            project=project, user=user, role="project_manager", is_active=True
        )

        logger.info(
            f"[SUCCESS] Created personal project '{project.key} - {project.name}' "
            f"for user: {user.email}"
        )

        # Log summary of created resources
        logger.info(
            f"[COMPLETE] Successfully created complete personal workspace for {user.email}:\n"
            f"  - Organization: {organization.name} (slug: {org_slug})\n"
            f"  - Workspace: {workspace.name}\n"
            f"  - Project: {project.key} - {project.name}\n"
            f"  All memberships configured with appropriate permissions."
        )

    except Exception as e:
        # Log the error but don't break user creation
        logger.error(
            f"[ERROR] Failed to create personal resources for user {user.email}: {str(e)}",
            exc_info=True,
        )
        # Don't re-raise - user creation should succeed even if personal resources fail
