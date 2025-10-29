"""
Signals for automatic ActivityLog creation.

Tracks create, update, and delete operations for key models:
- Board, Sprint, Issue (Projects app)
- Project (Projects app)
- Workspace (Workspaces app)
"""

from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.projects.models import Board, Issue, Project, Sprint
from apps.workspaces.models import Workspace

from .middleware import get_current_request, get_current_user
from .models import ActivityLog


def get_client_ip(request):
    """Extract client IP from request."""
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def create_activity_log(user, action_type, obj, changes=None, request=None):
    """
    Helper to create ActivityLog entries with proper hierarchy.
    
    Automatically determines organization, workspace, and project based on object type.
    """
    if not user or not user.is_authenticated:
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
        ip_address=ip_address
    )


# ============================================================================
# BOARD SIGNALS
# ============================================================================

@receiver(post_save, sender=Board)
def log_board_activity(sender, instance, created, **kwargs):
    """Log Board create/update."""
    user = get_current_user()
    if not user or not user.is_authenticated:
        return
    
    action_type = "created" if created else "updated"
    
    create_activity_log(
        user=user,
        action_type=action_type,
        obj=instance,
        changes={},
        request=get_current_request()
    )


@receiver(post_delete, sender=Board)
def log_board_delete(sender, instance, **kwargs):
    """Log Board deletion."""
    user = get_current_user()
    if not user or not user.is_authenticated:
        return
    
    create_activity_log(
        user=user,
        action_type="deleted",
        obj=instance,
        request=get_current_request()
    )


# ============================================================================
# SPRINT SIGNALS
# ============================================================================

@receiver(post_save, sender=Sprint)
def log_sprint_activity(sender, instance, created, **kwargs):
    """Log Sprint create/update."""
    user = get_current_user()
    if not user or not user.is_authenticated:
        return
    
    action_type = "created" if created else "updated"
    
    create_activity_log(
        user=user,
        action_type=action_type,
        obj=instance,
        changes={},
        request=get_current_request()
    )


@receiver(post_delete, sender=Sprint)
def log_sprint_delete(sender, instance, **kwargs):
    """Log Sprint deletion."""
    user = get_current_user()
    if not user or not user.is_authenticated:
        return
    
    create_activity_log(
        user=user,
        action_type="deleted",
        obj=instance,
        request=get_current_request()
    )


# ============================================================================
# ISSUE SIGNALS
# ============================================================================

@receiver(post_save, sender=Issue)
def log_issue_activity(sender, instance, created, **kwargs):
    """Log Issue create/update."""
    user = get_current_user()
    if not user or not user.is_authenticated:
        return
    
    action_type = "created" if created else "updated"
    
    create_activity_log(
        user=user,
        action_type=action_type,
        obj=instance,
        changes={},
        request=get_current_request()
    )


@receiver(post_delete, sender=Issue)
def log_issue_delete(sender, instance, **kwargs):
    """Log Issue deletion."""
    user = get_current_user()
    if not user or not user.is_authenticated:
        return
    
    create_activity_log(
        user=user,
        action_type="deleted",
        obj=instance,
        request=get_current_request()
    )


# ============================================================================
# PROJECT SIGNALS
# ============================================================================

@receiver(post_save, sender=Project)
def log_project_activity(sender, instance, created, **kwargs):
    """Log Project create/update."""
    user = get_current_user()
    if not user or not user.is_authenticated:
        return
    
    action_type = "created" if created else "updated"
    
    create_activity_log(
        user=user,
        action_type=action_type,
        obj=instance,
        changes={},
        request=get_current_request()
    )


@receiver(post_delete, sender=Project)
def log_project_delete(sender, instance, **kwargs):
    """Log Project deletion."""
    user = get_current_user()
    if not user or not user.is_authenticated:
        return
    
    create_activity_log(
        user=user,
        action_type="deleted",
        obj=instance,
        request=get_current_request()
    )


# ============================================================================
# WORKSPACE SIGNALS
# ============================================================================

@receiver(post_save, sender=Workspace)
def log_workspace_activity(sender, instance, created, **kwargs):
    """Log Workspace create/update."""
    user = get_current_user()
    if not user or not user.is_authenticated:
        return
    
    action_type = "created" if created else "updated"
    
    create_activity_log(
        user=user,
        action_type=action_type,
        obj=instance,
        changes={},
        request=get_current_request()
    )


@receiver(post_delete, sender=Workspace)
def log_workspace_delete(sender, instance, **kwargs):
    """Log Workspace deletion."""
    user = get_current_user()
    if not user or not user.is_authenticated:
        return
    
    create_activity_log(
        user=user,
        action_type="deleted",
        obj=instance,
        request=get_current_request()
    )
