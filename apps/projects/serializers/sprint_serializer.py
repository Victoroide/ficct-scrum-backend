from rest_framework import serializers

from apps.projects.models import Project, Sprint
from base.serializers import ProjectBasicSerializer


class SprintListSerializer(serializers.ModelSerializer):
    project = ProjectBasicSerializer(read_only=True)
    issue_count = serializers.ReadOnlyField()
    progress_percentage = serializers.ReadOnlyField()

    class Meta:
        model = Sprint
        fields = [
            "id",
            "project",
            "name",
            "goal",
            "status",
            "start_date",
            "end_date",
            "issue_count",
            "progress_percentage",
            "created_at",
        ]
        read_only_fields = fields


class SprintDetailSerializer(serializers.ModelSerializer):
    project = ProjectBasicSerializer(read_only=True)
    issue_count = serializers.ReadOnlyField()
    completed_issue_count = serializers.ReadOnlyField()
    progress_percentage = serializers.ReadOnlyField()
    duration_days = serializers.ReadOnlyField()
    remaining_days = serializers.ReadOnlyField()

    class Meta:
        model = Sprint
        fields = [
            "id",
            "project",
            "name",
            "goal",
            "status",
            "start_date",
            "end_date",
            "committed_points",
            "completed_points",
            "issue_count",
            "completed_issue_count",
            "progress_percentage",
            "duration_days",
            "remaining_days",
            "created_at",
            "updated_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "project",
            "issue_count",
            "completed_issue_count",
            "progress_percentage",
            "duration_days",
            "remaining_days",
            "created_at",
            "updated_at",
            "completed_at",
        ]


class SprintCreateSerializer(serializers.ModelSerializer):
    project = serializers.UUIDField(write_only=True, required=True)

    class Meta:
        model = Sprint
        fields = ["project", "name", "goal", "start_date", "end_date"]

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

    def validate(self, attrs):
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "End date must be after start date"}
            )

        project_id = attrs.get("project")
        name = attrs.get("name")

        if Sprint.objects.filter(project_id=project_id, name=name).exists():
            raise serializers.ValidationError(
                {"name": "Sprint with this name already exists in this project"}
            )

        return attrs

    def create(self, validated_data):
        project_id = validated_data.pop("project")
        project = Project.objects.get(id=project_id)

        validated_data["project"] = project
        validated_data["created_by"] = self.context["request"].user

        return super().create(validated_data)


class SprintUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sprint
        fields = ["name", "goal", "start_date", "end_date"]

    def validate(self, attrs):
        instance = self.instance

        if instance.status == "completed":
            if "start_date" in attrs or "end_date" in attrs:
                raise serializers.ValidationError(
                    "Cannot modify dates of a completed sprint"
                )

        start_date = attrs.get("start_date", instance.start_date)
        end_date = attrs.get("end_date", instance.end_date)

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "End date must be after start date"}
            )

        name = attrs.get("name")
        if name and name != instance.name:
            if Sprint.objects.filter(project=instance.project, name=name).exists():
                raise serializers.ValidationError(
                    {"name": "Sprint with this name already exists in this project"}
                )

        return attrs
