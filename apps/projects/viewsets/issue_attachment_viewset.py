from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.logging.services import LoggerService
from apps.projects.models import Issue, IssueAttachment
from apps.projects.permissions import CanAccessProject, IsProjectTeamMember
from apps.projects.serializers import IssueAttachmentSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["Issues"],
        operation_id="issue_attachments_list",
        summary="List Issue Attachments",
        description="Retrieve all attachments for a specific issue",
    ),
    retrieve=extend_schema(
        tags=["Issues"],
        operation_id="issue_attachments_retrieve",
        summary="Get Attachment Details",
        description="Retrieve details of a specific issue attachment",
    ),
    create=extend_schema(
        tags=["Issues"],
        operation_id="issue_attachments_create",
        summary="Upload Attachment to Issue ",
        description="Upload a file attachment to an issue",
    ),
    destroy=extend_schema(
        tags=["Issues"],
        operation_id="issue_attachments_destroy",
        summary="Delete Attachment",
        description="Delete an attachment from an issue",
    ),
)
class IssueAttachmentViewSet(viewsets.ModelViewSet):
    serializer_class = IssueAttachmentSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):
        issue_id = self.kwargs.get("issue_pk")
        return IssueAttachment.objects.filter(issue_id=issue_id).select_related("uploaded_by", "issue")

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), IsProjectTeamMember()]
        elif self.action == "destroy":
            return [IsAuthenticated()]
        return [IsAuthenticated(), CanAccessProject()]

    def perform_create(self, serializer):
        issue_id = self.kwargs.get("issue_pk")
        try:
            issue = Issue.objects.get(id=issue_id)
        except Issue.DoesNotExist:
            return Response(
                {"error": "Issue does not exist"},
                status=status.HTTP_404_NOT_FOUND
            )

        attachment = serializer.save(issue=issue)

        LoggerService.log_info(
            action="attachment_uploaded",
            user=self.request.user,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            details={
                "attachment_id": str(attachment.id),
                "issue_id": str(issue.id),
                "issue_key": issue.full_key,
                "filename": attachment.filename,
                "file_size": attachment.file_size,
            },
        )

    def perform_destroy(self, instance):
        from apps.projects.models import ProjectTeamMember

        if instance.uploaded_by != self.request.user:
            project_member = ProjectTeamMember.objects.filter(
                project=instance.issue.project,
                user=self.request.user,
                is_active=True
            ).first()

            if not project_member or not project_member.can_manage_project:
                return Response(
                    {"error": "You can only delete your own attachments"},
                    status=status.HTTP_403_FORBIDDEN
                )

        LoggerService.log_info(
            action="attachment_deleted",
            user=self.request.user,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            details={
                "attachment_id": str(instance.id),
                "issue_id": str(instance.issue.id),
                "issue_key": instance.issue.full_key,
                "filename": instance.filename,
            },
        )

        instance.delete()
