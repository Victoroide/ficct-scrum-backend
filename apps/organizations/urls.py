from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .viewsets import OrganizationViewSet, OrganizationMemberViewSet

router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet, basename='organizations')
router.register(r'members', OrganizationMemberViewSet, basename='organization-members')

urlpatterns = [
    path('', include(router.urls)),
]
