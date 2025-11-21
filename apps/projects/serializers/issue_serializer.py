from rest_framework import serializers

from apps.projects.models import Issue, IssueType, Project, WorkflowStatus
from apps.projects.services import IssueKeyGenerator, WorkflowValidator
from base.serializers import ProjectBasicSerializer, UserBasicSerializer


class IssueTypeBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueType
        fields = ["id", "name", "category", "icon", "color"]
        read_only_fields = ["id", "name", "category", "icon", "color"]


class WorkflowStatusBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowStatus
        fields = ["id", "name", "category", "color", "is_initial", "is_final"]
        read_only_fields = ["id", "name", "category", "color", "is_initial", "is_final"]


class IssueListSerializer(serializers.ModelSerializer):
    assignee = UserBasicSerializer(read_only=True)
    reporter = UserBasicSerializer(read_only=True)
    status = WorkflowStatusBasicSerializer(read_only=True)
    issue_type = IssueTypeBasicSerializer(read_only=True)

    class Meta:
        model = Issue
        fields = [
            "id",
            "key",
            "title",
            "priority",
            "status",
            "assignee",
            "reporter",
            "issue_type",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class IssueDetailSerializer(serializers.ModelSerializer):
    assignee = UserBasicSerializer(read_only=True)
    reporter = UserBasicSerializer(read_only=True)
    status = WorkflowStatusBasicSerializer(read_only=True)
    issue_type = IssueTypeBasicSerializer(read_only=True)
    project = ProjectBasicSerializer(read_only=True)
    parent_issue = IssueListSerializer(read_only=True)
    comment_count = serializers.ReadOnlyField()
    attachment_count = serializers.ReadOnlyField()
    link_count = serializers.ReadOnlyField()
    full_key = serializers.ReadOnlyField()

    class Meta:
        model = Issue
        fields = [
            "id",
            "project",
            "key",
            "full_key",
            "title",
            "description",
            "priority",
            "status",
            "issue_type",
            "assignee",
            "reporter",
            "parent_issue",
            "sprint",
            "estimated_hours",
            "actual_hours",
            "story_points",
            "order",
            "is_active",
            "comment_count",
            "attachment_count",
            "link_count",
            "created_at",
            "updated_at",
            "resolved_at",
        ]
        read_only_fields = [
            "id",
            "project",
            "key",
            "full_key",
            "reporter",
            "comment_count",
            "attachment_count",
            "link_count",
            "created_at",
            "updated_at",
            "resolved_at",
        ]


class IssueCreateSerializer(serializers.ModelSerializer):
    project = serializers.UUIDField(write_only=True, required=True)
    # Accept either UUID or category string (task, bug, epic, story,
    # improvement, sub_task)
    issue_type = serializers.CharField(write_only=True, required=True)
    # assignee expects user_uuid (not integer id)
    assignee = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    parent_issue = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    sprint = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Issue
        fields = [
            "project",
            "issue_type",
            "title",
            "description",
            "priority",
            "assignee",
            "parent_issue",
            "sprint",
            "estimated_hours",
            "story_points",
        ]

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

    def validate_issue_type(self, value):
        """
        Accept either:
        1. UUID string - looks up IssueType by ID
        2. Category string - looks up IssueType by category for the project
           Valid categories: epic, story, task, bug, improvement, sub_task
        """
        import uuid as uuid_module

        # Try to parse as UUID first
        try:
            uuid_obj = uuid_module.UUID(value)
            # It's a valid UUID, try to fetch by ID
            try:
                _issue_type = IssueType.objects.get(id=uuid_obj)  # noqa: F841
                return str(uuid_obj)  # Return UUID string
            except IssueType.DoesNotExist:
                raise serializers.ValidationError(
                    f"Issue type with ID '{value}' does not exist"
                )
        except (ValueError, AttributeError):
            # Not a UUID, treat as category string
            valid_categories = [
                "epic",
                "story",
                "task",
                "bug",
                "improvement",
                "sub_task",
            ]
            value_lower = value.lower()

            if value_lower not in valid_categories:
                raise serializers.ValidationError(
                    f"Invalid issue type. Must be a valid UUID or one of: {', '.join(valid_categories)}"  # noqa: E501
                )

            # Return the category string, will be resolved in validate() with project
            # context
            return value_lower

    def validate_assignee(self, value):
        """Validate assignee exists by user_uuid."""
        if not value:
            return None

        from apps.authentication.models import User

        try:
            User.objects.get(user_uuid=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Assignee user does not exist")
        return value

    def validate(self, attrs):
        import uuid as uuid_module

        project_id = attrs.get("project")
        issue_type_value = attrs.get("issue_type")

        project = Project.objects.get(id=project_id)

        # Resolve issue_type: could be UUID string or category string
        try:
            # Check if it's a UUID
            uuid_module.UUID(issue_type_value)
            # It's a UUID, get the IssueType
            issue_type = IssueType.objects.get(id=issue_type_value)

            if issue_type.project != project:
                raise serializers.ValidationError(
                    {"issue_type": "Issue type does not belong to this project"}
                )
        except (ValueError, AttributeError):
            # It's a category string, find matching IssueType for this project
            issue_types = IssueType.objects.filter(
                project=project, category=issue_type_value, is_active=True
            )

            if not issue_types.exists():
                raise serializers.ValidationError(
                    {
                        "issue_type": f"No issue type with category '{issue_type_value}' found for this project. "  # noqa: E501
                        f"Please create issue types for this project first."
                    }
                )

            # Prefer default issue type, otherwise take first
            issue_type = (
                issue_types.filter(is_default=True).first() or issue_types.first()
            )

            # Replace category string with actual UUID for create() method
            attrs["issue_type"] = str(issue_type.id)

        assignee_uuid = attrs.get("assignee")
        if assignee_uuid:
            from apps.authentication.models import User
            from apps.projects.models import ProjectTeamMember

            assignee = User.objects.get(user_uuid=assignee_uuid)
            if not ProjectTeamMember.objects.filter(
                project=project, user=assignee, is_active=True
            ).exists():
                raise serializers.ValidationError(
                    {"assignee": "Assignee is not a member of this project"}
                )

        parent_issue_id = attrs.get("parent_issue")
        if parent_issue_id:
            try:
                parent_issue = Issue.objects.get(id=parent_issue_id)
                if parent_issue.project != project:
                    raise serializers.ValidationError(
                        {"parent_issue": "Parent issue does not belong to this project"}
                    )
            except Issue.DoesNotExist:
                raise serializers.ValidationError(
                    {"parent_issue": "Parent issue does not exist"}
                )

        sprint_id = attrs.get("sprint")
        if sprint_id:
            from apps.projects.models import Sprint

            try:
                sprint = Sprint.objects.get(id=sprint_id)
                if sprint.project != project:
                    raise serializers.ValidationError(
                        {"sprint": "Sprint does not belong to this project"}
                    )
            except Sprint.DoesNotExist:
                raise serializers.ValidationError({"sprint": "Sprint does not exist"})

        return attrs

    def create(self, validated_data):
        from apps.authentication.models import User
        from apps.projects.models import Sprint

        project_id = validated_data.pop("project")
        issue_type_id = validated_data.pop("issue_type")
        assignee_uuid = validated_data.pop("assignee", None)
        parent_issue_id = validated_data.pop("parent_issue", None)
        sprint_id = validated_data.pop("sprint", None)

        project = Project.objects.get(id=project_id)
        issue_type = IssueType.objects.get(id=issue_type_id)

        initial_status = WorkflowStatus.objects.filter(
            project=project, is_initial=True, is_active=True
        ).first()

        if not initial_status:
            initial_status = WorkflowStatus.objects.filter(
                project=project, is_active=True
            ).first()

        key = IssueKeyGenerator.generate_key(project)

        validated_data["project"] = project
        validated_data["issue_type"] = issue_type
        validated_data["status"] = initial_status
        validated_data["reporter"] = self.context["request"].user
        validated_data["key"] = key

        if assignee_uuid:
            validated_data["assignee"] = User.objects.get(user_uuid=assignee_uuid)

        if parent_issue_id:
            validated_data["parent_issue"] = Issue.objects.get(id=parent_issue_id)

        if sprint_id:
            validated_data["sprint"] = Sprint.objects.get(id=sprint_id)

        return super().create(validated_data)


class IssueTransitionSerializer(serializers.Serializer):
    """
    Serializer for issue status transitions.

    Accepts both 'status' and 'status_uuid' field names for backward
    compatibility with different frontend implementations.

    Validates:
    - UUID format
    - Status exists in database
    - Status belongs to same project as issue
    - Workflow allows the transition
    - Sets/clears resolved_at timestamp based on final status

    Args:
        status: UUID of the target WorkflowStatus (optional)
        status_uuid: UUID of the target WorkflowStatus (optional)

    Raises:
        ValidationError: If validation fails with clear error message

    Example:
        serializer = IssueTransitionSerializer(
            data={'status_uuid': 'abc-123'},
            context={'issue': issue_instance, 'request': request}
        )
        if serializer.is_valid():
            new_status = serializer.validated_data['new_status']
    """

    status = serializers.UUIDField(
        required=False, allow_null=False, help_text="UUID of the target workflow status"
    )
    status_uuid = serializers.UUIDField(
        required=False,
        allow_null=False,
        help_text="UUID of the target workflow status (alternative field name)",
    )

    def validate(self, attrs):
        """
        Validate the status transition.

        Checks that either 'status' or 'status_uuid' is provided,
        validates the status exists and belongs to the project,
        and verifies the workflow allows the transition.
        """
        # Get status_id from either field name
        status_id = attrs.get("status") or attrs.get("status_uuid")

        if not status_id:
            raise serializers.ValidationError(
                "Either 'status' or 'status_uuid' field is required"
            )

        # Get issue from context
        issue = self.context.get("issue")
        if not issue:
            raise serializers.ValidationError(
                "Issue instance must be provided in serializer context"
            )

        # Validate status exists
        try:
            new_status = WorkflowStatus.objects.select_related("project").get(
                id=status_id
            )
        except WorkflowStatus.DoesNotExist:
            raise serializers.ValidationError(
                {"status": f"Workflow status with ID '{status_id}' does not exist"}
            )

        # Validate status belongs to same project
        if new_status.project != issue.project:
            raise serializers.ValidationError(
                {
                    "status": (
                        f"Status '{new_status.name}' does not belong to "
                        f"project '{issue.project.name}'"
                    )
                }
            )

        # Validate workflow transition is allowed
        can_transition, message = WorkflowValidator.can_transition(issue, new_status)
        if not can_transition:
            raise serializers.ValidationError({"status": message})

        # Store the validated status object for use in viewset
        attrs["new_status"] = new_status
        attrs["old_status"] = issue.status

        return attrs


class IssueUpdateSerializer(serializers.ModelSerializer):
    # assignee expects user_uuid (not integer id)
    assignee = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    status = serializers.UUIDField(write_only=True, required=False)
    sprint = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Issue
        fields = [
            "title",
            "description",
            "priority",
            "assignee",
            "status",
            "sprint",
            "estimated_hours",
            "actual_hours",
            "story_points",
        ]

    def validate_status(self, value):
        if not value:
            return None

        try:
            WorkflowStatus.objects.get(id=value)
        except WorkflowStatus.DoesNotExist:
            raise serializers.ValidationError("Status does not exist")
        return value

    def validate_assignee(self, value):
        """Validate assignee exists by user_uuid."""
        if not value:
            return None

        from apps.authentication.models import User

        try:
            User.objects.get(user_uuid=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Assignee user does not exist")
        return value

    def validate_sprint(self, value):
        if not value:
            return None

        from apps.projects.models import Sprint

        try:
            Sprint.objects.get(id=value)
        except Sprint.DoesNotExist:
            raise serializers.ValidationError("Sprint does not exist")
        return value

    def validate(self, attrs):
        instance = self.instance
        status_id = attrs.get("status")

        if status_id:
            new_status = WorkflowStatus.objects.get(id=status_id)
            can_transition, message = WorkflowValidator.can_transition(
                instance, new_status
            )
            if not can_transition:
                raise serializers.ValidationError({"status": message})

        assignee_uuid = attrs.get("assignee")
        if assignee_uuid:
            from apps.authentication.models import User
            from apps.projects.models import ProjectTeamMember

            assignee = User.objects.get(user_uuid=assignee_uuid)
            if not ProjectTeamMember.objects.filter(
                project=instance.project, user=assignee, is_active=True
            ).exists():
                raise serializers.ValidationError(
                    {"assignee": "Assignee is not a member of this project"}
                )

        sprint_id = attrs.get("sprint")
        if sprint_id:
            from apps.projects.models import Sprint

            sprint = Sprint.objects.get(id=sprint_id)
            if sprint.project != instance.project:
                raise serializers.ValidationError(
                    {"sprint": "Sprint does not belong to this project"}
                )

        return attrs

    def update(self, instance, validated_data):
        from datetime import datetime

        from apps.authentication.models import User
        from apps.projects.models import Sprint

        assignee_uuid = validated_data.pop("assignee", None)
        status_id = validated_data.pop("status", None)
        sprint_id = validated_data.pop("sprint", None)

        if assignee_uuid is not None:
            if assignee_uuid:
                instance.assignee = User.objects.get(user_uuid=assignee_uuid)
            else:
                instance.assignee = None

        if status_id:
            new_status = WorkflowStatus.objects.get(id=status_id)
            instance.status = new_status
            if new_status.is_final and not instance.resolved_at:
                instance.resolved_at = datetime.now()

        if sprint_id is not None:
            if sprint_id:
                instance.sprint = Sprint.objects.get(id=sprint_id)
            else:
                instance.sprint = None

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance
