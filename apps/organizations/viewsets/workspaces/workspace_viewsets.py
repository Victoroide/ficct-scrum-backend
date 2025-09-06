from rest_framework import viewsets, permissions, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, inline_serializer

from apps.organizations.models import (
    Workspace,
    WorkspaceMembership,
    OrganizationMembership
)
from apps.organizations.serializers import (
    WorkspaceSerializer,
    WorkspaceMembershipSerializer
)
from apps.logging.services import LoggerService


@extend_schema(tags=['Workspaces'])
class WorkspaceViewSet(viewsets.ModelViewSet):
    """
    Workspace CRUD operations and member management.
    """
    serializer_class = WorkspaceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Guard for Spectacular schema generation
        if getattr(self, "swagger_fake_view", False):
            return Workspace.objects.none()
        return Workspace.objects.filter(
            members__user=self.request.user,
            members__is_active=True,
            is_active=True
        ).distinct().select_related('organization', 'created_by')

    @extend_schema(responses={200: WorkspaceMembershipSerializer(many=True)})
    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        """Get workspace members"""
        try:
            workspace = self.get_object()
            memberships = WorkspaceMembership.objects.filter(
                workspace=workspace,
                is_active=True
            ).select_related('user')
            
            serializer = WorkspaceMembershipSerializer(memberships, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            LoggerService.log_error(
                action='get_workspace_members_error',
                user=request.user,
                error=str(e)
            )
            return Response(
                {'error': 'Failed to retrieve workspace members'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        request=inline_serializer(
            name='AddWorkspaceMemberRequest',
            fields={
                'user_id': serializers.UUIDField(),
                'role': serializers.CharField()
            }
        ),
        responses={201: WorkspaceMembershipSerializer}
    )
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def add_member(self, request, pk=None):
        """Add member to workspace"""
        try:
            workspace = self.get_object()
            
            # Check if user can manage workspace
            membership = WorkspaceMembership.objects.get(
                workspace=workspace,
                user=request.user,
                is_active=True
            )
            
            if not membership.can_edit_workspace:
                return Response(
                    {'error': 'You do not have permission to add members'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            user_id = request.data.get('user_id')
            role = request.data.get('role', 'member')
            
            from apps.authentication.models import User
            user = get_object_or_404(User, id=user_id)
            
            # Check if user is organization member
            if not OrganizationMembership.objects.filter(
                organization=workspace.organization,
                user=user,
                is_active=True
            ).exists():
                return Response(
                    {'error': 'User must be an organization member first'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            workspace_membership, created = WorkspaceMembership.objects.get_or_create(
                workspace=workspace,
                user=user,
                defaults={'role': role}
            )
            
            if not created:
                workspace_membership.role = role
                workspace_membership.is_active = True
                workspace_membership.save()
            
            LoggerService.log_info(
                action='workspace_member_added',
                user=request.user,
                details={
                    'workspace_id': str(workspace.id),
                    'added_user_id': str(user.id),
                    'role': role
                }
            )
            
            serializer = WorkspaceMembershipSerializer(workspace_membership)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except WorkspaceMembership.DoesNotExist:
            return Response(
                {'error': 'You are not a member of this workspace'},
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            LoggerService.log_error(
                action='add_workspace_member_error',
                user=request.user,
                error=str(e)
            )
            return Response(
                {'error': 'Failed to add workspace member'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
