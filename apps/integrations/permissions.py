from rest_framework import permissions


class CanManageIntegrations(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        project_id = request.data.get("project") or view.kwargs.get("project_id")
        if not project_id:
            return False

        from apps.projects.models import ProjectTeamMember

        return ProjectTeamMember.objects.filter(
            project_id=project_id, user=request.user, role__in=["owner", "admin"]
        ).exists()

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in permissions.SAFE_METHODS:
            return self._is_team_member(request.user, obj.project)

        return self._is_admin(request.user, obj.project)

    def _is_team_member(self, user, project):
        from apps.projects.models import ProjectTeamMember

        return ProjectTeamMember.objects.filter(
            project=project, user=user, is_active=True
        ).exists()

    def _is_admin(self, user, project):
        from apps.projects.models import ProjectTeamMember

        return ProjectTeamMember.objects.filter(
            project=project, user=user, role__in=["owner", "admin"], is_active=True
        ).exists()


class CanViewIntegrations(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        from apps.projects.models import ProjectTeamMember

        return ProjectTeamMember.objects.filter(
            project=obj.project, user=request.user, is_active=True
        ).exists()
