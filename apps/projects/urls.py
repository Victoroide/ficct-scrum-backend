from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .viewsets import (
    BoardViewSet,
    IssueAttachmentViewSet,
    IssueCommentViewSet,
    IssueLinkViewSet,
    IssueTypeViewSet,
    IssueViewSet,
    ProjectConfigViewSet,
    ProjectViewSet,
    SprintViewSet,
    WorkflowStatusViewSet,
)

router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"configs", ProjectConfigViewSet, basename="project-config")
router.register(r"issues", IssueViewSet, basename="issue")
router.register(r"issue-types", IssueTypeViewSet, basename="issue-type")
router.register(r"workflow-statuses", WorkflowStatusViewSet, basename="workflow-status")
router.register(r"sprints", SprintViewSet, basename="sprint")
router.register(r"boards", BoardViewSet, basename="board")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "issues/<uuid:issue_pk>/comments/",
        IssueCommentViewSet.as_view({"get": "list", "post": "create"}),
        name="issue-comment-list",
    ),
    path(
        "issues/<uuid:issue_pk>/comments/<uuid:pk>/",
        IssueCommentViewSet.as_view(
            {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
        ),
        name="issue-comment-detail",
    ),
    path(
        "issues/<uuid:issue_pk>/attachments/",
        IssueAttachmentViewSet.as_view({"get": "list", "post": "create"}),
        name="issue-attachment-list",
    ),
    path(
        "issues/<uuid:issue_pk>/attachments/<uuid:pk>/",
        IssueAttachmentViewSet.as_view({"get": "retrieve", "delete": "destroy"}),
        name="issue-attachment-detail",
    ),
    path(
        "issues/<uuid:issue_pk>/links/",
        IssueLinkViewSet.as_view({"get": "list", "post": "create"}),
        name="issue-link-list",
    ),
    path(
        "issues/<uuid:issue_pk>/links/<uuid:pk>/",
        IssueLinkViewSet.as_view({"get": "retrieve", "delete": "destroy"}),
        name="issue-link-detail",
    ),
]
