"""URL configuration for Machine Learning app."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.ml.viewsets import MLViewSet

router = DefaultRouter()
router.register(r"", MLViewSet, basename="ml")

urlpatterns = [
    path("", include(router.urls)),
]
