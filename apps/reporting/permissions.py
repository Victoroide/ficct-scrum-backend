from rest_framework import permissions


class CanGenerateReports(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Check for both 'project' and 'project_id' for backward compatibility
        project_id = (
            request.query_params.get("project")
            or request.query_params.get("project_id")
            or request.data.get("project")
            or request.data.get("project_id")
        )
        if not project_id:
            return True

        from apps.projects.models import ProjectTeamMember
        from apps.workspaces.models import WorkspaceMember

        # Check if user is project member
        is_project_member = ProjectTeamMember.objects.filter(
            project_id=project_id, user=request.user, is_active=True
        ).exists()

        if is_project_member:
            return True

        # Check if user is workspace member (has access to all projects in workspace)
        from apps.projects.models import Project

        try:
            project = Project.objects.select_related("workspace").get(id=project_id)
            return WorkspaceMember.objects.filter(
                workspace=project.workspace, user=request.user, is_active=True
            ).exists()
        except Project.DoesNotExist:
            return False

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        from apps.projects.models import ProjectTeamMember

        if hasattr(obj, "project"):
            project = obj.project
        elif hasattr(obj, "user"):
            return obj.user == request.user or request.user.is_staff
        else:
            return False

        return ProjectTeamMember.objects.filter(
            project=project, user=request.user, is_active=True
        ).exists()


class CanExportData(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Check for both 'project' and 'project_id' for backward compatibility
        project_id = (
            request.data.get("project")
            or request.data.get("project_id")
            or request.query_params.get("project")
            or request.query_params.get("project_id")
        )
        if not project_id:
            return False

        from apps.projects.models import ProjectTeamMember
        from apps.workspaces.models import WorkspaceMember

        # Check if user is project admin/owner
        is_project_admin = ProjectTeamMember.objects.filter(
            project_id=project_id,
            user=request.user,
            role__in=["owner", "admin"],
            is_active=True,
        ).exists()

        if is_project_admin:
            return True

        # Check if user is workspace admin
        from apps.projects.models import Project

        try:
            project = Project.objects.select_related("workspace").get(id=project_id)
            return WorkspaceMember.objects.filter(
                workspace=project.workspace,
                user=request.user,
                role="admin",
                is_active=True,
            ).exists()
        except Project.DoesNotExist:
            return False
