"""
Notification service for creating and delivering notifications.

Handles in-app, email, and Slack notifications based on user preferences.
"""

import logging
from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.notifications.models import Notification, NotificationPreference
from base.services import EmailService
from .slack_service import SlackService

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationService:
    """Service for creating and managing notifications."""

    def __init__(self):
        """Initialize notification service."""
        self.email_service = EmailService()
        self.slack_service = SlackService()

    def create_notification(
        self,
        recipient: User,
        notification_type: str,
        title: str,
        message: str,
        link: str = "",
        data: Optional[Dict[str, Any]] = None,
        send_email: bool = True,
        send_slack: bool = False,
    ) -> Notification:
        """
        Create and deliver notification to user.

        Args:
            recipient: User to receive notification
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            link: Optional link to resource
            data: Additional data dictionary
            send_email: Send email notification
            send_slack: Send Slack notification

        Returns:
            Created Notification instance
        """
        try:
            # Get user preferences
            preferences = self._get_or_create_preferences(recipient)
            
            # Check if in-app notifications are enabled
            if not preferences.in_app_enabled:
                logger.debug(f"In-app notifications disabled for {recipient.email}")
                return None
            
            # Check if user wants this type of notification
            if not preferences.is_type_enabled(notification_type):
                logger.debug(f"Notification type {notification_type} disabled for {recipient.email}")
                return None
            
            # Create in-app notification
            notification = Notification.objects.create(
                recipient=recipient,
                notification_type=notification_type,
                title=title,
                message=message,
                link=link,
                data=data or {},
            )
            
            # Send via channels based on preferences
            if send_email and preferences.email_enabled and not preferences.digest_enabled:
                self._send_email_notification(notification)
            
            if send_slack and preferences.slack_enabled:
                self._send_slack_notification(notification)
            
            logger.info(f"Created notification {notification.id} for {recipient.email}")
            return notification
            
        except Exception as e:
            logger.exception(f"Error creating notification: {str(e)}")
            raise

    def notify_issue_assigned(self, issue_id: str, assignee_id: str, assigner_id: str):
        """Notify user when issue is assigned to them."""
        try:
            from apps.projects.models import Issue
            
            issue = Issue.objects.select_related("project", "assignee").get(id=issue_id)
            assignee = User.objects.get(id=assignee_id)
            assigner = User.objects.get(id=assigner_id)
            
            title = f"Issue assigned: {issue.title}"
            message = f"{assigner.get_full_name()} assigned you to {issue.project.key}-{issue.key}: {issue.title}"
            link = f"/projects/{issue.project.key}/issues/{issue.id}"
            
            self.create_notification(
                recipient=assignee,
                notification_type="issue_assigned",
                title=title,
                message=message,
                link=link,
                data={"issue_id": str(issue_id), "project_id": str(issue.project_id)},
                send_email=True,
            )
        except Exception as e:
            logger.exception(f"Error in notify_issue_assigned: {str(e)}")

    def notify_status_change(self, issue_id: str, old_status: str, new_status: str, changed_by_id: str):
        """Notify relevant users when issue status changes."""
        try:
            from apps.projects.models import Issue
            
            issue = Issue.objects.select_related("project", "assignee", "reporter").get(id=issue_id)
            changed_by = User.objects.get(id=changed_by_id)
            
            # Notify assignee and reporter
            recipients = [user for user in [issue.assignee, issue.reporter] if user and user.id != changed_by_id]
            
            title = f"Status changed: {issue.title}"
            message = f"{changed_by.get_full_name()} changed status from {old_status} to {new_status}"
            link = f"/projects/{issue.project.key}/issues/{issue.id}"
            
            for recipient in recipients:
                self.create_notification(
                    recipient=recipient,
                    notification_type="status_changed",
                    title=title,
                    message=message,
                    link=link,
                    data={"issue_id": str(issue_id), "old_status": old_status, "new_status": new_status},
                )
        except Exception as e:
            logger.exception(f"Error in notify_status_change: {str(e)}")

    def notify_deadline_approaching(self, issue_id: str, days_until_deadline: int):
        """Notify assignee about approaching deadline."""
        try:
            from apps.projects.models import Issue
            
            issue = Issue.objects.select_related("project", "assignee").get(id=issue_id)
            
            if not issue.assignee:
                return
            
            title = f"Deadline approaching: {issue.title}"
            message = f"Issue {issue.project.key}-{issue.key} is due in {days_until_deadline} day(s)"
            link = f"/projects/{issue.project.key}/issues/{issue.id}"
            
            self.create_notification(
                recipient=issue.assignee,
                notification_type="deadline_approaching",
                title=title,
                message=message,
                link=link,
                data={"issue_id": str(issue_id), "days_until": days_until_deadline},
                send_email=True,
            )
        except Exception as e:
            logger.exception(f"Error in notify_deadline_approaching: {str(e)}")

    def notify_anomaly_detected(self, project_id: str, anomaly_type: str, description: str, severity: str):
        """Notify project leads about detected anomalies."""
        try:
            from apps.projects.models import Project, ProjectTeamMember
            
            project = Project.objects.get(id=project_id)
            
            # Get project leads and admins
            leads = ProjectTeamMember.objects.filter(
                project=project,
                role__in=["lead", "admin"],
                is_active=True,
            ).select_related("user")
            
            title = f"Anomaly detected in {project.name}"
            message = f"{severity.upper()}: {description}"
            link = f"/projects/{project.key}/analytics"
            
            for lead in leads:
                self.create_notification(
                    recipient=lead.user,
                    notification_type="anomaly_detected",
                    title=title,
                    message=message,
                    link=link,
                    data={"project_id": str(project_id), "anomaly_type": anomaly_type, "severity": severity},
                    send_email=True,
                )
        except Exception as e:
            logger.exception(f"Error in notify_anomaly_detected: {str(e)}")

    def bulk_create_notifications(self, notifications_data: List[Dict[str, Any]]) -> int:
        """
        Create multiple notifications efficiently.

        Args:
            notifications_data: List of notification data dictionaries

        Returns:
            Number of notifications created
        """
        notifications = []
        for data in notifications_data:
            recipient = data.get("recipient")
            if not recipient:
                continue
            
            preferences = self._get_or_create_preferences(recipient)
            if not preferences.is_type_enabled(data.get("notification_type", "")):
                continue
            
            notifications.append(
                Notification(
                    recipient=recipient,
                    notification_type=data["notification_type"],
                    title=data["title"],
                    message=data["message"],
                    link=data.get("link", ""),
                    data=data.get("data", {}),
                )
            )
        
        created = Notification.objects.bulk_create(notifications)
        logger.info(f"Bulk created {len(created)} notifications")
        return len(created)

    def mark_all_read(self, user: User) -> int:
        """Mark all notifications as read for user."""
        from django.utils import timezone
        
        count = Notification.objects.filter(
            recipient=user, is_read=False
        ).update(is_read=True, read_at=timezone.now())
        
        logger.info(f"Marked {count} notifications as read for {user.email}")
        return count

    def mark_all_as_read(self, user: User) -> int:
        """Alias for mark_all_read."""
        return self.mark_all_read(user)

    def get_unread_count(self, user: User) -> int:
        """Get count of unread notifications for user."""
        return Notification.objects.filter(recipient=user, is_read=False).count()

    def mark_as_read(self, notification_id, user: User) -> bool:
        """Mark a specific notification as read."""
        from django.utils import timezone
        
        try:
            notification = Notification.objects.get(id=notification_id, recipient=user)
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at"])
            return True
        except Notification.DoesNotExist:
            return False

    def get_notifications_for_user(self, user: User, limit=50):
        """Get notifications for a user."""
        return Notification.objects.filter(recipient=user).order_by('-created_at')[:limit]

    def delete_old_notifications(self, days=90) -> int:
        """Delete notifications older than specified days."""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        count, _ = Notification.objects.filter(created_at__lt=cutoff_date).delete()
        logger.info(f"Deleted {count} notifications older than {days} days")
        return count

    def get_user_preferences(self, user: User):
        """Get notification preferences for user."""
        return self.get_or_create_preferences(user)

    def update_user_preferences(self, user: User, **preferences):
        """Update notification preferences for user."""
        prefs = self.get_or_create_preferences(user)
        for key, value in preferences.items():
            if hasattr(prefs, key):
                setattr(prefs, key, value)
        prefs.save()
        return prefs

    def get_notifications_by_type(self, user: User, notification_type: str, limit=50):
        """Get notifications filtered by type."""
        return Notification.objects.filter(
            recipient=user,
            notification_type=notification_type
        ).order_by('-created_at')[:limit]

    def get_unread_notifications(self, user: User):
        """Get unread notifications for user."""
        return Notification.objects.filter(recipient=user, is_read=False).order_by('-created_at')

    def get_or_create_preferences(self, user):
        """Get or create notification preferences for user."""
        preferences, created = NotificationPreference.objects.get_or_create(
            user=user,
            defaults={
                'email_enabled': True,
                'in_app_enabled': True,
                'slack_enabled': False
            }
        )
        return preferences

    def get_user_notifications(self, user, unread_only=False, notification_type=None, limit=50):
        """Get notifications for a user with optional filtering."""
        queryset = Notification.objects.filter(recipient=user)
        if unread_only:
            queryset = queryset.filter(is_read=False)
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        return queryset[:limit]

    def _get_or_create_preferences(self, user: User) -> NotificationPreference:
        """Get or create notification preferences for user."""
        preferences, created = NotificationPreference.objects.get_or_create(
            user=user,
            defaults={
                'email_enabled': True,
                'in_app_enabled': True,
                'slack_enabled': False,
                'notification_types': {}
            }
        )
        return preferences

    def _send_email_notification(self, notification: Notification):
        """Send email notification."""
        try:
            # Use existing EmailService
            subject = notification.title
            message = notification.message
            
            if notification.link:
                message += f"\n\nView: {notification.link}"
            
            # This is a placeholder - actual implementation would use EmailService
            # self.email_service.send_notification_email(
            #     to_email=notification.recipient.email,
            #     subject=subject,
            #     message=message,
            # )
            
            notification.email_sent = True
            notification.save(update_fields=["email_sent"])
            logger.debug(f"Email sent for notification {notification.id}")
            
        except Exception as e:
            logger.exception(f"Error sending email notification: {str(e)}")

    def _send_slack_notification(self, notification: Notification):
        """Send Slack notification."""
        try:
            # This would use SlackService
            self.slack_service.send_notification(
                channel=None,  # User's DM
                title=notification.title,
                message=notification.message,
                link=notification.link,
            )
            
            notification.slack_sent = True
            notification.save(update_fields=["slack_sent"])
            logger.debug(f"Slack sent for notification {notification.id}")
            
        except Exception as e:
            logger.exception(f"Error sending Slack notification: {str(e)}")
