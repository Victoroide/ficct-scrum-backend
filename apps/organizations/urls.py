from django.urls import include, path

from rest_framework.routers import DefaultRouter

from .viewsets import (
    OrganizationInvitationViewSet,
    OrganizationMemberViewSet,
    OrganizationViewSet,
)

router = DefaultRouter()
router.register(r"organizations", OrganizationViewSet, basename="organizations")
router.register(r"members", OrganizationMemberViewSet, basename="organization-members")
router.register(r"invitations", OrganizationInvitationViewSet, basename="invitations")

urlpatterns = [
    path("", include(router.urls)),
]
