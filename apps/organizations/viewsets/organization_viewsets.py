from rest_framework import viewsets, permissions, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, inline_serializer

from apps.organizations.models import (
    Organization,
    OrganizationMembership,
    OrganizationInvitation,
    Workspace,
    WorkspaceMembership
)
from apps.organizations.serializers import (
    OrganizationSerializer,
    OrganizationMembershipSerializer,
    OrganizationInvitationSerializer,
    WorkspaceSerializer,
    WorkspaceMembershipSerializer,
    InvitationAcceptSerializer
)
from apps.logging.services import LoggerService


class OrganizationViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Guard for Spectacular schema generation
        if getattr(self, "swagger_fake_view", False):
            return Organization.objects.none()
        return Organization.objects.filter(
            memberships__user=self.request.user,
            memberships__is_active=True,
            is_active=True
        ).distinct()

    @extend_schema(responses={200: OrganizationSerializer(many=True)})
    def list(self, request):
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            LoggerService.log_error(
                action='list_organizations_error',
                user=request.user,
                error=str(e)
            )
            return Response(
                {'error': 'Failed to retrieve organizations'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        request=OrganizationSerializer,
        responses={201: OrganizationSerializer}
    )
    @transaction.atomic
    def create(self, request):
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                organization = serializer.save()
                
                LoggerService.log_info(
                    action='organization_created',
                    user=request.user,
                    details={
                        'organization_id': str(organization.id),
                        'organization_name': organization.name
                    }
                )
                
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            LoggerService.log_error(
                action='create_organization_error',
                user=request.user,
                error=str(e)
            )
            return Response(
                {'error': 'Failed to create organization'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(responses={200: OrganizationMembershipSerializer(many=True)})
    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        try:
            organization = self.get_object()
            memberships = OrganizationMembership.objects.filter(
                organization=organization,
                is_active=True
            ).select_related('user', 'invited_by')
            
            serializer = OrganizationMembershipSerializer(memberships, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            LoggerService.log_error(
                action='get_organization_members_error',
                user=request.user,
                error=str(e)
            )
            return Response(
                {'error': 'Failed to retrieve organization members'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        request=OrganizationInvitationSerializer,
        responses={201: OrganizationInvitationSerializer}
    )
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def invite_member(self, request, pk=None):
        try:
            organization = self.get_object()
            
            # Check if user can invite members
            membership = OrganizationMembership.objects.get(
                organization=organization,
                user=request.user,
                is_active=True
            )
            
            if not membership.can_manage_members:
                return Response(
                    {'error': 'You do not have permission to invite members'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = OrganizationInvitationSerializer(
                data=request.data,
                context={'request': request, 'organization': organization}
            )
            
            if serializer.is_valid():
                invitation = serializer.save()
                
                LoggerService.log_info(
                    action='organization_member_invited',
                    user=request.user,
                    details={
                        'organization_id': str(organization.id),
                        'invited_email': invitation.email,
                        'role': invitation.role
                    }
                )
                
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except OrganizationMembership.DoesNotExist:
            return Response(
                {'error': 'You are not a member of this organization'},
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            LoggerService.log_error(
                action='invite_organization_member_error',
                user=request.user,
                error=str(e)
            )
            return Response(
                {'error': 'Failed to send invitation'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(responses={200: WorkspaceSerializer(many=True)})
    @action(detail=True, methods=['get'])
    def workspaces(self, request, pk=None):
        try:
            organization = self.get_object()
            workspaces = Workspace.objects.filter(
                organization=organization,
                is_active=True
            ).select_related('created_by')
            
            serializer = WorkspaceSerializer(
                workspaces,
                many=True,
                context={'request': request}
            )
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            LoggerService.log_error(
                action='get_organization_workspaces_error',
                user=request.user,
                error=str(e)
            )
            return Response(
                {'error': 'Failed to retrieve workspaces'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        request=WorkspaceSerializer,
        responses={201: WorkspaceSerializer}
    )
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def create_workspace(self, request, pk=None):
        try:
            organization = self.get_object()
            
            # Check if user can create workspaces
            membership = OrganizationMembership.objects.get(
                organization=organization,
                user=request.user,
                is_active=True
            )
            
            if not membership.can_manage_members:
                return Response(
                    {'error': 'You do not have permission to create workspaces'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = WorkspaceSerializer(
                data=request.data,
                context={'request': request, 'organization': organization}
            )
            
            if serializer.is_valid():
                workspace = serializer.save()
                
                LoggerService.log_info(
                    action='workspace_created',
                    user=request.user,
                    details={
                        'organization_id': str(organization.id),
                        'workspace_id': str(workspace.id),
                        'workspace_name': workspace.name
                    }
                )
                
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except OrganizationMembership.DoesNotExist:
            return Response(
                {'error': 'You are not a member of this organization'},
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            LoggerService.log_error(
                action='create_workspace_error',
                user=request.user,
                error=str(e)
            )
            return Response(
                {'error': 'Failed to create workspace'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class InvitationViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        request=InvitationAcceptSerializer,
        responses={200: OrganizationMembershipSerializer}
    )
    @action(detail=False, methods=['post'])
    @transaction.atomic
    def accept(self, request):
        try:
            serializer = InvitationAcceptSerializer(
                data=request.data,
                context={'request': request}
            )
            
            if serializer.is_valid():
                membership = serializer.save()
                
                LoggerService.log_info(
                    action='organization_invitation_accepted',
                    user=request.user,
                    details={
                        'organization_id': str(membership.organization.id),
                        'role': membership.role
                    }
                )
                
                membership_serializer = OrganizationMembershipSerializer(membership)
                return Response(membership_serializer.data, status=status.HTTP_200_OK)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            LoggerService.log_error(
                action='accept_invitation_error',
                user=request.user,
                error=str(e)
            )
            return Response(
                {'error': 'Failed to accept invitation'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class WorkspaceViewSet(viewsets.ModelViewSet):
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
