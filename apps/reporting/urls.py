from django.urls import include, path

from rest_framework.routers import DefaultRouter

from .viewsets import (
    ActivityLogViewSet,
    DiagramViewSet,
    ReportViewSet,
    SavedFilterViewSet,
)

router = DefaultRouter()
router.register(r"filters", SavedFilterViewSet, basename="saved-filter")
router.register(r"activity", ActivityLogViewSet, basename="activity-log")
router.register(r"diagrams", DiagramViewSet, basename="diagram")
router.register(r"reports", ReportViewSet, basename="report")

urlpatterns = [
    path("", include(router.urls)),
]
