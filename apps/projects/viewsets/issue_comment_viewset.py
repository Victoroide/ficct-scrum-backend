from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.logging.services import LoggerService
from apps.projects.models import Issue, IssueComment
from apps.projects.permissions import CanAccessProject, IsProjectTeamMember
from apps.projects.serializers import IssueCommentSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["Issues"],
        operation_id="issue_comments_list",
        summary="List Issue Comments",
        description="Retrieve all comments for a specific issue",
    ),
    retrieve=extend_schema(
        tags=["Issues"],
        operation_id="issue_comments_retrieve",
        summary="Get Comment Details",
        description="Retrieve details of a specific comment",
    ),
    create=extend_schema(
        tags=["Issues"],
        operation_id="issue_comments_create",
        summary="Add Comment to Issue ",
        description="Add a new comment to an issue",
    ),
    update=extend_schema(
        tags=["Issues"],
        operation_id="issue_comments_update",
        summary="Edit Comment",
        description="Update an existing comment (author only)",
    ),
    partial_update=extend_schema(
        tags=["Issues"],
        operation_id="issue_comments_partial_update",
        summary="Partial Update Comment",
        description="Partially update an existing comment (author only)",
    ),
    destroy=extend_schema(
        tags=["Issues"],
        operation_id="issue_comments_destroy",
        summary="Delete Comment",
        description="Delete a comment (author or project admin)",
    ),
)
class IssueCommentViewSet(viewsets.ModelViewSet):
    serializer_class = IssueCommentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        issue_id = self.kwargs.get("issue_pk")
        return IssueComment.objects.filter(issue_id=issue_id).select_related(
            "author", "issue"
        )

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), IsProjectTeamMember()]
        elif self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated()]
        return [IsAuthenticated(), CanAccessProject()]

    def perform_create(self, serializer):
        issue_id = self.kwargs.get("issue_pk")
        try:
            issue = Issue.objects.get(id=issue_id)
        except Issue.DoesNotExist:
            return Response(
                {"error": "Issue does not exist"}, status=status.HTTP_404_NOT_FOUND
            )

        comment = serializer.save(issue=issue, author=self.request.user)

        LoggerService.log_info(
            action="comment_added",
            user=self.request.user,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            details={
                "comment_id": str(comment.id),
                "issue_id": str(issue.id),
                "issue_key": issue.full_key,
            },
        )

    def perform_update(self, serializer):
        comment = self.get_object()

        if comment.author != self.request.user:
            return Response(
                {"error": "You can only edit your own comments"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer.save()

    def perform_destroy(self, instance):
        if not instance.can_delete(self.request.user):
            return Response(
                {"error": "You do not have permission to delete this comment"},
                status=status.HTTP_403_FORBIDDEN,
            )

        LoggerService.log_info(
            action="comment_deleted",
            user=self.request.user,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            details={
                "comment_id": str(instance.id),
                "issue_id": str(instance.issue.id),
                "issue_key": instance.issue.full_key,
            },
        )

        instance.delete()
