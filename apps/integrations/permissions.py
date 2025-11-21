from rest_framework import permissions


class CanManageIntegrations(permissions.BasePermission):
    """
    Permission to manage GitHub integrations.
    Project lead/admin, workspace admin, or organization owner/admin can manage.

    ARCHITECTURE:
    - Project members with owner/admin role can manage integrations
    - Workspace admins can manage integrations for ALL projects in their workspace
    - Organization owners/admins can manage integrations for ALL projects in their org
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        # Only POST to CREATE endpoint requires project_id in request body
        # POST to detail endpoints (custom actions like sync_commits) use has_object_permission()  # noqa: E501
        # DELETE, PATCH, PUT also use has_object_permission() which gets project
        # from object
        if request.method == "POST":
            # Check if this is a detail action (has pk in URL) vs list action (create)
            # Detail actions: /integrations/github/{pk}/sync_commits/ → Delegate to has_object_permission  # noqa: E501
            # List actions: /integrations/github/ → Require project in body
            if view.kwargs.get("pk"):
                # This is a POST to a detail endpoint (custom action)
                # Delegate to has_object_permission() - don't require project in body
                return True

            # This is a POST to list endpoint (CREATE) - require project in body
            project_id = request.data.get("project") or view.kwargs.get("project_id")
            if not project_id:
                self.message = "Missing required field 'project'. Please provide project ID in request body."  # noqa: E501
                return False

            from apps.organizations.models import OrganizationMembership
            from apps.projects.models import Project, ProjectTeamMember
            from apps.workspaces.models import WorkspaceMember

            try:
                project = Project.objects.select_related(
                    "workspace", "workspace__organization"
                ).get(id=project_id)
            except Project.DoesNotExist:
                self.message = f"Project with ID '{project_id}' does not exist."
                return False

            # Check project membership
            is_project_admin = ProjectTeamMember.objects.filter(
                project=project,
                user=request.user,
                role__in=["owner", "admin"],
                is_active=True,
            ).exists()

            if is_project_admin:
                return True

            # Check workspace membership
            is_workspace_admin = WorkspaceMember.objects.filter(
                workspace=project.workspace,
                user=request.user,
                role="admin",
                is_active=True,
            ).exists()

            if is_workspace_admin:
                return True

            # Check organization membership
            is_org_admin = OrganizationMembership.objects.filter(
                organization=project.workspace.organization,
                user=request.user,
                role__in=["owner", "admin"],
                is_active=True,
            ).exists()

            if not is_org_admin:
                self.message = "You do not have permission to manage integrations for this project. Required role: Project owner/admin, Workspace admin, or Organization owner/admin."  # noqa: E501

            return is_org_admin
        else:
            # For object-level operations (DELETE, PATCH, PUT),
            # has_object_permission() will be called with the actual object
            return True

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in permissions.SAFE_METHODS:
            return self._is_team_member(request.user, obj.project)

        return self._is_admin(request.user, obj.project)

    def _is_team_member(self, user, project):
        from apps.projects.models import ProjectTeamMember
        from apps.workspaces.models import WorkspaceMember

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

    def _is_admin(self, user, project):
        from apps.organizations.models import OrganizationMembership
        from apps.projects.models import ProjectTeamMember
        from apps.workspaces.models import WorkspaceMember

        # Check project admin
        is_project_admin = ProjectTeamMember.objects.filter(
            project=project, user=user, role__in=["owner", "admin"], is_active=True
        ).exists()

        if is_project_admin:
            return True

        # Check workspace admin
        is_workspace_admin = WorkspaceMember.objects.filter(
            workspace=project.workspace, user=user, role="admin", is_active=True
        ).exists()

        if is_workspace_admin:
            return True

        # Check organization owner/admin
        is_org_admin = OrganizationMembership.objects.filter(
            organization=project.workspace.organization,
            user=user,
            role__in=["owner", "admin"],
            is_active=True,
        ).exists()

        return is_org_admin


class CanViewIntegrations(permissions.BasePermission):
    """
    Permission to view GitHub integrations.
    Project members, workspace members, or organization members can view.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        from apps.projects.models import ProjectTeamMember
        from apps.workspaces.models import WorkspaceMember

        # Check project membership
        is_project_member = ProjectTeamMember.objects.filter(
            project=obj.project, user=request.user, is_active=True
        ).exists()

        if is_project_member:
            return True

        # Check workspace membership
        is_workspace_member = WorkspaceMember.objects.filter(
            workspace=obj.project.workspace, user=request.user, is_active=True
        ).exists()

        return is_workspace_member
