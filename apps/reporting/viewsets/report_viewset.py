from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
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

from apps.reporting.models import ReportSnapshot
from apps.reporting.permissions import CanExportData, CanGenerateReports
from apps.reporting.serializers import (
    ExportRequestSerializer,
    ReportSnapshotSerializer,
)
from apps.reporting.services.analytics_service import AnalyticsService


@extend_schema_view(
    list=extend_schema(
        summary="List report snapshots",
        tags=["Reporting"],
        parameters=[
            OpenApiParameter(
                name="project",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Project UUID to list snapshots for",
            ),
        ],
        responses={
            200: ReportSnapshotSerializer(many=True),
            400: OpenApiResponse(description="Missing or invalid project parameter"),
        },
    ),
)
class ReportViewSet(viewsets.ViewSet):
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

    def _get_sprint_or_error(self, sprint_id):
        """Get sprint by ID or raise appropriate error."""
        from apps.projects.models import Sprint

        try:
            self._validate_uuid(sprint_id, "sprint")
            sprint = Sprint.objects.get(id=sprint_id)
            
            # Check user has access to sprint's project
            if not self._user_has_project_access(sprint.project):
                raise PermissionDenied("You do not have access to this sprint")
            
            return sprint
        except Sprint.DoesNotExist:
            raise ValidationError("Sprint not found")

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
        summary="Generate velocity chart",
        tags=["Reporting"],
        description="Generates velocity chart showing team velocity over the last N sprints. Helps track team consistency and predict future capacity.",
        parameters=[
            OpenApiParameter(
                name="project",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Project UUID to generate velocity chart for",
            ),
            OpenApiParameter(
                name="num_sprints",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Number of sprints to include (default: 5)",
            ),
        ],
        responses={
            200: OpenApiResponse(description="Velocity chart generated successfully"),
            400: OpenApiResponse(description="Missing or invalid parameters"),
            403: OpenApiResponse(description="No permission to access this project"),
            404: OpenApiResponse(description="Project not found"),
        },
    )
    @action(detail=False, methods=["get"])
    def velocity(self, request):
        project_id = request.query_params.get("project")
        
        if not project_id:
            return Response(
                {"error": "project parameter is required", "detail": "Provide project UUID in query params"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            num_sprints = int(request.query_params.get("num_sprints", 5))
            if num_sprints < 1 or num_sprints > 20:
                return Response(
                    {"error": "num_sprints must be between 1 and 20"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except (ValueError, TypeError):
            return Response(
                {"error": "num_sprints must be a valid integer"},
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

        service = AnalyticsService()
        chart_data = service.generate_velocity_chart(project, num_sprints)

        return Response(chart_data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Generate sprint report",
        tags=["Reporting"],
        description="Generates comprehensive sprint report including burndown chart, velocity, completion metrics, and team performance analysis.",
        parameters=[
            OpenApiParameter(
                name="sprint",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Sprint UUID to generate report for",
            ),
        ],
        responses={
            200: OpenApiResponse(description="Sprint report generated successfully"),
            400: OpenApiResponse(description="Missing or invalid sprint parameter"),
            403: OpenApiResponse(description="No permission to access this sprint"),
            404: OpenApiResponse(description="Sprint not found"),
        },
    )
    @action(detail=False, methods=["get"], url_path="sprint-report")
    def sprint_report(self, request):
        sprint_id = request.query_params.get("sprint")

        if not sprint_id:
            return Response(
                {"error": "sprint parameter is required", "detail": "Provide sprint UUID in query params"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            sprint = self._get_sprint_or_error(sprint_id)
        except ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST if "format" in str(e) else status.HTTP_404_NOT_FOUND,
            )
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)

        service = AnalyticsService()
        report = service.generate_sprint_report(sprint)

        ReportSnapshot.objects.create(
            project=sprint.project,
            sprint=sprint,
            report_type="sprint_summary",
            report_data=report,
            generated_by=request.user,
        )

        return Response(report, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Generate team metrics",
        tags=["Reporting"],
        description="Generates team performance metrics including task completion rates, average cycle time, and individual contributor statistics.",
        parameters=[
            OpenApiParameter(
                name="project",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Project UUID to generate team metrics for",
            ),
            OpenApiParameter(
                name="period",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Period in days to analyze (default: 30, max: 365)",
            ),
        ],
        responses={
            200: OpenApiResponse(description="Team metrics generated successfully"),
            400: OpenApiResponse(description="Missing or invalid parameters"),
            403: OpenApiResponse(description="No permission to access this project"),
            404: OpenApiResponse(description="Project not found"),
        },
    )
    @action(detail=False, methods=["get"], url_path="team-metrics")
    def team_metrics(self, request):
        project_id = request.query_params.get("project")

        if not project_id:
            return Response(
                {"error": "project parameter is required", "detail": "Provide project UUID in query params"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            period = int(request.query_params.get("period", 30))
            if period < 1 or period > 365:
                return Response(
                    {"error": "period must be between 1 and 365 days"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except (ValueError, TypeError):
            return Response(
                {"error": "period must be a valid integer"},
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

        service = AnalyticsService()
        metrics = service.generate_team_metrics(project, period)

        return Response(metrics, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Generate cumulative flow diagram",
        tags=["Reporting"],
        description="Generates cumulative flow diagram (CFD) showing work distribution across different statuses over time. Helps identify bottlenecks.",
        parameters=[
            OpenApiParameter(
                name="project",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Project UUID to generate CFD for",
            ),
            OpenApiParameter(
                name="days",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Number of days to include (default: 30, max: 180)",
            ),
        ],
        responses={
            200: OpenApiResponse(description="CFD generated successfully"),
            400: OpenApiResponse(description="Missing or invalid parameters"),
            403: OpenApiResponse(description="No permission to access this project"),
            404: OpenApiResponse(description="Project not found"),
        },
    )
    @action(detail=False, methods=["get"], url_path="cumulative-flow")
    def cumulative_flow(self, request):
        project_id = request.query_params.get("project")

        if not project_id:
            return Response(
                {"error": "project parameter is required", "detail": "Provide project UUID in query params"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            days = int(request.query_params.get("days", 30))
            if days < 1 or days > 180:
                return Response(
                    {"error": "days must be between 1 and 180"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except (ValueError, TypeError):
            return Response(
                {"error": "days must be a valid integer"},
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

        service = AnalyticsService()
        cfd_data = service.generate_cumulative_flow_diagram(project, days)

        return Response(cfd_data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Export data to CSV",
        tags=["Reporting"],
        request=ExportRequestSerializer,
        responses={200: {"type": "object"}},
    )
    @action(detail=False, methods=["post"], permission_classes=[CanExportData])
    def export(self, request):
        serializer = ExportRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data_type = serializer.validated_data["data_type"]
        project_id = serializer.validated_data["project"]
        filters = serializer.validated_data.get("filters", {})

        from apps.projects.models import Project

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response(
                {"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND
            )

        service = AnalyticsService()
        csv_content = service.export_to_csv(project, data_type, filters)

        snapshot = ReportSnapshot.objects.create(
            project=project,
            report_type="custom",
            report_data={"export_type": data_type, "filters": filters},
            generated_by=request.user,
        )

        filename = f"{data_type}_export_{snapshot.id}.csv"
        snapshot.csv_file.save(filename, ContentFile(csv_content.encode("utf-8")))

        return Response(
            {
                "message": "Export completed successfully",
                "download_url": snapshot.download_url,
                "snapshot_id": str(snapshot.id),
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Get project dashboard",
        tags=["Reporting"],
        description="Generates comprehensive project dashboard with key metrics, active sprints, recent activity, and health indicators.",
        parameters=[
            OpenApiParameter(
                name="project",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Project UUID to generate dashboard for",
            ),
        ],
        responses={
            200: OpenApiResponse(description="Dashboard generated successfully"),
            400: OpenApiResponse(description="Missing or invalid project parameter"),
            403: OpenApiResponse(description="No permission to access this project"),
            404: OpenApiResponse(description="Project not found"),
        },
    )
    @action(detail=False, methods=["get"])
    def dashboard(self, request):
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

        service = AnalyticsService()
        dashboard_data = service.generate_project_dashboard(project)

        return Response(dashboard_data, status=status.HTTP_200_OK)

    def list(self, request):
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

        snapshots = ReportSnapshot.objects.filter(project=project).order_by(
            "-generated_at"
        )[:50]

        serializer = ReportSnapshotSerializer(snapshots, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
