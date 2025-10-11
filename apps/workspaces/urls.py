from django.urls import include, path

from rest_framework.routers import DefaultRouter

from .viewsets import WorkspaceMemberViewSet, WorkspaceViewSet

router = DefaultRouter()
# Register members FIRST to avoid route conflicts with workspace detail actions
router.register(r"members", WorkspaceMemberViewSet, basename="workspace-members")
router.register(r"", WorkspaceViewSet, basename="workspaces")

urlpatterns = [
    path("", include(router.urls)),
]
