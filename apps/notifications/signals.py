"""
Signals for automatic notification creation.

Automatically creates notifications when issues are assigned, status changes, etc.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.projects.models import Issue
from apps.reporting.middleware import get_current_user

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Issue)
def notify_on_issue_change(sender, instance, created, **kwargs):
    """
    Create notifications when issues are created or updated.

    Args:
        sender: Issue model
        instance: Issue instance
        created: True if newly created
        **kwargs: Additional arguments
    """
    try:
        from apps.notifications.services import NotificationService
        
        notification_service = NotificationService()
        current_user = get_current_user()
        
        # Skip if no authenticated user (e.g., management commands)
        if not current_user or not current_user.is_authenticated:
            return
        
        # Notify on assignment
        if created and instance.assignee and instance.assignee != current_user:
            notification_service.notify_issue_assigned(
                issue_id=str(instance.id),
                assignee_id=str(instance.assignee_id),
                assigner_id=str(current_user.id),
            )
            logger.debug(f"Sent assignment notification for issue {instance.id}")
        
        # Notify on status change (detect using update_fields)
        update_fields = kwargs.get("update_fields")
        if not created and update_fields and "status" in update_fields:
            # Would need to track old status - simplified implementation
            # In production, use django-simple-history or custom tracking
            pass
            
    except Exception as e:
        logger.exception(f"Error creating notification for issue {instance.id}: {str(e)}")
