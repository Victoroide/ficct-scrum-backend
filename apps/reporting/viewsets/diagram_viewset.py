from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.reporting.permissions import CanGenerateReports
from apps.reporting.serializers import (
    DiagramRequestSerializer,
    DiagramResponseSerializer,
)
from apps.reporting.services.diagram_service import DiagramService


@extend_schema_view(
    list=extend_schema(summary="List cached diagrams", tags=["Diagrams"]),
)
class DiagramViewSet(viewsets.ViewSet):
    permission_classes = [CanGenerateReports]

    @extend_schema(
        summary="Generate diagram",
        tags=["Diagrams"],
        request=DiagramRequestSerializer,
        responses={200: DiagramResponseSerializer},
    )
    @action(detail=False, methods=["post"])
    def generate(self, request):
        serializer = DiagramRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        diagram_type = serializer.validated_data["diagram_type"]
        project_id = request.query_params.get("project")

        if not project_id:
            return Response(
                {"error": "project parameter is required"},
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
                integration = project.github_integration
                result = service.generate_uml_from_code(integration)
            elif diagram_type == "architecture":
                integration = project.github_integration
                result = service.generate_architecture_diagram(integration)
            else:
                return Response(
                    {"error": "Invalid diagram type"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            response_serializer = DiagramResponseSerializer(data=result)
            response_serializer.is_valid(raise_exception=True)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="List cached diagrams",
        tags=["Diagrams"],
        responses={200: {"type": "array"}},
    )
    def list(self, request):
        from apps.reporting.models import DiagramCache

        project_id = request.query_params.get("project")
        if not project_id:
            return Response(
                {"error": "project parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        caches = DiagramCache.objects.filter(project_id=project_id).order_by(
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
