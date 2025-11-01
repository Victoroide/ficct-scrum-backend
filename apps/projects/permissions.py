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
        elif hasattr(obj, "issue"):
            # Handle IssueComment, IssueAttachment
            project = obj.issue.project
        elif hasattr(obj, "source_issue"):
            # Handle IssueLink
            project = obj.source_issue.project
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
        elif hasattr(obj, "issue"):
            # Handle IssueComment, IssueAttachment
            project = obj.issue.project
        elif hasattr(obj, "source_issue"):
            # Handle IssueLink
            project = obj.source_issue.project
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
    
    ARCHITECTURE:
    - Workspace members have access to ALL projects in their workspace (read + write)
    - Project members have access to their specific project (read + write)
    - Organization members have read-only access to public workspaces
    """

    def has_object_permission(self, request, view, obj):
        """Check if user can access this project."""
        # obj could be Project or related model
        if hasattr(obj, "project"):
            project = obj.project
        elif hasattr(obj, "issue"):
            # Handle IssueComment, IssueAttachment
            project = obj.issue.project
        elif hasattr(obj, "source_issue"):
            # Handle IssueLink
            project = obj.source_issue.project
        else:
            project = obj

        # Check project membership (full access)
        is_project_member = ProjectTeamMember.objects.filter(
            project=project, user=request.user, is_active=True
        ).exists()

        if is_project_member:
            return True

        # Check workspace membership (full access)
        # Workspace members can access ALL projects in their workspace
        is_workspace_member = WorkspaceMember.objects.filter(
            workspace=project.workspace, user=request.user, is_active=True
        ).exists()

        if is_workspace_member:
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


class CanModifyIssue(permissions.BasePermission):
    """
    Permission to modify issues.
    Assignee, reporter, or project admin can modify.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return CanAccessProject().has_object_permission(request, view, obj)

        issue = obj if hasattr(obj, 'assignee') else obj

        if issue.assignee == request.user or issue.reporter == request.user:
            return True

        project_member = ProjectTeamMember.objects.filter(
            project=issue.project,
            user=request.user,
            is_active=True
        ).first()

        if project_member and project_member.can_manage_project:
            return True

        return IsProjectLeadOrAdmin().has_object_permission(request, view, issue.project)


class CanDeleteIssue(permissions.BasePermission):
    """
    Permission to delete issues.
    Only project lead or admin can delete issues.
    """

    def has_object_permission(self, request, view, obj):
        issue = obj if hasattr(obj, 'project') else obj.issue
        return IsProjectLeadOrAdmin().has_object_permission(request, view, issue.project)


class CanManageSprint(permissions.BasePermission):
    """
    Permission to manage sprints.
    Only project lead or admin can manage sprints.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return CanAccessProject().has_object_permission(request, view, obj)

        sprint = obj if hasattr(obj, 'project') else obj
        return IsProjectLeadOrAdmin().has_object_permission(request, view, sprint.project)


class CanModifyBoard(permissions.BasePermission):
    """
    Permission to modify boards.
    Board creator or project admin can modify.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return CanAccessProject().has_object_permission(request, view, obj)

        board = obj if hasattr(obj, 'created_by') else obj

        if board.created_by == request.user:
            return True

        return IsProjectLeadOrAdmin().has_object_permission(request, view, board.project)


class IsProjectTeamMember(permissions.BasePermission):
    """
    Permission to check if user is a team member of the project.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, "project"):
            project = obj.project
        elif hasattr(obj, "issue"):
            # Handle IssueComment, IssueAttachment
            project = obj.issue.project
        elif hasattr(obj, "source_issue"):
            # Handle IssueLink
            project = obj.source_issue.project
        else:
            project = obj

        return ProjectTeamMember.objects.filter(
            project=project, user=request.user, is_active=True
        ).exists()
