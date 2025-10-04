from django.urls import include, path

from rest_framework.routers import DefaultRouter

from .viewsets import WorkspaceMemberViewSet, WorkspaceViewSet

router = DefaultRouter()
router.register(r"", WorkspaceViewSet, basename="workspaces")
router.register(r"members", WorkspaceMemberViewSet, basename="workspace-members")

urlpatterns = [
    path("", include(router.urls)),
]
