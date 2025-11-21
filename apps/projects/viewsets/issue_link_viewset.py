from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.logging.services import LoggerService
from apps.projects.models import IssueLink
from apps.projects.permissions import CanAccessProject, IsProjectTeamMember
from apps.projects.serializers import IssueLinkSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["Issues"],
        operation_id="issue_links_list",
        summary="List Issue Links",
        description="Retrieve all links for a specific issue",
    ),
    retrieve=extend_schema(
        tags=["Issues"],
        operation_id="issue_links_retrieve",
        summary="Get Issue Link Details",
        description="Retrieve details of a specific issue link",
    ),
    create=extend_schema(
        tags=["Issues"],
        operation_id="issue_links_create",
        summary="Create Issue Link ",
        description="Link issues together. Creates reciprocal link automatically (e.g., 'blocks' creates 'blocked_by').",  # noqa: E501
    ),
    destroy=extend_schema(
        tags=["Issues"],
        operation_id="issue_links_destroy",
        summary="Delete Issue Link",
        description="Delete an issue link and its reciprocal relationship",
    ),
)
class IssueLinkViewSet(viewsets.ModelViewSet):
    serializer_class = IssueLinkSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):
        issue_id = self.kwargs.get("issue_pk")
        return IssueLink.objects.filter(source_issue_id=issue_id).select_related(
            "source_issue", "target_issue", "created_by"
        )

    def get_permissions(self):
        if self.action in ["create", "destroy"]:
            return [IsAuthenticated(), IsProjectTeamMember()]
        return [IsAuthenticated(), CanAccessProject()]

    def create(self, request, *args, **kwargs):
        issue_id = self.kwargs.get("issue_pk")
        request.data["source_issue_id"] = issue_id
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        link = serializer.save()

        LoggerService.log_info(
            action="issue_linked",
            user=self.request.user,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            details={
                "link_id": str(link.id),
                "source_issue_key": link.source_issue.full_key,
                "target_issue_key": link.target_issue.full_key,
                "link_type": link.link_type,
            },
        )

    def perform_destroy(self, instance):
        reciprocal_link_type = IssueLink.get_reciprocal_link_type(instance.link_type)

        LoggerService.log_info(
            action="issue_link_deleted",
            user=self.request.user,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            details={
                "link_id": str(instance.id),
                "source_issue_key": instance.source_issue.full_key,
                "target_issue_key": instance.target_issue.full_key,
                "link_type": instance.link_type,
            },
        )

        IssueLink.objects.filter(
            source_issue=instance.target_issue,
            target_issue=instance.source_issue,
            link_type=reciprocal_link_type,
        ).delete()

        instance.delete()
