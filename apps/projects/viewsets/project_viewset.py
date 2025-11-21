import logging
from uuid import UUID

from django.db import transaction

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.logging.services import LoggerService
from apps.projects.models import Project
from apps.projects.permissions import (
    CanAccessProject,
    IsProjectLeadOrAdmin,
)
from apps.projects.serializers import ProjectSerializer
from base.utils.file_handlers import upload_project_file_to_s3

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        tags=["Projects"],
        operation_id="projects_list",
        summary="List Projects",
        description=(
            "Returns projects where the authenticated user is a workspace member. "
            "Supports filtering by workspace and organization."
        ),
        parameters=[
            OpenApiParameter(
                name="workspace",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter projects by workspace UUID",
                required=False,
            ),
            OpenApiParameter(
                name="organization",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter projects by organization UUID",
                required=False,
            ),
        ],
    ),
    retrieve=extend_schema(
        tags=["Projects"],
        operation_id="projects_retrieve",
        summary="Get Project Details",
    ),
    create=extend_schema(
        tags=["Projects"],
        operation_id="projects_create",
        summary="Create Project",
        description=(
            "**MAJOR CHANGE:** Automatically creates 3 default workflow statuses: "
            "'To Do' (initial), 'In Progress', 'Done' (final). "
            "Creator is automatically assigned as project lead. "
            "Frontend must fetch workflow statuses immediately after creation "
            "and should NOT manually create statuses."
        ),
    ),
    update=extend_schema(
        tags=["Projects"], operation_id="projects_update", summary="Update Project"
    ),
    partial_update=extend_schema(
        tags=["Projects"],
        operation_id="projects_partial_update",
        summary="Partial Update Project",
    ),
    destroy=extend_schema(
        tags=["Projects"], operation_id="projects_destroy", summary="Delete Project"
    ),
)
class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        """Assign permissions based on action."""
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsProjectLeadOrAdmin()]
        elif self.action in ["retrieve", "list"]:
            return [IsAuthenticated(), CanAccessProject()]
        return [IsAuthenticated()]

    def get_queryset(self):
        """
        Filter projects based on user membership and query parameters.

        Query Parameters:
            - workspace: UUID of workspace to filter by
            - organization: UUID of organization to filter by

        Returns only projects where user is a workspace member.
        """
        # Base queryset: user must be a member of the workspace
        queryset = (
            Project.objects.filter(
                workspace__members__user=self.request.user,
                workspace__members__is_active=True,
            )
            .select_related(
                "workspace", "workspace__organization", "lead", "created_by"
            )
            .prefetch_related("team_members", "team_members__user")
            .distinct()
        )

        # Filter by workspace if provided
        workspace_id = self.request.query_params.get("workspace")
        if workspace_id:
            try:
                # Validate UUID format
                UUID(workspace_id)

                # Apply workspace filter
                queryset = queryset.filter(workspace_id=workspace_id)

                logger.info(
                    f"[PROJECT FILTER] User {self.request.user.email} filtering by workspace: {workspace_id}, "  # noqa: E501
                    f"Result count: {queryset.count()}"
                )

            except ValueError:
                logger.warning(
                    f"[PROJECT FILTER] Invalid workspace UUID format: {workspace_id} "
                    f"from user {self.request.user.email}"
                )
                raise ValidationError(
                    {"workspace": "Invalid workspace ID format. Must be a valid UUID."}
                )

        # Filter by organization if provided
        organization_id = self.request.query_params.get("organization")
        if organization_id:
            try:
                # Validate UUID format
                UUID(organization_id)

                # Apply organization filter
                queryset = queryset.filter(workspace__organization_id=organization_id)

                logger.info(
                    f"[PROJECT FILTER] User {self.request.user.email} filtering by organization: {organization_id}, "  # noqa: E501
                    f"Result count: {queryset.count()}"
                )

            except ValueError:
                logger.warning(
                    f"[PROJECT FILTER] Invalid organization UUID format: {organization_id} "  # noqa: E501
                    f"from user {self.request.user.email}"
                )
                raise ValidationError(
                    {
                        "organization": "Invalid organization ID format. Must be a valid UUID."  # noqa: E501
                    }
                )

        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        # Create project with creator as lead
        project = serializer.save(created_by=self.request.user, lead=self.request.user)

        # Note: Default workflow statuses, issue types, transitions, and configuration
        # are automatically created by signals in apps/projects/signals.py
        # No manual creation needed here to avoid duplicates

        LoggerService.log_info(
            action="project_created_with_workflows",
            user=self.request.user,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            details={
                "project_id": str(project.id),
                "project_key": project.key,
                "project_name": project.name,
                "workspace_id": str(project.workspace.id),
                "workflow_statuses_created": len(default_statuses),  # noqa: F821
            },
        )

    @extend_schema(
        tags=["Projects"],
        operation_id="projects_upload_attachment",
        summary="Upload Project Attachment",
    )
    @action(detail=True, methods=["post"], url_path="upload-attachment")
    def upload_attachment(self, request, pk=None):
        project = self.get_object()
        if "attachment" not in request.FILES:
            return Response(
                {"error": "No attachment file provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        attachment_file = request.FILES["attachment"]
        try:
            attachment_path = upload_project_file_to_s3(attachment_file, project.id)
            project.attachments = attachment_path
            project.save()
            return Response(
                {"attachment_url": project.attachments.url}, status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
