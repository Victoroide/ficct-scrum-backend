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
        description="Generate diagram data in JSON format. Returns structured data for frontend rendering with D3.js, Cytoscape.js, or similar libraries. Supports workflow, dependency, roadmap, UML, architecture, and Angular diagrams.",
        request=DiagramRequestSerializer,
        responses={
            200: OpenApiResponse(
                description="Diagram data generated successfully. Returns JSON data structure with nodes, edges, metadata, and layout hints.",
                response=DiagramResponseSerializer,
            ),
            400: OpenApiResponse(
                description="Invalid request parameters or configuration error"
            ),
            403: OpenApiResponse(description="No permission to access this project"),
            404: OpenApiResponse(description="Project not found"),
        },
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
                        "valid_options": VALID_UML_TYPES,
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
            # Generate diagram with error logging
            import logging

            logger = logging.getLogger(__name__)

            # Extract force_refresh parameter
            force_refresh = parameters.get("force_refresh", False)
            if force_refresh:
                logger.info(
                    f"Force refresh requested for {diagram_type} diagram (project {project.id})"
                )
            else:
                logger.info(
                    f"Generating {diagram_type} diagram for project {project.id}"
                )

            if diagram_type == "workflow":
                result = service.generate_workflow_diagram(
                    project, force_refresh=force_refresh
                )
            elif diagram_type == "dependency":
                # Extract filter parameters
                filters = {}
                if "sprint_id" in parameters:
                    filters["sprint_id"] = parameters["sprint_id"]

                # Normalize status_ids: accept UUIDs OR status names/categories
                if "status_ids" in parameters:
                    filters["status_ids"] = self._normalize_status_ids(
                        parameters["status_ids"], project
                    )

                if "priorities" in parameters:
                    filters["priorities"] = parameters["priorities"]
                if "assignee_id" in parameters:
                    filters["assignee_id"] = parameters["assignee_id"]
                if "issue_type_ids" in parameters:
                    filters["issue_type_ids"] = parameters["issue_type_ids"]
                if "search" in parameters:
                    filters["search"] = parameters["search"]

                result = service.generate_dependency_diagram(
                    project, filters, force_refresh=force_refresh
                )
            elif diagram_type == "roadmap":
                result = service.generate_roadmap(project, force_refresh=force_refresh)
            elif diagram_type == "uml":
                result = service.generate_uml_diagram(
                    project, diagram_format, parameters
                )
            elif diagram_type == "architecture":
                result = service.generate_architecture_diagram(
                    project, diagram_format, parameters
                )
            elif diagram_type == "angular_component_hierarchy":
                result = service.generate_angular_diagram(
                    project, "component_hierarchy", diagram_format, parameters
                )
            elif diagram_type == "angular_service_dependencies":
                result = service.generate_angular_diagram(
                    project, "service_dependencies", diagram_format, parameters
                )
            elif diagram_type == "angular_module_graph":
                result = service.generate_angular_diagram(
                    project, "module_graph", diagram_format, parameters
                )
            elif diagram_type == "angular_routing_structure":
                result = service.generate_angular_diagram(
                    project, "routing_structure", diagram_format, parameters
                )
            else:
                return Response(
                    {"error": "Invalid diagram type"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Log result structure before serialization
            logger.debug(f"Service result keys: {result.keys()}")
            logger.debug(f"Data format: {result.get('format')}")
            logger.debug(f"Data type: {type(result.get('data')).__name__}")
            logger.debug(f"Cached: {result.get('cached', False)}")

            response_serializer = DiagramResponseSerializer(data=result)
            response_serializer.is_valid(raise_exception=True)

            # Prepare response with cache headers
            # DRF Response will automatically JSON-encode the dict once
            response = Response(response_serializer.data, status=status.HTTP_200_OK)

            # Add cache status headers
            is_cached = result.get("cached", False)
            if is_cached:
                response["X-Cache-Status"] = "HIT"
                response["X-Diagram-Cached"] = "true"
                cache_age = result.get("cache_age", 0)
                response["X-Cache-Age"] = str(cache_age)
                response["Cache-Control"] = "private, max-age=600"
            else:
                response["X-Cache-Status"] = "MISS"
                response["X-Diagram-Cached"] = "false"
                generation_time = result.get("generation_time_ms", 0)
                response["X-Generation-Time"] = str(generation_time)
                response["Cache-Control"] = "private, max-age=600"

            # Add cache key for debugging
            if "cache_key" in result:
                response["X-Cache-Key"] = result["cache_key"][:16] + "..."

            # Add diagram metadata headers
            response["X-Diagram-Type"] = diagram_type
            response["X-Diagram-Format"] = diagram_format

            return response

        except ValueError as e:
            # ValueError = user-facing errors (missing GitHub integration, no Python files, etc.)
            return Response(
                {"status": "error", "error": str(e), "code": "CONFIGURATION_ERROR"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            import logging
            import traceback

            from django.core.exceptions import FieldError

            logger = logging.getLogger(__name__)

            # Log full traceback for debugging
            logger.error(
                f"Error generating {diagram_type} diagram for project {project_id}:\n"
                f"Error type: {type(e).__name__}\n"
                f"Error message: {str(e)}\n"
                f"Traceback:\n{traceback.format_exc()}",
                exc_info=True,
            )

            # Check if it's an ORM field error (like using non-existent field in query)
            if isinstance(e, FieldError):
                return Response(
                    {
                        "status": "error",
                        "error": "Database query configuration error. Please check system configuration.",
                        "detail": str(e),
                        "code": "QUERY_ERROR",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check for attribute errors (missing fields or methods)
            if isinstance(e, AttributeError):
                return Response(
                    {
                        "status": "error",
                        "error": f"Diagram generation error: {str(e)}",
                        "detail": "A required field or method is missing. This may be a data integrity issue.",
                        "code": "ATTRIBUTE_ERROR",
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Check for type errors (incorrect data types)
            if isinstance(e, TypeError):
                return Response(
                    {
                        "status": "error",
                        "error": f"Data type error: {str(e)}",
                        "detail": "Invalid data type encountered during diagram generation.",
                        "code": "TYPE_ERROR",
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Unexpected server errors
            return Response(
                {
                    "status": "error",
                    "error": "An unexpected error occurred while generating the diagram",
                    "detail": str(e),
                    "error_type": type(e).__name__,
                    "code": "INTERNAL_ERROR",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Export diagram as SVG or PNG",
        tags=["Reporting"],
        description="""
        Export a diagram in SVG or PNG format for download.
        
        **Supported formats:**
        - `svg`: Vector graphic (scalable, best quality)
        - `png`: Raster image (requires cairosvg library)
        
        **Supported diagram types:**
        - `workflow`: Workflow status diagram
        - `dependency`: Issue dependency graph
        - `roadmap`: Project roadmap timeline
        
        **Response:**
        - SVG: Returns SVG XML as text/xml
        - PNG: Returns PNG image as image/png (base64 or binary)
        """,
        request=DiagramRequestSerializer,
        responses={
            200: OpenApiResponse(
                description="Diagram exported successfully",
                response={"type": "string", "format": "binary"},
            ),
            400: OpenApiResponse(description="Invalid parameters"),
            404: OpenApiResponse(description="Project not found"),
            500: OpenApiResponse(description="Export failed"),
        },
    )
    @action(detail=False, methods=["post"])
    def export(self, request):
        """Export diagram as SVG or PNG for download."""
        serializer = DiagramRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        diagram_type = serializer.validated_data["diagram_type"]
        project_id = serializer.validated_data["project"]
        export_format = serializer.validated_data.get("format", "svg")
        parameters = serializer.validated_data.get("parameters", {})

        # Validate export format
        if export_format not in ["svg", "png"]:
            return Response(
                {
                    "error": f"Invalid export format: '{export_format}'",
                    "detail": "Supported formats: svg, png",
                    "code": "INVALID_FORMAT",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate diagram type supports export
        if diagram_type not in ["workflow", "dependency", "roadmap"]:
            return Response(
                {
                    "error": f"Diagram type '{diagram_type}' does not support export",
                    "detail": "Supported types: workflow, dependency, roadmap",
                    "code": "UNSUPPORTED_DIAGRAM_TYPE",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        import logging

        from apps.projects.models import Project

        logger = logging.getLogger(__name__)

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response(
                {"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            # Generate SVG diagram
            from apps.reporting.services.diagram_generators import (
                generate_dependency_graph_svg,
                generate_roadmap_timeline_svg,
                generate_workflow_diagram_svg,
            )

            logger.info(
                f"Exporting {diagram_type} diagram as {export_format} for project {project.key}"
            )

            # Generate SVG based on diagram type
            if diagram_type == "workflow":
                svg_content = generate_workflow_diagram_svg(project)
            elif diagram_type == "dependency":
                # Extract filters for dependency diagram
                filters = {}
                if "sprint_id" in parameters:
                    filters["sprint_id"] = parameters["sprint_id"]
                if "status_ids" in parameters:
                    filters["status_ids"] = self._normalize_status_ids(
                        parameters["status_ids"], project
                    )
                if "priorities" in parameters:
                    filters["priorities"] = parameters["priorities"]
                if "assignee_id" in parameters:
                    filters["assignee_id"] = parameters["assignee_id"]
                if "issue_type_ids" in parameters:
                    filters["issue_type_ids"] = parameters["issue_type_ids"]
                if "search" in parameters:
                    filters["search"] = parameters["search"]

                svg_content = generate_dependency_graph_svg(project, filters)
            elif diagram_type == "roadmap":
                svg_content = generate_roadmap_timeline_svg(project)

            # Return SVG format
            if export_format == "svg":
                from django.http import HttpResponse

                response = HttpResponse(svg_content, content_type="image/svg+xml")
                response[
                    "Content-Disposition"
                ] = f'attachment; filename="{project.key}_{diagram_type}.svg"'
                response["X-Diagram-Type"] = diagram_type
                response["X-Export-Format"] = "svg"

                logger.info(f"SVG export successful: {len(svg_content)} bytes")
                return response

            # Convert SVG to PNG
            elif export_format == "png":
                try:
                    import io

                    import cairosvg

                    # Convert SVG to PNG
                    png_data = cairosvg.svg2png(bytestring=svg_content.encode("utf-8"))

                    from django.http import HttpResponse

                    response = HttpResponse(png_data, content_type="image/png")
                    response[
                        "Content-Disposition"
                    ] = f'attachment; filename="{project.key}_{diagram_type}.png"'
                    response["X-Diagram-Type"] = diagram_type
                    response["X-Export-Format"] = "png"

                    logger.info(f"PNG export successful: {len(png_data)} bytes")
                    return response

                except ImportError:
                    return Response(
                        {
                            "error": "PNG export not available",
                            "detail": "cairosvg library is not installed. Install it with: pip install cairosvg",
                            "code": "PNG_NOT_SUPPORTED",
                            "alternatives": [
                                "Use SVG format instead",
                                "Convert SVG to PNG in frontend using canvas",
                                "Install cairosvg: pip install cairosvg",
                            ],
                        },
                        status=status.HTTP_501_NOT_IMPLEMENTED,
                    )
                except Exception as e:
                    logger.error(f"PNG conversion failed: {str(e)}")
                    return Response(
                        {
                            "error": "PNG conversion failed",
                            "detail": str(e),
                            "code": "PNG_CONVERSION_ERROR",
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

        except Exception as e:
            logger.error(f"Export failed: {str(e)}", exc_info=True)
            return Response(
                {"error": "Export failed", "detail": str(e), "code": "EXPORT_ERROR"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def list(self, request):
        from apps.reporting.models import DiagramCache

        project_id = request.query_params.get("project")
        if not project_id:
            return Response(
                {
                    "error": "project parameter is required",
                    "detail": "Provide project UUID in query params",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            project = self._get_project_or_error(project_id)
        except ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
                if "format" in str(e)
                else status.HTTP_404_NOT_FOUND,
            )
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)

        caches = DiagramCache.objects.filter(project=project).order_by("-generated_at")[
            :20
        ]

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

    def _normalize_status_ids(self, status_ids, project):
        """
        Normalize status_ids to accept both UUIDs and status names/categories.

        Accepts:
        - UUIDs: ["uuid1", "uuid2"]
        - Status names: ["To Do", "In Progress", "Done"]
        - Status categories: ["backlog", "todo", "in_progress", "done"]
        - Mixed: ["uuid1", "In Progress", "done"]

        Returns:
        - List of valid status UUIDs
        """
        import logging
        from uuid import UUID

        from apps.projects.models import WorkflowStatus

        logger = logging.getLogger(__name__)
        normalized_ids = []

        for status_id in status_ids:
            # Try to parse as UUID first
            try:
                UUID(str(status_id))
                # Valid UUID, add directly
                normalized_ids.append(status_id)
                logger.debug(f"Accepted UUID: {status_id}")
            except (ValueError, AttributeError):
                # Not a UUID, try to find by name or category
                logger.debug(f"Not a UUID, searching for status: {status_id}")

                # Try exact name match (case-insensitive)
                status = WorkflowStatus.objects.filter(
                    project=project, name__iexact=status_id
                ).first()

                if status:
                    normalized_ids.append(str(status.id))
                    logger.debug(f"Found by name: {status_id} -> {status.id}")
                    continue

                # Try category match (case-insensitive)
                status = WorkflowStatus.objects.filter(
                    project=project, category__iexact=status_id
                ).first()

                if status:
                    normalized_ids.append(str(status.id))
                    logger.debug(f"Found by category: {status_id} -> {status.id}")
                    continue

                # Try partial name match (contains)
                status = WorkflowStatus.objects.filter(
                    project=project, name__icontains=status_id
                ).first()

                if status:
                    normalized_ids.append(str(status.id))
                    logger.debug(f"Found by partial name: {status_id} -> {status.id}")
                    continue

                # Not found - log warning but don't fail
                logger.warning(
                    f"Status not found: {status_id} (project: {project.key})"
                )

        logger.info(
            f"Normalized {len(status_ids)} status filters to {len(normalized_ids)} UUIDs"
        )
        return normalized_ids
