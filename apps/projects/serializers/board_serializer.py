from rest_framework import serializers

from apps.projects.models import Board, BoardColumn, Project, WorkflowStatus
from apps.projects.serializers.issue_serializer import WorkflowStatusBasicSerializer
from base.serializers import ProjectBasicSerializer, UserBasicSerializer


class BoardColumnSerializer(serializers.ModelSerializer):
    workflow_status = WorkflowStatusBasicSerializer(read_only=True)
    workflow_status_id = serializers.UUIDField(
        write_only=True, source="workflow_status"
    )
    issue_count = serializers.ReadOnlyField()

    class Meta:
        model = BoardColumn
        fields = [
            "id",
            "name",
            "workflow_status",
            "workflow_status_id",
            "order",
            "min_wip",
            "max_wip",
            "issue_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "workflow_status",
            "issue_count",
            "created_at",
            "updated_at",
        ]

    def validate_workflow_status(self, value):
        try:
            WorkflowStatus.objects.get(id=value)
        except WorkflowStatus.DoesNotExist:
            raise serializers.ValidationError("Workflow status does not exist")
        return value

    def validate(self, attrs):
        board = self.context.get("board")
        if board:
            workflow_status_id = attrs.get("workflow_status")
            if workflow_status_id:
                workflow_status = WorkflowStatus.objects.get(id=workflow_status_id)
                if workflow_status.project != board.project:
                    raise serializers.ValidationError(
                        {
                            "workflow_status_id": "Workflow status must belong to the same project as the board"
                        }
                    )

        min_wip = attrs.get("min_wip")
        max_wip = attrs.get("max_wip")
        if min_wip and max_wip and min_wip > max_wip:
            raise serializers.ValidationError(
                {"min_wip": "Minimum WIP cannot be greater than maximum WIP"}
            )

        return attrs


class BoardListSerializer(serializers.ModelSerializer):
    project = ProjectBasicSerializer(read_only=True)
    created_by = UserBasicSerializer(read_only=True)
    column_count = serializers.ReadOnlyField()

    class Meta:
        model = Board
        fields = [
            "id",
            "project",
            "name",
            "description",
            "board_type",
            "column_count",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields


class BoardDetailSerializer(serializers.ModelSerializer):
    project = ProjectBasicSerializer(read_only=True)
    created_by = UserBasicSerializer(read_only=True)
    columns = BoardColumnSerializer(many=True, read_only=True)
    column_count = serializers.ReadOnlyField()
    issue_count = serializers.ReadOnlyField()

    class Meta:
        model = Board
        fields = [
            "id",
            "project",
            "name",
            "description",
            "board_type",
            "saved_filter",
            "columns",
            "column_count",
            "issue_count",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "project",
            "columns",
            "column_count",
            "issue_count",
            "created_by",
            "created_at",
            "updated_at",
        ]


class BoardCreateSerializer(serializers.ModelSerializer):
    project = serializers.UUIDField(write_only=True, required=True)

    class Meta:
        model = Board
        fields = ["project", "name", "description", "board_type", "saved_filter"]

    def validate_project(self, value):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required")

        try:
            project = Project.objects.get(id=value)
        except Project.DoesNotExist:
            raise serializers.ValidationError("Project does not exist")

        from apps.projects.models import ProjectTeamMember
        from apps.workspaces.models import WorkspaceMember

        # Check if user is a project team member
        is_project_member = ProjectTeamMember.objects.filter(
            project=project, user=request.user, is_active=True
        ).exists()

        # Check if user is a workspace member (has access to all projects in workspace)
        is_workspace_member = WorkspaceMember.objects.filter(
            workspace=project.workspace, user=request.user, is_active=True
        ).exists()

        if not (is_project_member or is_workspace_member):
            raise serializers.ValidationError("You are not a member of this project")

        return value

    def create(self, validated_data):
        project_id = validated_data.pop("project")
        project = Project.objects.get(id=project_id)

        validated_data["project"] = project
        validated_data["created_by"] = self.context["request"].user

        return super().create(validated_data)


class BoardUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Board
        fields = ["name", "description", "board_type", "saved_filter"]
