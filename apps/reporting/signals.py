"""
Signals for automatic ActivityLog creation.

Tracks create, update, and delete operations for key models:
- Board, Sprint, Issue (Projects app)
- Project (Projects app)
- Workspace (Workspaces app)

Enhanced with:
- Fallback actor detection (works without request context)
- Field change detection for detailed activity logs
- Anti-duplication logic
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.projects.models import Board, Issue, Project, Sprint
from apps.workspaces.models import Workspace

from .middleware import get_current_request, get_current_user
from .models import ActivityLog

User = get_user_model()


def get_client_ip(request):
    """Extract client IP from request."""
    if not request:
        return None
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def get_actor(instance):
    """
    Get the user responsible for the action.

    Tries multiple sources in priority order:
    1. Current request user (from middleware)
    2. Instance's reporter/creator field
    3. Instance's assignee field
    4. System user (fallback)

    Args:
        instance: Model instance being modified

    Returns:
        User instance
    """
    # Try request context first
    user = get_current_user()
    if user and user.is_authenticated:
        return user

    # Try instance-specific user fields
    if isinstance(instance, Issue):
        # Try reporter first, then assignee
        if instance.reporter:
            return instance.reporter
        if instance.assignee:
            return instance.assignee
    elif isinstance(instance, (Sprint, Board, Project)):
        # Try lead/creator
        if hasattr(instance, "lead") and instance.lead:
            return instance.lead
        if hasattr(instance, "created_by") and instance.created_by:
            return instance.created_by
        # Try project lead
        if hasattr(instance, "project") and instance.project and instance.project.lead:
            return instance.project.lead

    # Fallback to first superuser (system user)
    system_user = User.objects.filter(is_superuser=True).first()
    if system_user:
        return system_user

    # Last resort: first active user
    return User.objects.filter(is_active=True).first()


def should_create_activity(obj, action_type):
    """
    Check if activity should be created (anti-duplication).

    Prevents duplicate activities within 60 seconds for same object and action.

    Args:
        obj: Model instance
        action_type: Type of action

    Returns:
        bool: True if activity should be created
    """
    cache_key = f"activity_log_{obj._meta.model_name}_{obj.id}_{action_type}"
    if cache.get(cache_key):
        return False

    # Set cache for 60 seconds
    cache.set(cache_key, True, 60)
    return True


def create_activity_log(user, action_type, obj, changes=None, request=None):
    """
    Helper to create ActivityLog entries with proper hierarchy.

    Automatically determines organization, workspace, and project based on object type.
    Works both in request context and outside (e.g., management commands).

    Args:
        user: User performing the action
        action_type: Type of action
        obj: Object being modified
        changes: Dictionary of changes
        request: HTTP request (optional)
    """
    if not user:
        user = get_actor(obj)

    if not user:
        return  # No user available, skip

    # Anti-duplication check
    if not should_create_activity(obj, action_type):
        return

    content_type = ContentType.objects.get_for_model(obj)

    # Determine hierarchy based on object type
    project = None
    workspace = None
    organization = None

    if isinstance(obj, Issue):
        project = obj.project
        workspace = project.workspace if project else None
        organization = workspace.organization if workspace else None
    elif isinstance(obj, (Board, Sprint)):
        project = obj.project
        workspace = project.workspace if project else None
        organization = workspace.organization if workspace else None
    elif isinstance(obj, Project):
        project = obj
        workspace = obj.workspace
        organization = workspace.organization if workspace else None
    elif isinstance(obj, Workspace):
        workspace = obj
        organization = obj.organization

    # Get IP address
    ip_address = get_client_ip(request) if request else None

    # Create log
    ActivityLog.objects.create(
        user=user,
        action_type=action_type,
        content_type=content_type,
        object_id=str(obj.id),
        object_repr=str(obj),
        project=project,
        workspace=workspace,
        organization=organization,
        changes=changes or {},
        ip_address=ip_address,
    )


# ============================================================================
# BOARD SIGNALS
# ============================================================================


@receiver(post_save, sender=Board)
def log_board_activity(sender, instance, created, **kwargs):
    """Log Board create/update."""
    action_type = "created" if created else "updated"

    create_activity_log(
        user=None,  # Will use fallback actor detection
        action_type=action_type,
        obj=instance,
        changes={},
        request=get_current_request(),
    )


@receiver(post_delete, sender=Board)
def log_board_delete(sender, instance, **kwargs):
    """Log Board deletion."""
    create_activity_log(
        user=None,  # Will use fallback actor detection
        action_type="deleted",
        obj=instance,
        request=get_current_request(),
    )


# ============================================================================
# SPRINT SIGNALS
# ============================================================================


@receiver(pre_save, sender=Sprint)
def store_sprint_old_values_for_activity(sender, instance, **kwargs):
    """Store old values before save to detect status transitions."""
    if instance.pk:
        try:
            old_instance = Sprint.objects.get(pk=instance.pk)
            instance._old_activity_values = {
                "status": old_instance.status,
            }
        except Sprint.DoesNotExist:
            instance._old_activity_values = {}
    else:
        instance._old_activity_values = {}


@receiver(post_save, sender=Sprint)
def log_sprint_activity(sender, instance, created, **kwargs):
    """Log Sprint create/update with status transition detection."""
    if created:
        create_activity_log(
            user=None,  # Will use fallback actor detection
            action_type="created",
            obj=instance,
            changes={},
            request=get_current_request(),
        )
    else:
        # Check for status transitions
        if hasattr(instance, "_old_activity_values"):
            old_status = instance._old_activity_values.get("status")
            new_status = instance.status

            if old_status != new_status:
                # Log status transition
                create_activity_log(
                    user=None,
                    action_type="transitioned",
                    obj=instance,
                    changes={
                        "field": "status",
                        "old_value": old_status,
                        "new_value": new_status,
                    },
                    request=get_current_request(),
                )

        # Log general update
        create_activity_log(
            user=None,
            action_type="updated",
            obj=instance,
            changes={},
            request=get_current_request(),
        )


@receiver(post_delete, sender=Sprint)
def log_sprint_delete(sender, instance, **kwargs):
    """Log Sprint deletion."""
    create_activity_log(
        user=None,  # Will use fallback actor detection
        action_type="deleted",
        obj=instance,
        request=get_current_request(),
    )


# ============================================================================
# ISSUE SIGNALS
# ============================================================================


@receiver(pre_save, sender=Issue)
def store_issue_old_values_for_activity(sender, instance, **kwargs):
    """Store old values before save to detect field changes."""
    if instance.pk:
        try:
            old_instance = Issue.objects.get(pk=instance.pk)
            instance._old_activity_values = {
                "status_id": old_instance.status_id,
                "assignee_id": old_instance.assignee_id,
                "priority": old_instance.priority,
                "sprint_id": old_instance.sprint_id,
            }
        except Issue.DoesNotExist:
            instance._old_activity_values = {}
    else:
        instance._old_activity_values = {}


@receiver(post_save, sender=Issue)
def log_issue_activity(sender, instance, created, **kwargs):
    """Log Issue create/update with detailed field change detection."""
    if created:
        create_activity_log(
            user=None,  # Will use fallback actor detection
            action_type="created",
            obj=instance,
            changes={},
            request=get_current_request(),
        )
    else:
        # Detect and log specific field changes
        if hasattr(instance, "_old_activity_values"):
            old_values = instance._old_activity_values

            # Status change
            if old_values.get("status_id") != instance.status_id:
                old_status = old_values.get("status_id")
                try:
                    from apps.projects.models import WorkflowStatus

                    old_status_name = (
                        WorkflowStatus.objects.get(pk=old_status).name
                        if old_status
                        else "None"
                    )
                    new_status_name = (
                        instance.status.name if instance.status else "None"
                    )
                except:
                    old_status_name = str(old_status)
                    new_status_name = str(instance.status_id)

                create_activity_log(
                    user=None,
                    action_type="transitioned",
                    obj=instance,
                    changes={
                        "field": "status",
                        "old_value": old_status_name,
                        "new_value": new_status_name,
                    },
                    request=get_current_request(),
                )

            # Assignee change
            if old_values.get("assignee_id") != instance.assignee_id:
                old_assignee = old_values.get("assignee_id")
                try:
                    from django.contrib.auth import get_user_model

                    User = get_user_model()
                    old_assignee_name = (
                        User.objects.get(pk=old_assignee).get_full_name()
                        if old_assignee
                        else "Unassigned"
                    )
                    new_assignee_name = (
                        instance.assignee.get_full_name()
                        if instance.assignee
                        else "Unassigned"
                    )
                except:
                    old_assignee_name = str(old_assignee)
                    new_assignee_name = str(instance.assignee_id)

                create_activity_log(
                    user=None,
                    action_type="assigned",
                    obj=instance,
                    changes={
                        "field": "assignee",
                        "old_value": old_assignee_name,
                        "new_value": new_assignee_name,
                    },
                    request=get_current_request(),
                )

            # Sprint change
            if old_values.get("sprint_id") != instance.sprint_id:
                if instance.sprint_id and not old_values.get("sprint_id"):
                    # Added to sprint
                    create_activity_log(
                        user=None,
                        action_type="sprint_added",
                        obj=instance,
                        changes={
                            "field": "sprint",
                            "sprint_name": instance.sprint.name
                            if instance.sprint
                            else "",
                        },
                        request=get_current_request(),
                    )
                elif not instance.sprint_id and old_values.get("sprint_id"):
                    # Removed from sprint
                    create_activity_log(
                        user=None,
                        action_type="sprint_removed",
                        obj=instance,
                        changes={"field": "sprint"},
                        request=get_current_request(),
                    )

        # Log general update (only if no specific changes logged)
        create_activity_log(
            user=None,
            action_type="updated",
            obj=instance,
            changes={},
            request=get_current_request(),
        )


@receiver(post_delete, sender=Issue)
def log_issue_delete(sender, instance, **kwargs):
    """Log Issue deletion."""
    create_activity_log(
        user=None,  # Will use fallback actor detection
        action_type="deleted",
        obj=instance,
        request=get_current_request(),
    )


# ============================================================================
# PROJECT SIGNALS
# ============================================================================


@receiver(post_save, sender=Project)
def log_project_activity(sender, instance, created, **kwargs):
    """Log Project create/update."""
    action_type = "created" if created else "updated"

    create_activity_log(
        user=None,  # Will use fallback actor detection
        action_type=action_type,
        obj=instance,
        changes={},
        request=get_current_request(),
    )


@receiver(post_delete, sender=Project)
def log_project_delete(sender, instance, **kwargs):
    """Log Project deletion."""
    create_activity_log(
        user=None,  # Will use fallback actor detection
        action_type="deleted",
        obj=instance,
        request=get_current_request(),
    )


# ============================================================================
# WORKSPACE SIGNALS
# ============================================================================


@receiver(post_save, sender=Workspace)
def log_workspace_activity(sender, instance, created, **kwargs):
    """Log Workspace create/update."""
    action_type = "created" if created else "updated"

    create_activity_log(
        user=None,  # Will use fallback actor detection
        action_type=action_type,
        obj=instance,
        changes={},
        request=get_current_request(),
    )


@receiver(post_delete, sender=Workspace)
def log_workspace_delete(sender, instance, **kwargs):
    """Log Workspace deletion."""
    create_activity_log(
        user=None,  # Will use fallback actor detection
        action_type="deleted",
        obj=instance,
        request=get_current_request(),
    )
