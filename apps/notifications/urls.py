"""URL configuration for Notifications app."""

from django.urls import include, path

from rest_framework.routers import DefaultRouter

from apps.notifications.viewsets import (
    NotificationPreferenceViewSet,
    NotificationViewSet,
    SlackIntegrationViewSet,
)

router = DefaultRouter()
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(
    r"preferences", NotificationPreferenceViewSet, basename="notification-preference"
)
router.register(r"slack", SlackIntegrationViewSet, basename="slack")

urlpatterns = [
    path("", include(router.urls)),
]
