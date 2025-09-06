from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .viewsets import (
    SystemLogViewSet,
    ErrorLogViewSet,
    AuditLogViewSet,
    AlertRuleViewSet,
    AlertViewSet,
)

router = DefaultRouter()
router.register(r'system-logs', SystemLogViewSet, basename='system-logs')
router.register(r'error-logs', ErrorLogViewSet, basename='error-logs')
router.register(r'audit-logs', AuditLogViewSet, basename='audit-logs')
router.register(r'alert-rules', AlertRuleViewSet, basename='alert-rules')
router.register(r'alerts', AlertViewSet, basename='alerts')

urlpatterns = [
    path('', include(router.urls)),
]
