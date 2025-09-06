from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .viewsets import SystemLogViewSet, ErrorLogViewSet

router = DefaultRouter()
router.register(r'system-logs', SystemLogViewSet, basename='system-logs')
router.register(r'error-logs', ErrorLogViewSet, basename='error-logs')

urlpatterns = [
    path('', include(router.urls)),
]
