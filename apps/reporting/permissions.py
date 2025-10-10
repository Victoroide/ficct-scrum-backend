from rest_framework import permissions


class CanGenerateReports(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        project_id = request.query_params.get("project") or request.data.get("project")
        if not project_id:
            return True

        from apps.projects.models import ProjectTeamMember

        return ProjectTeamMember.objects.filter(
            project_id=project_id, user=request.user, is_active=True
        ).exists()

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

        project_id = request.data.get("project") or request.query_params.get("project")
        if not project_id:
            return False

        from apps.projects.models import ProjectTeamMember

        return ProjectTeamMember.objects.filter(
            project_id=project_id,
            user=request.user,
            role__in=["owner", "admin"],
            is_active=True,
        ).exists()
