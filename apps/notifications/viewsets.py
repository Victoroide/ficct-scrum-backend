"""
Notification ViewSets for user alerts and preferences.

Provides REST API endpoints for notifications management.
"""

import logging

from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.services import SlackService

logger = logging.getLogger(__name__)


class NotificationViewSet(viewsets.ModelViewSet):
    """User notifications management."""

    permission_classes = [IsAuthenticated]
    serializer_class = None  # TODO: Create NotificationSerializer

    def get_queryset(self):
        """Return notifications for current user."""
        return Notification.objects.filter(recipient=self.request.user)

    @extend_schema(
        tags=["Notifications"],
        summary="List user notifications",
        description="Get all notifications for the authenticated user",
    )
    def list(self, request):
        """List notifications."""
        queryset = self.get_queryset()
        
        # Filter by read status if specified
        is_read = request.query_params.get("is_read")
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == "true")
        
        # Limit results
        limit = int(request.query_params.get("limit", 50))
        queryset = queryset[:limit]
        
        # Serialize and return
        data = [
            {
                "id": str(n.id),
                "type": n.notification_type,
                "title": n.title,
                "message": n.message,
                "link": n.link,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
            }
            for n in queryset
        ]
        
        return Response({"count": len(data), "results": data}, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Notifications"],
        summary="Mark notification as read",
        description="Mark a single notification as read",
    )
    @action(detail=True, methods=["patch"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        """Mark notification as read."""
        try:
            notification = self.get_queryset().get(pk=pk)
            notification.mark_as_read()
            
            return Response(
                {"message": "Notification marked as read"},
                status=status.HTTP_200_OK,
            )
        except Notification.DoesNotExist:
            return Response(
                {"error": "Notification not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        tags=["Notifications"],
        summary="Mark all notifications as read",
        description="Mark all user notifications as read",
    )
    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        """Mark all notifications as read."""
        from django.utils import timezone
        
        count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True, read_at=timezone.now())
        
        return Response(
            {"message": f"Marked {count} notifications as read"},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Notifications"],
        summary="Get unread count",
        description="Get count of unread notifications for current user",
    )
    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        """Get unread notification count."""
        count = self.get_queryset().filter(is_read=False).count()
        return Response({"unread_count": count}, status=status.HTTP_200_OK)


class NotificationPreferenceViewSet(viewsets.ViewSet):
    """User notification preferences management."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Notifications"],
        summary="Get notification preferences",
        description="Get current user's notification preferences",
    )
    def list(self, request):
        """Get user preferences."""
        try:
            preferences, created = NotificationPreference.objects.get_or_create(
                user=request.user,
                defaults={
                    "email_enabled": True,
                    "in_app_enabled": True,
                    "notification_types": {},
                },
            )
            
            data = {
                "id": str(preferences.id),
                "email_enabled": preferences.email_enabled,
                "in_app_enabled": preferences.in_app_enabled,
                "slack_enabled": preferences.slack_enabled,
                "notification_types": preferences.notification_types,
                "digest_enabled": preferences.digest_enabled,
                "quiet_hours_enabled": preferences.quiet_hours_enabled,
            }
            
            return Response(data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.exception(f"Error getting preferences: {str(e)}")
            return Response(
                {"error": "Failed to get preferences"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        tags=["Notifications"],
        summary="Update notification preferences",
        description="Update user's notification preferences",
    )
    def update(self, request, pk=None):
        """Update user preferences."""
        try:
            preferences, created = NotificationPreference.objects.get_or_create(
                user=request.user
            )
            
            # Update fields
            if "email_enabled" in request.data:
                preferences.email_enabled = request.data["email_enabled"]
            if "in_app_enabled" in request.data:
                preferences.in_app_enabled = request.data["in_app_enabled"]
            if "slack_enabled" in request.data:
                preferences.slack_enabled = request.data["slack_enabled"]
            if "notification_types" in request.data:
                preferences.notification_types = request.data["notification_types"]
            if "digest_enabled" in request.data:
                preferences.digest_enabled = request.data["digest_enabled"]
            if "quiet_hours_enabled" in request.data:
                preferences.quiet_hours_enabled = request.data["quiet_hours_enabled"]
            
            preferences.save()
            
            return Response(
                {"message": "Preferences updated successfully"},
                status=status.HTTP_200_OK,
            )
            
        except Exception as e:
            logger.exception(f"Error updating preferences: {str(e)}")
            return Response(
                {"error": "Failed to update preferences"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SlackIntegrationViewSet(viewsets.ViewSet):
    """Slack integration management."""

    permission_classes = [IsAuthenticated]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.slack_service = SlackService()

    @extend_schema(
        tags=["Notifications"],
        summary="Test Slack webhook",
        description="Test Slack integration by sending a test message",
    )
    @action(detail=False, methods=["post"], url_path="test")
    def test_webhook(self, request):
        """Test Slack webhook configuration."""
        try:
            webhook_url = request.data.get("webhook_url")
            
            if not webhook_url:
                return Response(
                    {"error": "webhook_url is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            success = self.slack_service.test_webhook(webhook_url)
            
            if success:
                return Response(
                    {"message": "Slack webhook test successful"},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"error": "Slack webhook test failed"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
                
        except Exception as e:
            logger.exception(f"Error testing Slack webhook: {str(e)}")
            return Response(
                {"error": "Failed to test webhook"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
