"""
RBAC Permission Classes for Workspace Resources.
Implements role-based access control for workspaces and workspace members.
"""
from rest_framework import permissions

from apps.organizations.models import OrganizationMembership
from apps.workspaces.models import WorkspaceMember


class IsWorkspaceMember(permissions.BasePermission):
    """
    Permission to check if user is a member of the workspace.
    Allows read access to all workspace members.
    """

    def has_object_permission(self, request, view, obj):
        """Check if user is an active member of the workspace."""
        # obj could be Workspace or WorkspaceMember
        if hasattr(obj, "workspace"):
            workspace = obj.workspace
        else:
            workspace = obj

        return WorkspaceMember.objects.filter(
            workspace=workspace, user=request.user, is_active=True
        ).exists()


class IsWorkspaceAdmin(permissions.BasePermission):
    """
    Permission to check if user is an admin of the workspace.
    Required for modifying workspace settings and managing members.
    """

    def has_object_permission(self, request, view, obj):
        """Check if user has admin role in workspace."""
        # Allow read operations for workspace members
        if request.method in permissions.SAFE_METHODS:
            return IsWorkspaceMember().has_object_permission(request, view, obj)

        # obj could be Workspace or WorkspaceMember
        if hasattr(obj, "workspace"):
            workspace = obj.workspace
        else:
            workspace = obj

        # Check workspace admin role
        workspace_member = WorkspaceMember.objects.filter(
            workspace=workspace, user=request.user, role="admin", is_active=True
        ).first()

        if workspace_member:
            return True

        # Organization owners and admins also have admin access to workspaces
        org_membership = OrganizationMembership.objects.filter(
            organization=workspace.organization,
            user=request.user,
            role__in=["owner", "admin"],
            is_active=True,
        ).first()

        return org_membership is not None


class CanAccessWorkspace(permissions.BasePermission):
    """
    Permission for accessing workspace resources.
    Checks if user is either a workspace member or organization member
    based on workspace visibility settings.
    """

    def has_object_permission(self, request, view, obj):
        """Check if user can access this workspace."""
        # obj could be Workspace or WorkspaceMember
        if hasattr(obj, "workspace"):
            workspace = obj.workspace
        else:
            workspace = obj

        # Check if user is workspace member
        is_workspace_member = WorkspaceMember.objects.filter(
            workspace=workspace, user=request.user, is_active=True
        ).exists()

        if is_workspace_member:
            return True

        # If workspace is public or restricted, organization members can view
        if workspace.visibility in ["public", "restricted"]:
            is_org_member = OrganizationMembership.objects.filter(
                organization=workspace.organization, user=request.user, is_active=True
            ).exists()

            # Public workspaces: all org members can read
            if workspace.visibility == "public" and is_org_member:
                if request.method in permissions.SAFE_METHODS:
                    return True

            # Restricted workspaces: org admins can access
            if workspace.visibility == "restricted" and is_org_member:
                org_membership = OrganizationMembership.objects.filter(
                    organization=workspace.organization,
                    user=request.user,
                    role__in=["owner", "admin"],
                    is_active=True,
                ).first()
                if org_membership:
                    return True

        return False


class CanManageWorkspaceMembers(permissions.BasePermission):
    """
    Permission to manage workspace members.
    Workspace admins and organization owners/admins can manage members.
    """

    def has_permission(self, request, view):
        """Check if user can manage members at list level."""
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check if user can manage this workspace membership."""
        # Allow read operations for workspace members
        if request.method in permissions.SAFE_METHODS:
            return IsWorkspaceMember().has_object_permission(request, view, obj)

        # obj is WorkspaceMember
        workspace = obj.workspace

        # Check if user is workspace admin
        is_workspace_admin = WorkspaceMember.objects.filter(
            workspace=workspace, user=request.user, role="admin", is_active=True
        ).exists()

        if is_workspace_admin:
            return True

        # Check if user is organization owner/admin
        is_org_admin = OrganizationMembership.objects.filter(
            organization=workspace.organization,
            user=request.user,
            role__in=["owner", "admin"],
            is_active=True,
        ).exists()

        return is_org_admin
