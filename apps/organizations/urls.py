from django.urls import include, path

from rest_framework.routers import DefaultRouter

from .viewsets import OrganizationMemberViewSet, OrganizationViewSet

router = DefaultRouter()
router.register(r"organizations", OrganizationViewSet, basename="organizations")
router.register(r"members", OrganizationMemberViewSet, basename="organization-members")

urlpatterns = [
    path("", include(router.urls)),
]
