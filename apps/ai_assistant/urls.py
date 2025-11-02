"""URL configuration for AI Assistant app."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.ai_assistant.viewsets import AIAssistantViewSet

router = DefaultRouter()
router.register(r"", AIAssistantViewSet, basename="ai-assistant")

urlpatterns = [
    path("", include(router.urls)),
]
