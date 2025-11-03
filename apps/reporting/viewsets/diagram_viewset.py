from django.core.exceptions import ValidationError
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.reporting.permissions import CanGenerateReports
from apps.reporting.serializers import (
    DiagramRequestSerializer,
    DiagramResponseSerializer,
)
from apps.reporting.services.diagram_service import DiagramService


@extend_schema_view(
    list=extend_schema(
        summary="List cached diagrams",
        tags=["Reporting"],
        description="Returns list of previously generated diagrams for a project with cache status and access count.",
        parameters=[
            OpenApiParameter(
                name="project",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Project UUID to list cached diagrams for",
            ),
        ],
        responses={
            200: OpenApiResponse(description="List of cached diagrams"),
            400: OpenApiResponse(description="Missing or invalid project parameter"),
            403: OpenApiResponse(description="No permission to access this project"),
        },
    ),
)
class DiagramViewSet(viewsets.ViewSet):
    permission_classes = [CanGenerateReports]

    def _validate_uuid(self, uuid_string, param_name="parameter"):
        """Validate UUID format and return cleaned UUID string."""
        if not uuid_string:
            return None
        try:
            import uuid
            uuid.UUID(uuid_string)
            return uuid_string
        except (ValueError, AttributeError):
            raise ValidationError(f"Invalid {param_name} UUID format")

    def _get_project_or_error(self, project_id):
        """Get project by ID or raise appropriate error."""
        from apps.projects.models import Project

        try:
            self._validate_uuid(project_id, "project")
            project = Project.objects.get(id=project_id)
            
            # Check user has access to project
            if not self._user_has_project_access(project):
                raise PermissionDenied("You do not have access to this project")
            
            return project
        except Project.DoesNotExist:
            raise ValidationError("Project not found")

    def _user_has_project_access(self, project):
        """Check if request user has access to project."""
        from apps.projects.models import ProjectTeamMember
        from apps.workspaces.models import WorkspaceMember

        user = self.request.user
        
        # Check project membership
        is_project_member = ProjectTeamMember.objects.filter(
            project=project, user=user, is_active=True
        ).exists()
        
        if is_project_member:
            return True
        
        # Check workspace membership
        is_workspace_member = WorkspaceMember.objects.filter(
            workspace=project.workspace, user=user, is_active=True
        ).exists()
        
        return is_workspace_member

    @extend_schema(
        summary="Generate diagram",
        tags=["Reporting"],
        request=DiagramRequestSerializer,
        responses={200: DiagramResponseSerializer},
    )
    @action(detail=False, methods=["post"])
    def generate(self, request):
        serializer = DiagramRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        diagram_type = serializer.validated_data["diagram_type"]
        project_id = serializer.validated_data["project"]
        diagram_format = serializer.validated_data.get("format", "svg")
        parameters = serializer.validated_data.get("parameters", {})

        # Validate options for specific diagram types
        if diagram_type == "uml":
            uml_type = parameters.get("diagram_type", "class")
            VALID_UML_TYPES = ["class"]  # Currently only 'class' is supported
            
            if uml_type not in VALID_UML_TYPES:
                return Response(
                    {
                        "status": "error",
                        "error": f"Invalid UML diagram type: '{uml_type}'. Valid options: {VALID_UML_TYPES}",
                        "code": "INVALID_OPTIONS",
                        "valid_options": VALID_UML_TYPES
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        from apps.projects.models import Project

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response(
                {"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND
            )

        service = DiagramService()

        try:
            if diagram_type == "workflow":
                result = service.generate_workflow_diagram(project)
            elif diagram_type == "dependency":
                result = service.generate_dependency_diagram(project)
            elif diagram_type == "roadmap":
                result = service.generate_roadmap(project)
            elif diagram_type == "uml":
                result = service.generate_uml_diagram(project, diagram_format, parameters)
            elif diagram_type == "architecture":
                result = service.generate_architecture_diagram(project, diagram_format, parameters)
            else:
                return Response(
                    {"error": "Invalid diagram type"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            response_serializer = DiagramResponseSerializer(data=result)
            response_serializer.is_valid(raise_exception=True)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except ValueError as e:
            # ValueError = user-facing errors (missing GitHub integration, no Python files, etc.)
            return Response(
                {
                    "status": "error",
                    "error": str(e),
                    "code": "CONFIGURATION_ERROR"
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            from django.core.exceptions import FieldError
            
            # Check if it's an ORM field error (like using non-existent field in query)
            if isinstance(e, FieldError):
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Database query error (likely configuration issue): {str(e)}", exc_info=True)
                
                return Response(
                    {
                        "status": "error",
                        "error": "Database query configuration error. Please check system configuration.",
                        "detail": str(e),
                        "code": "QUERY_ERROR"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Unexpected server errors
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Unexpected error generating diagram: {str(e)}", exc_info=True)
            
            return Response(
                {
                    "status": "error",
                    "error": "An unexpected error occurred while generating the diagram",
                    "detail": str(e),
                    "code": "INTERNAL_ERROR"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def list(self, request):
        from apps.reporting.models import DiagramCache

        project_id = request.query_params.get("project")
        if not project_id:
            return Response(
                {"error": "project parameter is required", "detail": "Provide project UUID in query params"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            project = self._get_project_or_error(project_id)
        except ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST if "format" in str(e) else status.HTTP_404_NOT_FOUND,
            )
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)

        caches = DiagramCache.objects.filter(project=project).order_by(
            "-generated_at"
        )[:20]

        data = [
            {
                "id": str(cache.id),
                "diagram_type": cache.diagram_type,
                "format": cache.format,
                "generated_at": cache.generated_at,
                "is_expired": cache.is_expired,
                "access_count": cache.access_count,
            }
            for cache in caches
        ]

        return Response(data, status=status.HTTP_200_OK)
