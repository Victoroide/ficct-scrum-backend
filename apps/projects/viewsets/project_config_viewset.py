import logging

from django.db import IntegrityError

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.projects.models import ProjectConfiguration
from apps.projects.permissions import CanModifyProjectConfiguration
from apps.projects.serializers import ProjectConfigSerializer

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        tags=["Projects"],
        operation_id="project_configs_list",
        summary="List Project Configurations",
    ),
    retrieve=extend_schema(
        tags=["Projects"],
        operation_id="project_configs_retrieve",
        summary="Get Project Configuration",
    ),
    create=extend_schema(
        tags=["Projects"],
        operation_id="project_configs_create",
        summary="Create Project Configuration",
    ),
    update=extend_schema(
        tags=["Projects"],
        operation_id="project_configs_update",
        summary="Update Project Configuration",
    ),
    partial_update=extend_schema(
        tags=["Projects"],
        operation_id="project_configs_partial_update",
        summary="Partial Update Project Configuration",
    ),
    destroy=extend_schema(
        tags=["Projects"],
        operation_id="project_configs_destroy",
        summary="Delete Project Configuration",
    ),
)
class ProjectConfigViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing project configurations.

    Provides CRUD operations and search by project UUID.
    Prevents duplicate configurations with proper error handling.
    """

    queryset = ProjectConfiguration.objects.all()
    serializer_class = ProjectConfigSerializer
    permission_classes = [IsAuthenticated, CanModifyProjectConfiguration]

    def get_queryset(self):
        """Filter configurations by user's accessible projects."""
        return ProjectConfiguration.objects.filter(
            project__workspace__members__user=self.request.user,
            project__workspace__members__is_active=True,
        ).distinct()

    def create(self, request, *args, **kwargs):
        """
        Create a new project configuration.

        Handles IntegrityError as a fallback to prevent 500 errors.
        The serializer should catch duplicates during validation,
        but this provides an additional safety layer.
        """
        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError as e:
            logger.warning(
                f"Attempted to create duplicate configuration for project. "
                f"User: {request.user.email}, Project: {request.data.get('project')}, "
                f"Error: {str(e)}"
            )
            return Response(
                {"error": "A configuration already exists for this project."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        tags=["Projects"],
        operation_id="project_configs_by_project",
        summary="Get Configuration by Project UUID",
        description="Retrieve the configuration for a specific project using its UUID.",
        parameters=[
            OpenApiParameter(
                name="project",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description="UUID of the project",
            )
        ],
        responses={
            200: ProjectConfigSerializer,
            404: {"description": "Configuration not found for this project"},
            400: {"description": "Project UUID is required"},
        },
    )
    @action(detail=False, methods=["get"], url_path="by-project")
    def by_project(self, request):
        """
        Get configuration by project UUID.

        Query params:
            project: UUID of the project

        Returns:
            200: Configuration found
            404: Configuration not found
            400: Project UUID not provided
        """
        project_id = request.query_params.get("project")

        if not project_id:
            return Response(
                {"error": "Project UUID is required as query parameter."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            config = self.get_queryset().get(project_id=project_id)
            serializer = self.get_serializer(config)
            return Response(serializer.data)
        except ProjectConfiguration.DoesNotExist:
            return Response(
                {"error": "Configuration not found for this project."},
                status=status.HTTP_404_NOT_FOUND,
            )
