from django.urls import include, path

from rest_framework.routers import DefaultRouter

from .viewsets import ErrorLogViewSet, SystemLogViewSet

router = DefaultRouter()
router.register(r"system-logs", SystemLogViewSet, basename="system-logs")
router.register(r"error-logs", ErrorLogViewSet, basename="error-logs")

urlpatterns = [
    path("", include(router.urls)),
]
