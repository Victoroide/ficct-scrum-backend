from django.db import transaction

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.workspaces.models import WorkspaceMember
from apps.workspaces.serializers import WorkspaceMemberSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["Workspaces"],
        operation_id="workspace_members_list",
        summary="List Workspace Members",
    ),
    retrieve=extend_schema(
        tags=["Workspaces"],
        operation_id="workspace_members_retrieve",
        summary="Get Workspace Member Details",
    ),
    create=extend_schema(
        tags=["Workspaces"],
        operation_id="workspace_members_create",
        summary="Add Member to Workspace",
    ),
    update=extend_schema(
        tags=["Workspaces"],
        operation_id="workspace_members_update",
        summary="Update Member Role",
    ),
    partial_update=extend_schema(
        tags=["Workspaces"],
        operation_id="workspace_members_partial_update",
        summary="Partial Update Member",
    ),
)
class WorkspaceMemberViewSet(viewsets.ModelViewSet):
    serializer_class = WorkspaceMemberSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Handle schema generation
        if getattr(self, "swagger_fake_view", False):
            return WorkspaceMember.objects.none()
            
        if not self.request.user.is_authenticated:
            return WorkspaceMember.objects.none()

        user = self.request.user
        workspace_id = self.kwargs.get("workspace_id")

        if workspace_id:
            queryset = WorkspaceMember.objects.filter(workspace_id=workspace_id)
        else:
            queryset = WorkspaceMember.objects.filter(
                workspace__members__user=user, workspace__members__is_active=True
            ).distinct()

        return queryset.select_related("workspace", "user")

    @extend_schema(
        tags=["Workspaces"],
        operation_id="workspace_members_update_role",
        summary="Update Member Role",
    )
    @action(detail=True, methods=["patch"], url_path="update-role")
    def update_role(self, request, pk=None):
        member = self.get_object()
        new_role = request.data.get("role")

        if new_role not in dict(WorkspaceMember.ROLE_CHOICES):
            return Response(
                {"error": "Invalid role"}, status=status.HTTP_400_BAD_REQUEST
            )

        member.role = new_role
        member.save()

        serializer = self.get_serializer(member)
        return Response(serializer.data, status=status.HTTP_200_OK)
