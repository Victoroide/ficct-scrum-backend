from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .viewsets import (
    GitHubCommitViewSet,
    GitHubIntegrationViewSet,
    GitHubPullRequestViewSet,
)

router = DefaultRouter()
router.register(r"github", GitHubIntegrationViewSet, basename="github-integration")
router.register(r"commits", GitHubCommitViewSet, basename="github-commit")
router.register(
    r"pull-requests", GitHubPullRequestViewSet, basename="github-pull-request"
)

urlpatterns = [
    path("", include(router.urls)),
]
