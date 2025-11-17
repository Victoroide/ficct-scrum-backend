"""
ViewSet for managing project team members.
Provides CRUD operations for adding, updating, and removing team members.
"""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.authentication.models import User
from apps.logging.services import LoggerService
from apps.projects.models import Project, ProjectTeamMember
from apps.projects.permissions import CanAccessProject, CanManageProjectTeam
from apps.projects.serializers import (
    AddTeamMemberSerializer,
    ProjectTeamMemberSerializer,
)


@extend_schema_view(
    list=extend_schema(
        tags=["Project Team"],
        operation_id="project_team_members_list",
        summary="List Project Team Members",
        description="Get list of all team members for a specific project.",
    ),
    retrieve=extend_schema(
        tags=["Project Team"],
        operation_id="project_team_members_retrieve",
        summary="Get Team Member Details",
        description="Retrieve detailed information about a project team member.",
    ),
    create=extend_schema(
        tags=["Project Team"],
        operation_id="project_team_members_create",
        summary="Add Team Member",
        description="Add a new team member to the project. User must be a workspace member.",
        request=AddTeamMemberSerializer,
    ),
    partial_update=extend_schema(
        tags=["Project Team"],
        operation_id="project_team_members_partial_update",
        summary="Update Team Member",
        description="Update team member role, permissions, or hourly rate.",
    ),
    destroy=extend_schema(
        tags=["Project Team"],
        operation_id="project_team_members_destroy",
        summary="Remove Team Member",
        description="Remove a team member from the project (soft delete).",
    ),
)
class ProjectTeamViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing project team members.
    
    Provides endpoints for:
    - Listing all team members in a project
    - Adding new team members
    - Updating team member roles and permissions
    - Removing team members from the project
    
    Permissions:
    - Read: Any project member
    - Write: Project lead, admins, or workspace/org admins
    """

    serializer_class = ProjectTeamMemberSerializer
    permission_classes = [IsAuthenticated, CanAccessProject]
    lookup_field = "pk"

    def get_queryset(self):
        """Get team members for the specified project."""
        project_pk = self.kwargs.get("project_pk")
        return ProjectTeamMember.objects.filter(
            project_id=project_pk, is_active=True
        ).select_related("user", "project", "project__workspace")

    def get_permissions(self):
        """Apply appropriate permissions based on action."""
        if self.action in ["create", "partial_update", "destroy", "deactivate", "reactivate"]:
            return [IsAuthenticated(), CanManageProjectTeam()]
        return [IsAuthenticated(), CanAccessProject()]

    def get_project(self):
        """Get the project from URL parameter."""
        project_pk = self.kwargs.get("project_pk")
        try:
            return Project.objects.get(pk=project_pk)
        except Project.DoesNotExist:
            return None

    def create(self, request, *args, **kwargs):
        """
        Add a new team member to the project.
        
        Validates that:
        - User exists and is active
        - User is a workspace member
        - User is not already a team member
        """
        project = self.get_project()
        if not project:
            return Response(
                {"error": "Project not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = AddTeamMemberSerializer(
            data=request.data, context={"project": project, "request": request}
        )
        serializer.is_valid(raise_exception=True)

        try:
            team_member = serializer.save()
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        LoggerService.log_info(
            action="project_team_member_added",
            user=request.user,
            ip_address=request.META.get("REMOTE_ADDR"),
            details={
                "project_id": str(project.id),
                "project_key": project.key,
                "member_id": str(team_member.user.id),
                "member_email": team_member.user.email,
                "role": team_member.role,
            },
        )

        response_serializer = ProjectTeamMemberSerializer(
            team_member, context=self.get_serializer_context()
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        """
        Update team member role, permissions, or hourly rate.
        
        Only project lead and admins can update team members.
        """
        team_member = self.get_object()
        project = team_member.project

        # Validate that the role choice is valid (if provided)
        role = request.data.get("role")
        if role:
            valid_roles = [choice[0] for choice in ProjectTeamMember.ROLE_CHOICES]
            if role not in valid_roles:
                return Response(
                    {"error": f"Invalid role. Must be one of: {', '.join(valid_roles)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = self.get_serializer(
            team_member, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        LoggerService.log_info(
            action="project_team_member_updated",
            user=request.user,
            ip_address=request.META.get("REMOTE_ADDR"),
            details={
                "project_id": str(project.id),
                "project_key": project.key,
                "member_id": str(team_member.user.id),
                "member_email": team_member.user.email,
                "changes": request.data,
            },
        )

        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        """
        Remove team member from project (soft delete).
        
        Sets is_active to False rather than deleting the record.
        """
        team_member = self.get_object()
        project = team_member.project

        # Prevent removing the project lead
        if project.lead == team_member.user:
            return Response(
                {"error": "Cannot remove the project lead. Transfer leadership first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team_member.is_active = False
        team_member.save()

        LoggerService.log_info(
            action="project_team_member_removed",
            user=request.user,
            ip_address=request.META.get("REMOTE_ADDR"),
            details={
                "project_id": str(project.id),
                "project_key": project.key,
                "member_id": str(team_member.user.id),
                "member_email": team_member.user.email,
            },
        )

        return Response(
            {"message": "Team member removed successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )

    @extend_schema(
        tags=["Project Team"],
        operation_id="project_team_members_deactivate",
        summary="Deactivate Team Member",
        description="Temporarily deactivate a team member without removing them.",
    )
    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, project_pk=None, pk=None):
        """Deactivate a team member temporarily."""
        team_member = self.get_object()

        if not team_member.is_active:
            return Response(
                {"error": "Team member is already inactive"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team_member.is_active = False
        team_member.save()

        LoggerService.log_info(
            action="project_team_member_deactivated",
            user=request.user,
            ip_address=request.META.get("REMOTE_ADDR"),
            details={
                "project_id": str(team_member.project.id),
                "member_id": str(team_member.user.id),
            },
        )

        serializer = self.get_serializer(team_member)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Project Team"],
        operation_id="project_team_members_reactivate",
        summary="Reactivate Team Member",
        description="Reactivate a previously deactivated team member.",
    )
    @action(detail=True, methods=["post"], url_path="reactivate")
    def reactivate(self, request, project_pk=None, pk=None):
        """Reactivate a previously deactivated team member."""
        team_member = self.get_object()

        if team_member.is_active:
            return Response(
                {"error": "Team member is already active"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team_member.is_active = True
        team_member.save()

        LoggerService.log_info(
            action="project_team_member_reactivated",
            user=request.user,
            ip_address=request.META.get("REMOTE_ADDR"),
            details={
                "project_id": str(team_member.project.id),
                "member_id": str(team_member.user.id),
            },
        )

        serializer = self.get_serializer(team_member)
        return Response(serializer.data, status=status.HTTP_200_OK)
