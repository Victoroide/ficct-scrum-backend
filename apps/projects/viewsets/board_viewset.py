from django.db import models, transaction

from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.logging.services import LoggerService
from apps.projects.models import Board, BoardColumn, Issue, WorkflowStatus
from apps.projects.permissions import (
    CanAccessProject,
    CanModifyBoard,
    IsProjectTeamMember,
)
from apps.projects.serializers import (
    BoardColumnSerializer,
    BoardCreateSerializer,
    BoardDetailSerializer,
    BoardListSerializer,
    BoardUpdateSerializer,
    IssueCreateSerializer,
)
from apps.projects.utils.websocket_utils import BoardWebSocketNotifier


class BoardFilter(filters.FilterSet):
    project = filters.UUIDFilter(field_name="project__id")
    board_type = filters.ChoiceFilter(choices=Board.BOARD_TYPE_CHOICES)

    class Meta:
        model = Board
        fields = ["project", "board_type"]


@extend_schema_view(
    list=extend_schema(
        tags=["Boards"],
        operation_id="boards_list",
        summary="List Boards",
    ),
    retrieve=extend_schema(
        tags=["Boards"],
        operation_id="boards_retrieve",
        summary="Get Board Details ",
        description="Get board with columns and issues. Support filtering by assignee, priority, sprint.",
    ),
    create=extend_schema(
        tags=["Boards"],
        operation_id="boards_create",
        summary="Create Board ",
    ),
    update=extend_schema(
        tags=["Boards"],
        operation_id="boards_update",
        summary="Update Board",
    ),
    partial_update=extend_schema(
        tags=["Boards"],
        operation_id="boards_partial_update",
        summary="Partial Update Board",
    ),
    destroy=extend_schema(
        tags=["Boards"],
        operation_id="boards_destroy",
        summary="Delete Board",
    ),
)
class BoardViewSet(viewsets.ModelViewSet):
    queryset = Board.objects.all()
    permission_classes = [IsAuthenticated]
    filterset_class = BoardFilter
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        from django.db.models import Q

        return (
            Board.objects.filter(
                Q(
                    project__workspace__members__user=self.request.user,
                    project__workspace__members__is_active=True,
                )
                | Q(
                    project__team_members__user=self.request.user,
                    project__team_members__is_active=True,
                )
            )
            .select_related("project", "created_by")
            .prefetch_related("columns")
            .distinct()
        )

    def get_serializer_class(self):
        if self.action == "create":
            return BoardCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return BoardUpdateSerializer
        elif self.action == "retrieve":
            return BoardDetailSerializer
        return BoardListSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), IsProjectTeamMember()]
        elif self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated(), CanModifyBoard()]
        return [IsAuthenticated(), CanAccessProject()]

    @transaction.atomic
    def perform_create(self, serializer):
        board = serializer.save()

        # Auto-create columns based on project's workflow statuses
        workflow_statuses = WorkflowStatus.objects.filter(
            project=board.project, is_active=True
        ).order_by("order", "name")

        if workflow_statuses.exists():
            # Create column for each workflow status
            for index, workflow_status in enumerate(workflow_statuses):
                BoardColumn.objects.create(
                    board=board,
                    workflow_status=workflow_status,
                    name=workflow_status.name,
                    order=index,
                    min_wip=None,
                    max_wip=None,
                )
        else:
            # If no workflow statuses exist, create default columns
            # Get or create default statuses for the project
            default_statuses = [
                {
                    "name": "To Do",
                    "category": "to_do",
                    "color": "#DFE1E6",
                    "is_initial": True,
                    "order": 0,
                },
                {
                    "name": "In Progress",
                    "category": "in_progress",
                    "color": "#0052CC",
                    "order": 1,
                },
                {
                    "name": "Done",
                    "category": "done",
                    "color": "#00875A",
                    "is_final": True,
                    "order": 2,
                },
            ]

            for index, status_data in enumerate(default_statuses):
                workflow_status, created = WorkflowStatus.objects.get_or_create(
                    project=board.project,
                    name=status_data["name"],
                    defaults={
                        "category": status_data["category"],
                        "color": status_data["color"],
                        "is_initial": status_data.get("is_initial", False),
                        "is_final": status_data.get("is_final", False),
                        "order": status_data["order"],
                    },
                )

                BoardColumn.objects.create(
                    board=board,
                    workflow_status=workflow_status,
                    name=workflow_status.name,
                    order=index,
                    min_wip=None,
                    max_wip=None,
                )

        LoggerService.log_info(
            action="board_created",
            user=self.request.user,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            details={
                "board_id": str(board.id),
                "board_name": board.name,
                "project_id": str(board.project.id),
                "columns_created": board.columns.count(),
            },
        )

    @extend_schema(
        tags=["Boards"],
        operation_id="boards_add_column",
        summary="Add Column to Board ",
        description="Add a new column to the board mapped to a workflow status.",
    )
    @action(detail=True, methods=["post"], url_path="columns")
    def add_column(self, request, pk=None):
        board = self.get_object()

        serializer = BoardColumnSerializer(
            data=request.data, context={"request": request, "board": board}
        )
        serializer.is_valid(raise_exception=True)

        workflow_status_id = serializer.validated_data["workflow_status"]
        workflow_status = WorkflowStatus.objects.get(id=workflow_status_id)

        if workflow_status.project != board.project:
            return Response(
                {
                    "error": "Workflow status must belong to the same project as the board"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        max_order = (
            BoardColumn.objects.filter(board=board).aggregate(
                max_order=models.Max("order")
            )["max_order"]
            or 0
        )

        column = BoardColumn.objects.create(
            board=board,
            workflow_status=workflow_status,
            name=serializer.validated_data.get("name", workflow_status.name),
            order=serializer.validated_data.get("order", max_order + 1),
            min_wip=serializer.validated_data.get("min_wip"),
            max_wip=serializer.validated_data.get("max_wip"),
        )

        LoggerService.log_info(
            action="board_column_added",
            user=request.user,
            ip_address=request.META.get("REMOTE_ADDR"),
            details={
                "board_id": str(board.id),
                "column_id": str(column.id),
                "column_name": column.name,
            },
        )

        response_serializer = BoardColumnSerializer(column)

        BoardWebSocketNotifier.send_column_created(
            board_id=board.id, column_data=response_serializer.data, user=request.user
        )

        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["Boards"],
        operation_id="boards_update_column",
        summary="Update/Delete Board Column ",
        description="Update or delete a board column.",
    )
    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path="columns/(?P<column_id>[^/.]+)",
    )
    def update_column(self, request, pk=None, column_id=None):
        from django.db import models

        board = self.get_object()

        try:
            column = BoardColumn.objects.get(id=column_id, board=board)
        except BoardColumn.DoesNotExist:
            return Response(
                {"error": "Column not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if request.method == "PATCH":
            serializer = BoardColumnSerializer(
                column,
                data=request.data,
                partial=True,
                context={"request": request, "board": board},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

            BoardWebSocketNotifier.send_column_updated(
                board_id=board.id, column_data=serializer.data, user=request.user
            )

            return Response(serializer.data, status=status.HTTP_200_OK)

        elif request.method == "DELETE":
            column_id = column.id
            column_name = column.name

            LoggerService.log_info(
                action="board_column_deleted",
                user=request.user,
                ip_address=request.META.get("REMOTE_ADDR"),
                details={
                    "board_id": str(board.id),
                    "column_id": str(column_id),
                    "column_name": column_name,
                },
            )

            column.delete()

            BoardWebSocketNotifier.send_column_deleted(
                board_id=board.id,
                column_id=column_id,
                column_name=column_name,
                user=request.user,
            )

            return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["Boards"],
        operation_id="boards_create_issue",
        summary="Create Issue from Board ",
        description="Create a new issue directly from the board view.",
    )
    @action(detail=True, methods=["post"], url_path="issues")
    def create_issue(self, request, pk=None):
        board = self.get_object()

        request.data["project"] = str(board.project.id)

        serializer = IssueCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        issue = serializer.save()

        LoggerService.log_info(
            action="issue_created_from_board",
            user=request.user,
            ip_address=request.META.get("REMOTE_ADDR"),
            details={
                "board_id": str(board.id),
                "issue_id": str(issue.id),
                "issue_key": issue.full_key,
            },
        )

        from apps.projects.serializers import IssueDetailSerializer

        response_serializer = IssueDetailSerializer(issue)

        BoardWebSocketNotifier.send_issue_created(
            board_id=board.id, issue_data=response_serializer.data, user=request.user
        )

        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["Boards"],
        operation_id="boards_move_issue",
        summary="Move Issue in Board ",
        description="Move issue between columns. Updates issue status to match column's workflow status.",
    )
    @action(detail=True, methods=["patch"], url_path="issues/(?P<issue_id>[^/.]+)/move")
    def move_issue(self, request, pk=None, issue_id=None):
        from django.db import models

        board = self.get_object()
        column_id = request.data.get("column_id")

        if not column_id:
            return Response(
                {"error": "column_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            issue = Issue.objects.get(id=issue_id, project=board.project)
        except Issue.DoesNotExist:
            return Response(
                {"error": "Issue not found"}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            column = BoardColumn.objects.get(id=column_id, board=board)
        except BoardColumn.DoesNotExist:
            return Response(
                {"error": "Column not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if column.max_wip:
            current_count = Issue.objects.filter(
                project=board.project, status=column.workflow_status, is_active=True
            ).count()

            if (
                current_count >= column.max_wip
                and issue.status != column.workflow_status
            ):
                return Response(
                    {
                        "error": f"Column has reached maximum WIP limit of {column.max_wip}"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        old_status = issue.status
        issue.status = column.workflow_status

        if column.workflow_status.is_final and not issue.resolved_at:
            from datetime import datetime

            issue.resolved_at = datetime.now()

        issue.save()

        LoggerService.log_info(
            action="issue_moved_in_board",
            user=request.user,
            ip_address=request.META.get("REMOTE_ADDR"),
            details={
                "board_id": str(board.id),
                "issue_id": str(issue.id),
                "issue_key": issue.full_key,
                "old_status": old_status.name,
                "new_status": column.workflow_status.name,
                "column_id": str(column.id),
            },
        )

        from apps.projects.serializers import IssueDetailSerializer

        serializer = IssueDetailSerializer(issue)

        BoardWebSocketNotifier.send_issue_moved(
            board_id=board.id,
            issue_data=serializer.data,
            old_status_id=old_status.id,
            new_status_id=column.workflow_status.id,
            user=request.user,
        )

        return Response(serializer.data, status=status.HTTP_200_OK)
