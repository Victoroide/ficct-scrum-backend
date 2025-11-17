"""
Management command to create test notifications for development/testing.

Usage:
    python manage.py create_test_notifications
    python manage.py create_test_notifications --user <email>
    python manage.py create_test_notifications --count 10
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.notifications.models import Notification

User = get_user_model()


class Command(BaseCommand):
    """Create test notifications for development."""

    help = "Create test notifications for development and testing"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--user",
            type=str,
            help="Email of user to create notifications for",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=5,
            help="Number of notifications to create",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        user_email = options.get("user")
        count = options.get("count", 5)

        # Get target user
        if user_email:
            try:
                user = User.objects.get(email=user_email)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"User with email {user_email} not found")
                )
                return
        else:
            # Get first user
            user = User.objects.first()
            if not user:
                self.stdout.write(self.style.ERROR("No users found in database"))
                return

        self.stdout.write(
            self.style.SUCCESS(f"Creating {count} test notifications for {user.email}")
        )

        # Test notification data
        test_notifications = [
            {
                "notification_type": "issue_assigned",
                "title": "Issue Assigned to You",
                "message": "You have been assigned to issue PROJ-123: Fix login bug",
                "link": "/projects/PROJ/issues/PROJ-123",
                "data": {"issue_id": "test-uuid-1", "project_key": "PROJ"},
            },
            {
                "notification_type": "issue_commented",
                "title": "New Comment on Issue",
                "message": "John Doe commented on issue PROJ-456: 'Please review the changes'",
                "link": "/projects/PROJ/issues/PROJ-456",
                "data": {"issue_id": "test-uuid-2", "comment_id": "test-comment-1"},
            },
            {
                "notification_type": "sprint_started",
                "title": "Sprint Started",
                "message": "Sprint 'Q4 Development Sprint' has been started",
                "link": "/projects/PROJ/sprints/sprint-uuid",
                "data": {
                    "sprint_id": "test-sprint-1",
                    "sprint_name": "Q4 Development Sprint",
                },
            },
            {
                "notification_type": "status_changed",
                "title": "Issue Status Changed",
                "message": "Issue PROJ-789 moved from 'To Do' to 'In Progress'",
                "link": "/projects/PROJ/issues/PROJ-789",
                "data": {
                    "issue_id": "test-uuid-3",
                    "old_status": "To Do",
                    "new_status": "In Progress",
                },
            },
            {
                "notification_type": "deadline_approaching",
                "title": "Deadline Approaching",
                "message": "Issue PROJ-321 is due in 2 days",
                "link": "/projects/PROJ/issues/PROJ-321",
                "data": {"issue_id": "test-uuid-4", "days_remaining": 2},
            },
            {
                "notification_type": "mention",
                "title": "You Were Mentioned",
                "message": "@{} mentioned you in a comment on PROJ-555".format(
                    user.email.split("@")[0]
                ),
                "link": "/projects/PROJ/issues/PROJ-555",
                "data": {
                    "issue_id": "test-uuid-5",
                    "mentioned_by": "john.doe@example.com",
                },
            },
            {
                "notification_type": "ai_insight",
                "title": "AI Detected Pattern",
                "message": "Sprint velocity decreased by 30% compared to last sprint",
                "link": "/projects/PROJ/reports/velocity",
                "data": {"metric": "velocity", "change": -30},
            },
            {
                "notification_type": "anomaly_detected",
                "title": "Anomaly Detected",
                "message": "Unusual activity detected: 5 issues moved to 'Done' in the last hour",
                "link": "/projects/PROJ/dashboard",
                "data": {"issue_count": 5, "timeframe": "1h"},
            },
            {
                "notification_type": "sprint_completed",
                "title": "Sprint Completed",
                "message": "Sprint 'Q3 Maintenance Sprint' has been completed with 85% completion rate",
                "link": "/projects/PROJ/sprints/completed",
                "data": {"sprint_id": "test-sprint-2", "completion_rate": 85},
            },
            {
                "notification_type": "issue_updated",
                "title": "Issue Updated",
                "message": "Issue PROJ-999 has been updated by Jane Smith",
                "link": "/projects/PROJ/issues/PROJ-999",
                "data": {
                    "issue_id": "test-uuid-6",
                    "updated_by": "jane.smith@example.com",
                },
            },
        ]

        # Create notifications
        created_count = 0
        for i in range(count):
            notification_data = test_notifications[i % len(test_notifications)]

            notification = Notification.objects.create(
                recipient=user,
                notification_type=notification_data["notification_type"],
                title=notification_data["title"],
                message=notification_data["message"],
                link=notification_data["link"],
                data=notification_data["data"],
                is_read=(i % 3 == 0),  # Every 3rd notification is read
            )

            created_count += 1
            self.stdout.write(self.style.SUCCESS(f"✓ Created: {notification.title}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Successfully created {created_count} test notifications for {user.email}"
            )
        )

        # Show stats
        total = Notification.objects.filter(recipient=user).count()
        unread = Notification.objects.filter(recipient=user, is_read=False).count()

        self.stdout.write(
            self.style.SUCCESS(
                f"\n📊 User notification stats:"
                f"\n   - Total: {total}"
                f"\n   - Unread: {unread}"
                f"\n   - Read: {total - unread}"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n🔗 Test the API:"
                f"\n   - List all: GET /api/v1/notifications/"
                f"\n   - Unread only: GET /api/v1/notifications/?is_read=false"
                f"\n   - By type: GET /api/v1/notifications/?notification_type=issue_assigned"
                f"\n   - Search: GET /api/v1/notifications/?search=sprint"
                f"\n   - Unread count: GET /api/v1/notifications/unread-count/"
            )
        )
