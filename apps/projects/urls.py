from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .viewsets import ProjectViewSet, ProjectConfigViewSet

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='projects')
router.register(r'configs', ProjectConfigViewSet, basename='project-configs')

urlpatterns = [
    path('', include(router.urls)),
]
