from django.db import transaction
from django.shortcuts import get_object_or_404

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.authentication.serializers import UserSerializer
from apps.organizations.serializers import WorkspaceSerializer
from apps.projects.models import (
    IssueType,
    Project,
    ProjectTeamMember,
    WorkflowStatus,
    WorkflowTransition,
)


class ProjectSerializer(serializers.ModelSerializer):
    workspace = WorkspaceSerializer(read_only=True)
    lead = UserSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    team_member_count = serializers.ReadOnlyField()
    issue_count = serializers.ReadOnlyField()

    class Meta:
        model = Project
        fields = [
            "id",
            "workspace",
            "name",
            "key",
            "description",
            "methodology",
            "status",
            "priority",
            "lead",
            "start_date",
            "end_date",
            "estimated_hours",
            "budget",
            "project_settings",
            "is_active",
            "created_by",
            "team_member_count",
            "issue_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "workspace", "created_by", "created_at", "updated_at"]

    def validate_key(self, value):
        workspace = self.context.get("workspace")
        if self.instance:
            if (
                Project.objects.exclude(id=self.instance.id)
                .filter(workspace=workspace, key=value)
                .exists()
            ):
                raise serializers.ValidationError(
                    "Project with this key already exists in workspace"
                )
        else:
            if Project.objects.filter(workspace=workspace, key=value).exists():
                raise serializers.ValidationError(
                    "Project with this key already exists in workspace"
                )
        return value

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        workspace = self.context.get("workspace")

        validated_data["workspace"] = workspace
        validated_data["created_by"] = request.user

        project = Project.objects.create(**validated_data)

        # Create default issue types
        default_issue_types = [
            {"name": "Epic", "category": "epic", "color": "#8777D9", "icon": "epic"},
            {"name": "Story", "category": "story", "color": "#63BA3C", "icon": "story"},
            {"name": "Task", "category": "task", "color": "#4BADE8", "icon": "task"},
            {"name": "Bug", "category": "bug", "color": "#E97F33", "icon": "bug"},
            {
                "name": "Improvement",
                "category": "improvement",
                "color": "#2684FF",
                "icon": "improvement",
            },
        ]

        for issue_type_data in default_issue_types:
            IssueType.objects.create(project=project, **issue_type_data)

        # Create default workflow statuses
        default_statuses = [
            {
                "name": "To Do",
                "category": "to_do",
                "color": "#DFE1E6",
                "order": 1,
                "is_initial": True,
            },
            {
                "name": "In Progress",
                "category": "in_progress",
                "color": "#0052CC",
                "order": 2,
            },
            {
                "name": "Done",
                "category": "done",
                "color": "#00875A",
                "order": 3,
                "is_final": True,
            },
        ]

        statuses = []
        for status_data in default_statuses:
            status = WorkflowStatus.objects.create(project=project, **status_data)
            statuses.append(status)

        # Create default transitions
        WorkflowTransition.objects.create(
            project=project,
            name="Start Progress",
            from_status=statuses[0],
            to_status=statuses[1],
        )
        WorkflowTransition.objects.create(
            project=project,
            name="Complete",
            from_status=statuses[1],
            to_status=statuses[2],
        )

        # Add creator as project manager
        ProjectTeamMember.objects.create(
            project=project, user=request.user, role="project_manager"
        )

        return project


class ProjectTeamMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    project = ProjectSerializer(read_only=True)

    class Meta:
        model = ProjectTeamMember
        fields = [
            "id",
            "project",
            "user",
            "role",
            "permissions",
            "hourly_rate",
            "is_active",
            "joined_at",
            "updated_at",
        ]
        read_only_fields = ["id", "project", "user", "joined_at", "updated_at"]


class IssueTypeSerializer(serializers.ModelSerializer):
    project = ProjectSerializer(read_only=True)

    class Meta:
        model = IssueType
        fields = [
            "id",
            "project",
            "name",
            "category",
            "description",
            "icon",
            "color",
            "is_default",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "project", "created_at", "updated_at"]

    def validate_name(self, value):
        project = self.context.get("project")
        if self.instance:
            if (
                IssueType.objects.exclude(id=self.instance.id)
                .filter(project=project, name=value)
                .exists()
            ):
                raise serializers.ValidationError(
                    "Issue type with this name already exists in project"
                )
        else:
            if IssueType.objects.filter(project=project, name=value).exists():
                raise serializers.ValidationError(
                    "Issue type with this name already exists in project"
                )
        return value

    @transaction.atomic
    def create(self, validated_data):
        project = self.context.get("project")
        validated_data["project"] = project
        return IssueType.objects.create(**validated_data)


class WorkflowStatusSerializer(serializers.ModelSerializer):
    project = ProjectSerializer(read_only=True)

    class Meta:
        model = WorkflowStatus
        fields = [
            "id",
            "project",
            "name",
            "category",
            "description",
            "color",
            "order",
            "is_initial",
            "is_final",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "project", "created_at", "updated_at"]

    def validate_name(self, value):
        project = self.context.get("project")
        if self.instance:
            if (
                WorkflowStatus.objects.exclude(id=self.instance.id)
                .filter(project=project, name=value)
                .exists()
            ):
                raise serializers.ValidationError(
                    "Status with this name already exists in project"
                )
        else:
            if WorkflowStatus.objects.filter(project=project, name=value).exists():
                raise serializers.ValidationError(
                    "Status with this name already exists in project"
                )
        return value

    @transaction.atomic
    def create(self, validated_data):
        project = self.context.get("project")
        validated_data["project"] = project
        return WorkflowStatus.objects.create(**validated_data)


class WorkflowTransitionSerializer(serializers.ModelSerializer):
    project = ProjectSerializer(read_only=True)
    from_status = WorkflowStatusSerializer(read_only=True)
    to_status = WorkflowStatusSerializer(read_only=True)

    class Meta:
        model = WorkflowTransition
        fields = [
            "id",
            "project",
            "name",
            "from_status",
            "to_status",
            "conditions",
            "validators",
            "post_functions",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "project", "created_at", "updated_at"]

    @transaction.atomic
    def create(self, validated_data):
        project = self.context.get("project")
        validated_data["project"] = project
        return WorkflowTransition.objects.create(**validated_data)


class AddTeamMemberSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    role = serializers.ChoiceField(
        choices=ProjectTeamMember.ROLE_CHOICES, default="developer"
    )
    hourly_rate = serializers.DecimalField(
        max_digits=8, decimal_places=2, required=False
    )

    def validate_user_id(self, value):
        from apps.authentication.models import User

        try:
            user = User.objects.get(id=value, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")
        return value

    @transaction.atomic
    def save(self):
        project = self.context.get("project")
        user_id = self.validated_data["user_id"]
        role = self.validated_data["role"]
        hourly_rate = self.validated_data.get("hourly_rate")

        from apps.authentication.models import User

        user = User.objects.get(id=user_id)

        # Check if user is already a team member
        existing_member = ProjectTeamMember.objects.filter(
            project=project, user=user
        ).first()

        if existing_member:
            if existing_member.is_active:
                raise serializers.ValidationError("User is already a team member")
            else:
                # Reactivate existing membership
                existing_member.is_active = True
                existing_member.role = role
                if hourly_rate:
                    existing_member.hourly_rate = hourly_rate
                existing_member.save()
                return existing_member

        # Create new team membership
        return ProjectTeamMember.objects.create(
            project=project, user=user, role=role, hourly_rate=hourly_rate
        )
