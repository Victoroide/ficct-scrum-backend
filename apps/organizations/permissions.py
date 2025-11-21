"""
RBAC Permission Classes for Organization Resources.
Implements role-based access control for organizations and memberships.
"""

from rest_framework import permissions

from apps.organizations.models import OrganizationMembership


class IsOrganizationMember(permissions.BasePermission):
    """
    Permission to check if user is a member of the organization.
    Allows read access to all organization members.
    """

    def has_object_permission(self, request, view, obj):
        """Check if user is an active member of the organization."""
        # obj could be Organization or OrganizationMembership
        if hasattr(obj, "organization"):
            # obj is OrganizationMembership
            organization = obj.organization
        else:
            # obj is Organization
            organization = obj

        return OrganizationMembership.objects.filter(
            organization=organization, user=request.user, is_active=True
        ).exists()


class IsOrganizationOwnerOrAdmin(permissions.BasePermission):
    """
    Permission to check if user is owner or admin of the organization.
    Required for update and delete operations on organizations.
    """

    def has_object_permission(self, request, view, obj):
        """Check if user has owner or admin role."""
        # Allow read operations for all organization members
        if request.method in permissions.SAFE_METHODS:
            return IsOrganizationMember().has_object_permission(request, view, obj)

        # obj could be Organization or OrganizationMembership
        if hasattr(obj, "organization"):
            organization = obj.organization
        else:
            organization = obj

        membership = OrganizationMembership.objects.filter(
            organization=organization,
            user=request.user,
            role__in=["owner", "admin"],
            is_active=True,
        ).first()

        return membership is not None


class CanManageMembers(permissions.BasePermission):
    """
    Permission to manage organization members.
    Owner, admin, and manager roles can invite/manage members.
    """

    def has_permission(self, request, view):
        """Check if user can manage members at list level."""
        # For create operations, check in has_object_permission with organization
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check if user can manage this specific membership."""
        # Allow read operations for organization members
        if request.method in permissions.SAFE_METHODS:
            return IsOrganizationMember().has_object_permission(request, view, obj)

        # obj is OrganizationMembership
        organization = obj.organization

        # Check if requesting user has management permissions
        membership = OrganizationMembership.objects.filter(
            organization=organization,
            user=request.user,
            role__in=["owner", "admin", "manager"],
            is_active=True,
        ).first()

        if not membership:
            return False

        # Owners can manage anyone
        if membership.role == "owner":
            return True

        # Admins can't change owner roles or other admins
        if membership.role == "admin":
            return obj.role not in ["owner", "admin"]

        # Managers can only change regular members
        if membership.role == "manager":
            return obj.role in ["member", "guest"]

        return False


class IsOrganizationOwner(permissions.BasePermission):
    """
    Permission for operations that only the organization owner can perform.
    Such as deleting the organization or transferring ownership.
    """

    def has_object_permission(self, request, view, obj):
        """Check if user is the organization owner."""
        if hasattr(obj, "organization"):
            organization = obj.organization
        else:
            organization = obj

        # Check if user is the owner
        if hasattr(organization, "owner"):
            return organization.owner == request.user

        # Fallback: check membership role
        membership = OrganizationMembership.objects.filter(
            organization=organization, user=request.user, role="owner", is_active=True
        ).first()

        return membership is not None
