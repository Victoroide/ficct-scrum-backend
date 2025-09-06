from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .viewsets import OrganizationViewSet, InvitationViewSet, WorkspaceViewSet

router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet, basename='organizations')
router.register(r'invitations', InvitationViewSet, basename='invitations')
router.register(r'workspaces', WorkspaceViewSet, basename='workspaces')

urlpatterns = [
    path('', include(router.urls)),
]
