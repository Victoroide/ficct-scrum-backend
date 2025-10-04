"""
RBAC Permission Classes for Project Resources.
Implements role-based access control for projects and project team members.
"""
from rest_framework import permissions

from apps.organizations.models import OrganizationMembership
from apps.projects.models import ProjectTeamMember
from apps.workspaces.models import WorkspaceMember


class IsProjectMember(permissions.BasePermission):
    """
    Permission to check if user is a member of the project.
    Allows read access to all project members.
    """

    def has_object_permission(self, request, view, obj):
        """Check if user is a member of the project."""
        # obj could be Project or related model
        if hasattr(obj, "project"):
            project = obj.project
        else:
            project = obj

        # Check direct project membership
        is_project_member = ProjectTeamMember.objects.filter(
            project=project, user=request.user, is_active=True
        ).exists()

        if is_project_member:
            return True

        # Check if user is workspace member (can view projects)
        is_workspace_member = WorkspaceMember.objects.filter(
            workspace=project.workspace, user=request.user, is_active=True
        ).exists()

        return is_workspace_member


class IsProjectLeadOrAdmin(permissions.BasePermission):
    """
    Permission for project lead or admins.
    Required for modifying project settings and managing team members.
    """

    def has_object_permission(self, request, view, obj):
        """Check if user is project lead or has admin role."""
        # Allow read operations for project members
        if request.method in permissions.SAFE_METHODS:
            return IsProjectMember().has_object_permission(request, view, obj)

        # obj could be Project or related model
        if hasattr(obj, "project"):
            project = obj.project
        else:
            project = obj

        # Check if user is the project lead
        if project.lead == request.user:
            return True

        # Check if user is project admin
        project_member = ProjectTeamMember.objects.filter(
            project=project,
            user=request.user,
            role__in=["lead", "admin"],
            is_active=True,
        ).first()

        if project_member:
            return True

        # Check if user is workspace admin
        workspace_member = WorkspaceMember.objects.filter(
            workspace=project.workspace, user=request.user, role="admin", is_active=True
        ).first()

        if workspace_member:
            return True

        # Check if user is organization owner/admin
        org_membership = OrganizationMembership.objects.filter(
            organization=project.workspace.organization,
            user=request.user,
            role__in=["owner", "admin"],
            is_active=True,
        ).first()

        return org_membership is not None


class CanAccessProject(permissions.BasePermission):
    """
    Permission for accessing project resources.
    Checks if user has access through project, workspace, or organization membership.
    """

    def has_object_permission(self, request, view, obj):
        """Check if user can access this project."""
        # obj could be Project or related model
        if hasattr(obj, "project"):
            project = obj.project
        else:
            project = obj

        # Check project membership
        is_project_member = ProjectTeamMember.objects.filter(
            project=project, user=request.user, is_active=True
        ).exists()

        if is_project_member:
            return True

        # Check workspace membership
        is_workspace_member = WorkspaceMember.objects.filter(
            workspace=project.workspace, user=request.user, is_active=True
        ).exists()

        if is_workspace_member:
            # For write operations, need to be project member
            if request.method not in permissions.SAFE_METHODS:
                return False
            return True

        # Check organization membership (read-only for public workspaces)
        if project.workspace.visibility == "public":
            is_org_member = OrganizationMembership.objects.filter(
                organization=project.workspace.organization,
                user=request.user,
                is_active=True,
            ).exists()

            if is_org_member and request.method in permissions.SAFE_METHODS:
                return True

        return False


class CanManageProjectTeam(permissions.BasePermission):
    """
    Permission to manage project team members.
    Project lead, admins, and workspace/org admins can manage team.
    """

    def has_permission(self, request, view):
        """Check if user can manage team at list level."""
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check if user can manage this project team membership."""
        # Allow read operations for project members
        if request.method in permissions.SAFE_METHODS:
            return IsProjectMember().has_object_permission(request, view, obj)

        # obj is ProjectTeamMember
        project = obj.project

        # Check if user is project lead
        if project.lead == request.user:
            return True

        # Check if user is project admin
        is_project_admin = ProjectTeamMember.objects.filter(
            project=project,
            user=request.user,
            role__in=["lead", "admin"],
            is_active=True,
        ).exists()

        if is_project_admin:
            return True

        # Check if user is workspace admin
        is_workspace_admin = WorkspaceMember.objects.filter(
            workspace=project.workspace, user=request.user, role="admin", is_active=True
        ).exists()

        if is_workspace_admin:
            return True

        # Check if user is organization owner/admin
        is_org_admin = OrganizationMembership.objects.filter(
            organization=project.workspace.organization,
            user=request.user,
            role__in=["owner", "admin"],
            is_active=True,
        ).exists()

        return is_org_admin


class CanModifyProjectConfiguration(permissions.BasePermission):
    """
    Permission to modify project configuration.
    Only project lead/admin and workspace/org admins can modify configuration.
    """

    def has_object_permission(self, request, view, obj):
        """Check if user can modify project configuration."""
        # Allow read operations for project members
        if request.method in permissions.SAFE_METHODS:
            return IsProjectMember().has_object_permission(request, view, obj)

        # obj is ProjectConfiguration
        project = obj.project

        return IsProjectLeadOrAdmin().has_object_permission(request, view, project)
