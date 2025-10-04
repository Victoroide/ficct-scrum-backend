from django.db import transaction

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.logging.services import LoggerService
from apps.projects.models import Project, WorkflowStatus
from apps.projects.permissions import (
    CanAccessProject,
    IsProjectLeadOrAdmin,
    IsProjectMember,
)
from apps.projects.serializers import ProjectSerializer
from base.utils.file_handlers import upload_project_file_to_s3


@extend_schema_view(
    list=extend_schema(
        tags=["Projects"], operation_id="projects_list", summary="List Projects"
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
        return Project.objects.filter(
            workspace__members__user=self.request.user,
            workspace__members__is_active=True,
        ).distinct()

    @transaction.atomic
    def perform_create(self, serializer):
        # Create project with creator as lead
        project = serializer.save(created_by=self.request.user, lead=self.request.user)

        # Create default workflow statuses
        default_statuses = [
            WorkflowStatus(
                project=project,
                name="To Do",
                category="to_do",
                description="Tasks that are ready to be worked on",
                color="#DFE1E6",
                order=1,
                is_initial=True,
                is_final=False,
            ),
            WorkflowStatus(
                project=project,
                name="In Progress",
                category="in_progress",
                description="Tasks currently being worked on",
                color="#0052CC",
                order=2,
                is_initial=False,
                is_final=False,
            ),
            WorkflowStatus(
                project=project,
                name="Done",
                category="done",
                description="Completed tasks",
                color="#00875A",
                order=3,
                is_initial=False,
                is_final=True,
            ),
        ]

        WorkflowStatus.objects.bulk_create(default_statuses)

        LoggerService.log_info(
            action="project_created_with_workflows",
            user=self.request.user,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            details={
                "project_id": str(project.id),
                "project_key": project.key,
                "project_name": project.name,
                "workspace_id": str(project.workspace.id),
                "workflow_statuses_created": len(default_statuses),
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
