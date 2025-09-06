from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .viewsets import (
    ProjectViewSet,
    IssueTypeViewSet,
    WorkflowStatusViewSet,
    WorkflowTransitionViewSet
)

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='projects')
router.register(r'issue-types', IssueTypeViewSet, basename='issue-types')
router.register(r'workflow-statuses', WorkflowStatusViewSet, basename='workflow-statuses')
router.register(r'workflow-transitions', WorkflowTransitionViewSet, basename='workflow-transitions')

urlpatterns = [
    path('', include(router.urls)),
]
