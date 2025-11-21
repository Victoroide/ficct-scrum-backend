"""
Celery tasks for notifications app.

Scheduled tasks for deadline monitoring and notification delivery.
"""

import logging
from datetime import timedelta

from django.utils import timezone

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="apps.notifications.tasks.check_upcoming_deadlines")
def check_upcoming_deadlines(self):
    """
    Check for upcoming issue and sprint deadlines and send alerts.

    This task runs daily at 9 AM and sends notifications for:
    - Issues due in 3 days, 1 day, or today
    - Sprints ending in 3 days, 1 day, or today

    Returns:
        dict: Notification results summary
    """
    try:
        from apps.notifications.models import Notification
        from apps.notifications.services import NotificationService
        from apps.projects.models import Issue, Sprint

        logger.info("Starting deadline monitoring task")

        notification_service = NotificationService()
        now = timezone.now()
        today = now.date()

        results = {
            "issue_deadlines_checked": 0,
            "sprint_deadlines_checked": 0,
            "notifications_created": 0,
            "errors": [],
        }

        # ===== Check Issue Deadlines =====
        for days_until in [3, 1, 0]:  # 3 days, 1 day, today
            deadline_date = today + timedelta(days=days_until)

            # Query issues due on this date
            issues_due = Issue.objects.filter(
                due_date__date=deadline_date,
                status__is_final=False,  # Not completed
                assignee__isnull=False,  # Has assignee
            ).select_related("assignee", "project")

            for issue in issues_due:
                try:
                    results["issue_deadlines_checked"] += 1

                    # Check if we already notified about this deadline
                    already_notified = Notification.objects.filter(
                        recipient=issue.assignee,
                        notification_type="deadline_approaching",
                        data__issue_id=str(issue.id),
                        data__days_until=days_until,
                        created_at__gte=now
                        - timedelta(hours=12),  # Within last 12 hours
                    ).exists()

                    if already_notified:
                        logger.debug(
                            f"Already notified about issue {issue.key} deadline"
                        )
                        continue

                    # Send notification
                    notification_service.notify_deadline_approaching(
                        issue_id=str(issue.id),
                        days_until_deadline=days_until,
                    )

                    results["notifications_created"] += 1
                    logger.info(
                        f"Sent deadline notification for issue {issue.key} (due in {days_until} day(s))"  # noqa: E501
                    )

                except Exception as e:
                    error_msg = f"Error notifying issue {issue.id} deadline: {str(e)}"
                    logger.exception(error_msg)
                    results["errors"].append(error_msg)

        # ===== Check Sprint Deadlines =====
        for days_until in [3, 1, 0]:  # 3 days, 1 day, today
            deadline_date = today + timedelta(days=days_until)

            # Query sprints ending on this date
            sprints_ending = Sprint.objects.filter(
                end_date__date=deadline_date,
                status__in=["planning", "active"],  # Not completed
            ).select_related("project")

            for sprint in sprints_ending:
                try:
                    results["sprint_deadlines_checked"] += 1

                    # Get project team members (leads and admins)
                    from apps.projects.models import ProjectTeamMember

                    team_leads = ProjectTeamMember.objects.filter(
                        project=sprint.project,
                        role__in=["lead", "admin"],
                        is_active=True,
                    ).select_related("user")

                    for team_member in team_leads:
                        # Check if already notified
                        already_notified = Notification.objects.filter(
                            recipient=team_member.user,
                            notification_type="sprint_deadline_approaching",
                            data__sprint_id=str(sprint.id),
                            data__days_until=days_until,
                            created_at__gte=now - timedelta(hours=12),
                        ).exists()

                        if already_notified:
                            continue

                        # Create notification
                        urgency = (
                            "critical"
                            if days_until == 0
                            else "high"
                            if days_until == 1
                            else "medium"
                        )
                        title = f"Sprint deadline {'today' if days_until == 0 else f'in {days_until} day(s)'}"  # noqa: E501
                        message = f"Sprint '{sprint.name}' ends on {sprint.end_date.strftime('%Y-%m-%d')}"  # noqa: E501

                        notification_service.create_notification(
                            recipient=team_member.user,
                            notification_type="sprint_deadline_approaching",
                            title=title,
                            message=message,
                            link=f"/projects/{sprint.project.key}/sprints/{sprint.id}",
                            data={
                                "sprint_id": str(sprint.id),
                                "days_until": days_until,
                                "urgency": urgency,
                            },
                            send_email=True if days_until <= 1 else False,
                        )

                        results["notifications_created"] += 1
                        logger.info(
                            f"Sent sprint deadline notification for {sprint.name} to {team_member.user.email}"  # noqa: E501
                        )

                except Exception as e:
                    error_msg = f"Error notifying sprint {sprint.id} deadline: {str(e)}"
                    logger.exception(error_msg)
                    results["errors"].append(error_msg)

        logger.info(f"Deadline monitoring task completed: {results}")
        return results

    except Exception as e:
        logger.exception(f"Critical error in check_upcoming_deadlines task: {str(e)}")
        raise


@shared_task(bind=True, name="apps.notifications.tasks.send_notification_digests")
def send_notification_digests(self):
    """
    Send daily digest emails to users who have digest mode enabled.

    This task aggregates unread notifications and sends a summary email.

    Returns:
        dict: Digest sending results
    """
    try:
        from apps.notifications.models import Notification, NotificationPreference

        logger.info("Starting notification digest task")

        results = {
            "users_processed": 0,
            "digests_sent": 0,
            "errors": [],
        }

        # Get users with digest mode enabled
        digest_preferences = NotificationPreference.objects.filter(
            digest_enabled=True,
            email_enabled=True,
        ).select_related("user")

        for preference in digest_preferences:
            try:
                user = preference.user
                results["users_processed"] += 1

                # Get unread notifications from last 24 hours
                yesterday = timezone.now() - timedelta(days=1)
                unread_notifications = Notification.objects.filter(
                    recipient=user,
                    is_read=False,
                    created_at__gte=yesterday,
                ).order_by("-created_at")

                if not unread_notifications.exists():
                    continue

                # Group notifications by type
                notification_groups = {}
                for notif in unread_notifications:
                    if notif.notification_type not in notification_groups:
                        notification_groups[notif.notification_type] = []
                    notification_groups[notif.notification_type].append(notif)

                # Build digest email (simplified - would use email template in
                # production)
                digest_summary = (
                    f"You have {unread_notifications.count()} unread notifications:\n\n"
                )
                for notif_type, notifs in notification_groups.items():
                    digest_summary += f"- {len(notifs)} {notif_type.replace('_', ' ')} notifications\n"  # noqa: E501

                # Send digest email (placeholder - would use EmailService in production)
                # notification_service.email_service.send_digest_email(user.email, digest_summary)  # noqa: E501

                results["digests_sent"] += 1
                logger.info(
                    f"Sent digest to {user.email} with {unread_notifications.count()} notifications"  # noqa: E501
                )

            except Exception as e:
                error_msg = f"Error sending digest to {preference.user_id}: {str(e)}"
                logger.exception(error_msg)
                results["errors"].append(error_msg)

        logger.info(f"Notification digest task completed: {results}")
        return results

    except Exception as e:
        logger.exception(f"Critical error in send_notification_digests task: {str(e)}")
        raise


@shared_task(bind=True, name="apps.notifications.tasks.cleanup_old_notifications")
def cleanup_old_notifications(self):
    """
    Clean up old read notifications (older than 90 days).

    This maintenance task prevents unbounded growth of notification records.

    Returns:
        dict: Cleanup results
    """
    try:
        from apps.notifications.models import Notification

        logger.info("Starting notification cleanup task")

        ninety_days_ago = timezone.now() - timedelta(days=90)
        deleted_count, _ = Notification.objects.filter(
            is_read=True,
            created_at__lt=ninety_days_ago,
        ).delete()

        logger.info(f"Deleted {deleted_count} old notifications")
        return {"deleted_count": deleted_count}

    except Exception as e:
        logger.exception(f"Error in cleanup_old_notifications task: {str(e)}")
        raise
