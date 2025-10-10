from django.core.files.base import ContentFile
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.reporting.models import ReportSnapshot
from apps.reporting.permissions import CanExportData, CanGenerateReports
from apps.reporting.serializers import (
    ExportRequestSerializer,
    ReportSnapshotSerializer,
)
from apps.reporting.services.analytics_service import AnalyticsService


@extend_schema_view(
    list=extend_schema(summary="List report snapshots", tags=["Reports"]),
)
class ReportViewSet(viewsets.ViewSet):
    permission_classes = [CanGenerateReports]

    @extend_schema(
        summary="Generate velocity chart",
        tags=["Reports"],
        request=None,
        responses={200: {"type": "object"}},
    )
    @action(detail=False, methods=["get"])
    def velocity(self, request):
        project_id = request.query_params.get("project")
        num_sprints = int(request.query_params.get("num_sprints", 5))

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

        service = AnalyticsService()
        chart_data = service.generate_velocity_chart(project, num_sprints)

        return Response(chart_data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Generate sprint report",
        tags=["Reports"],
        request=None,
        responses={200: {"type": "object"}},
    )
    @action(detail=False, methods=["get"], url_path="sprint-report")
    def sprint_report(self, request):
        sprint_id = request.query_params.get("sprint")

        if not sprint_id:
            return Response(
                {"error": "sprint parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.projects.models import Sprint

        try:
            sprint = Sprint.objects.get(id=sprint_id)
        except Sprint.DoesNotExist:
            return Response(
                {"error": "Sprint not found"}, status=status.HTTP_404_NOT_FOUND
            )

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
        tags=["Reports"],
        request=None,
        responses={200: {"type": "object"}},
    )
    @action(detail=False, methods=["get"], url_path="team-metrics")
    def team_metrics(self, request):
        project_id = request.query_params.get("project")
        period = int(request.query_params.get("period", 30))

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

        service = AnalyticsService()
        metrics = service.generate_team_metrics(project, period)

        return Response(metrics, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Generate cumulative flow diagram",
        tags=["Reports"],
        request=None,
        responses={200: {"type": "object"}},
    )
    @action(detail=False, methods=["get"], url_path="cumulative-flow")
    def cumulative_flow(self, request):
        project_id = request.query_params.get("project")
        days = int(request.query_params.get("days", 30))

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

        service = AnalyticsService()
        cfd_data = service.generate_cumulative_flow_diagram(project, days)

        return Response(cfd_data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Export data to CSV",
        tags=["Reports"],
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
        tags=["Reports"],
        request=None,
        responses={200: {"type": "object"}},
    )
    @action(detail=False, methods=["get"])
    def dashboard(self, request):
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

        service = AnalyticsService()
        dashboard_data = service.generate_project_dashboard(project)

        return Response(dashboard_data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="List report snapshots",
        tags=["Reports"],
        responses={200: ReportSnapshotSerializer(many=True)},
    )
    def list(self, request):
        project_id = request.query_params.get("project")

        if not project_id:
            return Response(
                {"error": "project parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        snapshots = ReportSnapshot.objects.filter(project_id=project_id).order_by(
            "-generated_at"
        )[:50]

        serializer = ReportSnapshotSerializer(snapshots, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
