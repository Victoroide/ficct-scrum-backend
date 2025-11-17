"""
Notification ViewSets for user alerts and preferences.

Provides REST API endpoints for notifications management.
"""

import logging

from django.utils import timezone

from django_filters import rest_framework as filters
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.serializers import (
    NotificationPreferenceSerializer,
    NotificationSerializer,
    NotificationUpdateSerializer,
)
from apps.notifications.services import SlackService

logger = logging.getLogger(__name__)


class NotificationPagination(PageNumberPagination):
    """Custom pagination for notifications."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class NotificationFilter(filters.FilterSet):
    """Filter for notifications."""

    notification_type = filters.CharFilter(
        field_name="notification_type", lookup_expr="exact"
    )
    is_read = filters.BooleanFilter(field_name="is_read")
    created_after = filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = Notification
        fields = ["notification_type", "is_read", "created_after", "created_before"]


@extend_schema_view(
    list=extend_schema(
        tags=["Notifications"],
        summary="List user notifications",
        description="Get paginated list of notifications for authenticated user with filtering and search",
        parameters=[
            OpenApiParameter(
                name="notification_type",
                type=str,
                description="Filter by notification type",
            ),
            OpenApiParameter(
                name="is_read", type=bool, description="Filter by read status"
            ),
            OpenApiParameter(
                name="created_after",
                type=str,
                description="Filter notifications created after this datetime (ISO 8601)",
            ),
            OpenApiParameter(
                name="created_before",
                type=str,
                description="Filter notifications created before this datetime (ISO 8601)",
            ),
            OpenApiParameter(
                name="search", type=str, description="Search in title and message"
            ),
            OpenApiParameter(
                name="ordering",
                type=str,
                description="Order by field (prefix with - for descending). Options: created_at, -created_at",
            ),
            OpenApiParameter(name="page", type=int, description="Page number"),
            OpenApiParameter(
                name="page_size",
                type=int,
                description="Number of results per page (max 100)",
            ),
        ],
    ),
    retrieve=extend_schema(
        tags=["Notifications"],
        summary="Get notification details",
        description="Retrieve a single notification by ID",
    ),
    update=extend_schema(
        tags=["Notifications"],
        summary="Update notification",
        description="Update notification (typically to mark as read/unread)",
    ),
    partial_update=extend_schema(
        tags=["Notifications"],
        summary="Partially update notification",
        description="Partially update notification (typically to mark as read/unread)",
    ),
    destroy=extend_schema(
        tags=["Notifications"],
        summary="Delete notification",
        description="Delete a notification",
    ),
)
class NotificationViewSet(viewsets.ModelViewSet):
    """
    User notifications management.

    Provides CRUD operations and custom actions for user notifications.
    All operations are scoped to the authenticated user.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    pagination_class = NotificationPagination
    filter_backends = [filters.DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = NotificationFilter
    search_fields = ["title", "message"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]  # Default: most recent first

    def get_queryset(self):
        """Return notifications for current user only."""
        return Notification.objects.filter(recipient=self.request.user).select_related(
            "recipient"
        )

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action in ["update", "partial_update"]:
            return NotificationUpdateSerializer
        return NotificationSerializer

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

            # Return updated notification data
            serializer = NotificationSerializer(notification)

            return Response(
                {
                    "message": "Notification marked as read",
                    "notification": serializer.data,
                },
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
        description="Mark all unread notifications as read for current user",
    )
    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        """Mark all notifications as read."""
        count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True, read_at=timezone.now())

        return Response(
            {
                "message": f"Marked {count} notifications as read",
                "updated_count": count,
            },
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

    @extend_schema(
        tags=["Notifications"],
        summary="Delete all read notifications",
        description="Bulk delete all read notifications for current user",
    )
    @action(detail=False, methods=["delete"], url_path="delete-read")
    def delete_read(self, request):
        """Delete all read notifications."""
        count, _ = Notification.objects.filter(
            recipient=request.user, is_read=True
        ).delete()

        return Response(
            {
                "message": f"Deleted {count} read notifications",
                "deleted_count": count,
            },
            status=status.HTTP_200_OK,
        )


class NotificationPreferenceViewSet(viewsets.ViewSet):
    """
    User notification preferences management.

    NotificationPreference has OneToOne relationship with User,
    so all operations use authenticated user's preferences (no pk needed).

    Endpoints:
    - GET /preferences/ - Get current user's preferences
    - PUT /preferences/update/ - Full update
    - PATCH /preferences/update/ - Partial update
    """

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationPreferenceSerializer

    # Enable PATCH on list endpoint
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    @extend_schema(
        tags=["Notifications"],
        summary="Get or Update notification preferences",
        description="GET: Retrieve current user's preferences. PATCH: Partially update preferences.",
        request=NotificationPreferenceSerializer,
        responses={
            200: NotificationPreferenceSerializer,
            400: {"type": "object", "properties": {"errors": {"type": "object"}}},
        },
    )
    def list(self, request):
        """
        Get user preferences (GET) or update them (PATCH).

        Handles both GET and PATCH on /preferences/ endpoint.
        This is needed because NotificationPreference is OneToOne with User,
        so there's no pk in the URL - we always work with current user's preferences.
        """
        # Handle PATCH request to /preferences/ (partial update)
        if request.method == "PATCH":
            return self._update_preferences(request, partial=True)

        # Handle GET request
        try:
            preferences, created = NotificationPreference.objects.get_or_create(
                user=request.user,
                defaults={
                    "email_enabled": True,
                    "in_app_enabled": True,
                    "notification_types": {},
                },
            )

            serializer = NotificationPreferenceSerializer(preferences)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error getting preferences: {str(e)}")
            return Response(
                {"error": "Failed to get preferences"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        tags=["Notifications"],
        summary="Create/Update notification preferences (POST)",
        description="Create or update current user's notification preferences via POST /preferences/",
        request=NotificationPreferenceSerializer,
        responses={
            200: NotificationPreferenceSerializer,
            400: {"type": "object", "properties": {"errors": {"type": "object"}}},
        },
    )
    def create(self, request):
        """
        Handle POST to /preferences/ endpoint.

        Since this is OneToOne with user, treat POST as update operation.
        """
        return self._update_preferences(request, partial=True)

    def _update_preferences(self, request, partial=True):
        """Internal method to update preferences."""
        try:
            preferences, created = NotificationPreference.objects.get_or_create(
                user=request.user
            )

            serializer = NotificationPreferenceSerializer(
                preferences, data=request.data, partial=partial
            )

            if serializer.is_valid():
                serializer.save()
                return Response(
                    {
                        "message": "Preferences updated successfully",
                        "preferences": serializer.data,
                    },
                    status=status.HTTP_200_OK,
                )

            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as e:
            logger.exception(f"Error updating preferences: {str(e)}")
            return Response(
                {"error": "Failed to update preferences"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        tags=["Notifications"],
        summary="Update notification preferences",
        description="Update current user's notification preferences (supports partial updates via PATCH)",
        request=NotificationPreferenceSerializer,
        responses={
            200: NotificationPreferenceSerializer,
            400: {"type": "object", "properties": {"errors": {"type": "object"}}},
        },
    )
    @action(detail=False, methods=["put", "patch"], url_path="update")
    def update_preferences(self, request):
        """
        Update user preferences.

        Supports both PUT (full update) and PATCH (partial update).
        Works on /api/v1/notifications/preferences/update/ endpoint.
        """
        try:
            preferences, created = NotificationPreference.objects.get_or_create(
                user=request.user
            )

            # Use serializer for validation and update
            # partial=True allows PATCH to update only provided fields
            is_partial = request.method == "PATCH"
            serializer = NotificationPreferenceSerializer(
                preferences, data=request.data, partial=is_partial
            )

            if serializer.is_valid():
                serializer.save()
                return Response(
                    {
                        "message": "Preferences updated successfully",
                        "preferences": serializer.data,
                    },
                    status=status.HTTP_200_OK,
                )

            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
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
