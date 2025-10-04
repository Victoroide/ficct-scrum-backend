from django.urls import include, path

from rest_framework.routers import DefaultRouter

from .viewsets import ProjectConfigViewSet, ProjectViewSet

router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="projects")
router.register(r"configs", ProjectConfigViewSet, basename="project-configs")

urlpatterns = [
    path("", include(router.urls)),
]
