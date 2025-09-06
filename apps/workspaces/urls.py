from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .viewsets import WorkspaceViewSet, WorkspaceMemberViewSet

router = DefaultRouter()
router.register(r'workspaces', WorkspaceViewSet, basename='workspaces')
router.register(r'members', WorkspaceMemberViewSet, basename='workspace-members')

urlpatterns = [
    path('', include(router.urls)),
]
