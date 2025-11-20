"""
Signals for automatic notification creation.

Automatically creates notifications when issues are assigned, status changes, etc.
Implements field tracking to detect changes in assignee, status, and priority.
"""

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.projects.models import Issue, IssueComment
from apps.reporting.middleware import get_current_user

logger = logging.getLogger(__name__)


# =============================================================================
# FIELD TRACKING: Store old values before save
# =============================================================================


@receiver(pre_save, sender=Issue)
def track_issue_changes(sender, instance, **kwargs):
    """
    Track field changes before save to detect what changed.
    Stores old values in instance._old_values for comparison in post_save.
    """
    if instance.pk:  # Only for existing instances
        try:
            old_instance = Issue.objects.get(pk=instance.pk)
            instance._old_assignee_id = old_instance.assignee_id
            instance._old_status_id = old_instance.status_id
            instance._old_priority = old_instance.priority
        except Issue.DoesNotExist:
            pass


# =============================================================================
# ISSUE NOTIFICATIONS
# =============================================================================


@receiver(post_save, sender=Issue)
def notify_on_issue_change(sender, instance, created, **kwargs):
    """
    Create notifications when issues are created or updated.

    Handles:
    - New issue creation with assignee
    - Assignment changes
    - Status changes
    - Priority changes

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

        # Skip if no authenticated user (e.g., management commands, migrations)
        if not current_user or not current_user.is_authenticated:
            logger.debug(f"Skipping notification for issue {instance.id} - no authenticated user")
            return

        # =====================================================================
        # 1. ASSIGNMENT NOTIFICATIONS
        # =====================================================================
        
        if created:
            # New issue created with assignee
            if instance.assignee and instance.assignee != current_user:
                notification_service.notify_issue_assigned(
                    issue_id=str(instance.id),
                    assignee_id=str(instance.assignee_id),
                    assigner_id=str(current_user.id),
                )
                logger.info(f"[NOTIFICATION] Sent assignment notification for new issue {instance.full_key}")
        else:
            # Check if assignee changed on existing issue
            old_assignee_id = getattr(instance, '_old_assignee_id', None)
            new_assignee_id = instance.assignee_id
            
            # Convert to strings for comparison (UUIDs)
            old_id_str = str(old_assignee_id) if old_assignee_id else None
            new_id_str = str(new_assignee_id) if new_assignee_id else None
            current_user_id_str = str(current_user.id)
            
            if old_id_str != new_id_str:
                # Assignee changed
                if new_assignee_id and new_id_str != current_user_id_str:
                    # Notify new assignee
                    notification_service.notify_issue_assigned(
                        issue_id=str(instance.id),
                        assignee_id=new_id_str,
                        assigner_id=current_user_id_str,
                    )
                    logger.info(
                        f"[NOTIFICATION] Sent assignment change notification for issue {instance.full_key} "
                        f"(old: {old_id_str}, new: {new_id_str})"
                    )

        # =====================================================================
        # 2. STATUS CHANGE NOTIFICATIONS
        # =====================================================================
        
        if not created:
            old_status_id = getattr(instance, '_old_status_id', None)
            new_status_id = instance.status_id
            
            # Convert to strings for comparison (UUIDs)
            old_status_str = str(old_status_id) if old_status_id else None
            new_status_str = str(new_status_id) if new_status_id else None
            
            if old_status_str and old_status_str != new_status_str:
                # Status changed - get status names
                try:
                    from apps.projects.models import WorkflowStatus
                    
                    old_status = WorkflowStatus.objects.get(id=old_status_id)
                    new_status = WorkflowStatus.objects.get(id=new_status_id)
                    
                    notification_service.notify_status_change(
                        issue_id=str(instance.id),
                        old_status=old_status.name,
                        new_status=new_status.name,
                        changed_by_id=str(current_user.id),
                    )
                    logger.info(
                        f"[NOTIFICATION] Sent status change notification for issue {instance.full_key} "
                        f"({old_status.name} -> {new_status.name})"
                    )
                except Exception as e:
                    logger.error(f"Error notifying status change: {str(e)}")

        # =====================================================================
        # 3. PRIORITY CHANGE NOTIFICATIONS (Optional - can be enabled)
        # =====================================================================
        
        # Uncomment if you want priority change notifications:
        # if not created:
        #     old_priority = getattr(instance, '_old_priority', None)
        #     if old_priority and old_priority != instance.priority:
        #         # Notify assignee and reporter about priority change
        #         pass

    except Exception as e:
        logger.exception(
            f"[NOTIFICATION ERROR] Failed to create notification for issue {instance.id}: {str(e)}"
        )


# =============================================================================
# COMMENT NOTIFICATIONS
# =============================================================================


@receiver(post_save, sender=IssueComment)
def notify_on_comment(sender, instance, created, **kwargs):
    """
    Create notifications when comments are added to issues.

    Notifies:
    - Issue assignee (if not the commenter)
    - Issue reporter (if not the commenter)
    - Previous commenters (optional, can be enabled)

    Args:
        sender: IssueComment model
        instance: IssueComment instance
        created: True if newly created
        **kwargs: Additional arguments
    """
    if not created:
        return  # Only notify on new comments, not updates

    try:
        from apps.notifications.services import NotificationService

        notification_service = NotificationService()
        current_user = get_current_user()

        # Skip if no authenticated user
        if not current_user or not current_user.is_authenticated:
            logger.debug(f"Skipping comment notification - no authenticated user")
            return

        issue = instance.issue
        commenter = instance.author
        
        # Determine recipients (assignee and reporter, excluding commenter)
        recipients = []
        
        if issue.assignee and issue.assignee != commenter:
            recipients.append(issue.assignee)
        
        if issue.reporter and issue.reporter != commenter and issue.reporter not in recipients:
            recipients.append(issue.reporter)

        # Create notification for each recipient
        for recipient in recipients:
            title = f"New comment on {issue.full_key}: {issue.title}"
            message = f"{commenter.get_full_name()} commented: {instance.content[:100]}{'...' if len(instance.content) > 100 else ''}"
            link = f"/projects/{issue.project.key}/issues/{issue.id}"

            notification_service.create_notification(
                recipient=recipient,
                notification_type="issue_commented",
                title=title,
                message=message,
                link=link,
                data={
                    "issue_id": str(issue.id),
                    "comment_id": str(instance.id),
                    "project_id": str(issue.project_id),
                },
                send_email=True,
            )
            logger.info(
                f"[NOTIFICATION] Sent comment notification to {recipient.email} for issue {issue.full_key}"
            )

    except Exception as e:
        logger.exception(
            f"[NOTIFICATION ERROR] Failed to create comment notification: {str(e)}"
        )
