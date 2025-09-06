from rest_framework import viewsets, permissions, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, inline_serializer

from apps.projects.models import (
    Project,
    ProjectTeamMember,
    IssueType,
    WorkflowStatus,
    WorkflowTransition
)
from apps.projects.serializers import (
    ProjectSerializer,
    ProjectTeamMemberSerializer,
    IssueTypeSerializer,
    WorkflowStatusSerializer,
    WorkflowTransitionSerializer,
    AddTeamMemberSerializer
)
from apps.organizations.models import Workspace
from apps.logging.services import LoggerService


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['status', 'methodology', 'priority']
    search_fields = ['name', 'key', 'description']
    ordering = ['-created_at']
    
    def get_queryset(self):
        # Guard for Spectacular schema generation
        if getattr(self, "swagger_fake_view", False):
            return Project.objects.none()
        return Project.objects.filter(
            workspace__members__user=self.request.user,
            workspace__members__is_active=True,
            is_active=True
        ).distinct().select_related('workspace', 'lead', 'created_by')

    @extend_schema(
        request=ProjectSerializer,
        responses={201: ProjectSerializer}
    )
    @transaction.atomic
    def create(self, request):
        try:
            workspace_id = request.data.get('workspace_id')
            if not workspace_id:
                return Response(
                    {'error': 'workspace_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            workspace = get_object_or_404(Workspace, id=workspace_id)
            
            # Check if user can create projects in this workspace
            from apps.organizations.models import WorkspaceMembership
            membership = WorkspaceMembership.objects.filter(
                workspace=workspace,
                user=request.user,
                is_active=True
            ).first()
            
            if not membership or not membership.can_manage_projects:
                return Response(
                    {'error': 'You do not have permission to create projects in this workspace'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = self.get_serializer(
                data=request.data,
                context={'request': request, 'workspace': workspace}
            )
            
            if serializer.is_valid():
                project = serializer.save()
                
                LoggerService.log_info(
                    action='project_created',
                    user=request.user,
                    details={
                        'project_id': str(project.id),
                        'project_name': project.name,
                        'workspace_id': str(workspace.id)
                    }
                )
                
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            LoggerService.log_error(
                action='create_project_error',
                error=str(e),
                user=request.user
            )
            return Response(
                {'error': 'Failed to create project'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(responses={200: ProjectTeamMemberSerializer(many=True)})
    @action(detail=True, methods=['get'])
    def team_members(self, request, pk=None):
        try:
            project = self.get_object()
            team_members = ProjectTeamMember.objects.filter(
                project=project,
                is_active=True
            ).select_related('user')
            
            serializer = ProjectTeamMemberSerializer(team_members, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            LoggerService.log_error(
                action='get_project_team_members_error',
                error=str(e),
                user=request.user
            )
            return Response(
                {'error': 'Failed to retrieve team members'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        request=AddTeamMemberSerializer,
        responses={201: ProjectTeamMemberSerializer}
    )
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def add_team_member(self, request, pk=None):
        try:
            project = self.get_object()
            
            # Check if user can manage team
            team_member = ProjectTeamMember.objects.filter(
                project=project,
                user=request.user,
                is_active=True
            ).first()
            
            if not team_member or not team_member.can_manage_project:
                return Response(
                    {'error': 'You do not have permission to add team members'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = AddTeamMemberSerializer(
                data=request.data,
                context={'project': project}
            )
            
            if serializer.is_valid():
                team_member = serializer.save()
                
                LoggerService.log_info(
                    action='project_team_member_added',
                    user=request.user,
                    details={
                        'project_id': str(project.id),
                        'added_user_id': str(team_member.user.id),
                        'role': team_member.role
                    }
                )
                
                member_serializer = ProjectTeamMemberSerializer(team_member)
                return Response(member_serializer.data, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            LoggerService.log_error(
                action='add_project_team_member_error',
                error=str(e),
                user=request.user
            )
            return Response(
                {'error': 'Failed to add team member'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(responses={200: IssueTypeSerializer(many=True)})
    @action(detail=True, methods=['get'])
    def issue_types(self, request, pk=None):
        try:
            project = self.get_object()
            issue_types = IssueType.objects.filter(
                project=project,
                is_active=True
            )
            
            serializer = IssueTypeSerializer(issue_types, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            LoggerService.log_error(
                action='get_project_issue_types_error',
                error=str(e),
                user=request.user
            )
            return Response(
                {'error': 'Failed to retrieve issue types'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        request=IssueTypeSerializer,
        responses={201: IssueTypeSerializer}
    )
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def create_issue_type(self, request, pk=None):
        try:
            project = self.get_object()
            
            # Check permissions
            team_member = ProjectTeamMember.objects.filter(
                project=project,
                user=request.user,
                is_active=True
            ).first()
            
            if not team_member or not team_member.can_manage_project:
                return Response(
                    {'error': 'You do not have permission to create issue types'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = IssueTypeSerializer(
                data=request.data,
                context={'project': project}
            )
            
            if serializer.is_valid():
                issue_type = serializer.save()
                
                LoggerService.log_info(
                    action='issue_type_created',
                    user=request.user,
                    details={
                        'project_id': str(project.id),
                        'issue_type_name': issue_type.name
                    }
                )
                
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            LoggerService.log_error(
                action='create_issue_type_error',
                error=str(e),
                user=request.user
            )
            return Response(
                {'error': 'Failed to create issue type'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(responses={200: WorkflowStatusSerializer(many=True)})
    @action(detail=True, methods=['get'])
    def workflow_statuses(self, request, pk=None):
        try:
            project = self.get_object()
            statuses = WorkflowStatus.objects.filter(
                project=project,
                is_active=True
            ).order_by('order', 'name')
            
            serializer = WorkflowStatusSerializer(statuses, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            LoggerService.log_error(
                action='get_workflow_statuses_error',
                error=str(e),
                user=request.user
            )
            return Response(
                {'error': 'Failed to retrieve workflow statuses'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        responses={
            200: inline_serializer(
                name='ArchiveProjectResponse',
                fields={'message': serializers.CharField()}
            )
        }
    )
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def archive(self, request, pk=None):
        try:
            project = self.get_object()
            
            # Check permissions
            team_member = ProjectTeamMember.objects.filter(
                project=project,
                user=request.user,
                is_active=True
            ).first()
            
            if not team_member or not team_member.can_manage_project:
                return Response(
                    {'error': 'You do not have permission to archive this project'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            project.status = 'archived'
            project.is_active = False
            project.save()
            
            LoggerService.log_info(
                action='project_archived',
                user=request.user,
                details={'project_id': str(project.id)}
            )
            
            return Response(
                {'message': 'Project archived successfully'},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            LoggerService.log_error(
                action='archive_project_error',
                error=str(e),
                user=request.user
            )
            return Response(
                {'error': 'Failed to archive project'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class IssueTypeViewSet(viewsets.ModelViewSet):
    serializer_class = IssueTypeSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Guard for Spectacular schema generation
        if getattr(self, "swagger_fake_view", False):
            return IssueType.objects.none()
        return IssueType.objects.filter(
            project__workspace__members__user=self.request.user,
            project__workspace__members__is_active=True,
            is_active=True
        ).distinct().select_related('project')


class WorkflowStatusViewSet(viewsets.ModelViewSet):
    serializer_class = WorkflowStatusSerializer
    permission_classes = [permissions.IsAuthenticated]
    ordering = ['order', 'name']
    
    def get_queryset(self):
        # Guard for Spectacular schema generation
        if getattr(self, "swagger_fake_view", False):
            return WorkflowStatus.objects.none()
        return WorkflowStatus.objects.filter(
            project__workspace__members__user=self.request.user,
            project__workspace__members__is_active=True,
            is_active=True
        ).distinct().select_related('project')


class WorkflowTransitionViewSet(viewsets.ModelViewSet):
    serializer_class = WorkflowTransitionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Guard for Spectacular schema generation
        if getattr(self, "swagger_fake_view", False):
            return WorkflowTransition.objects.none()
        return WorkflowTransition.objects.filter(
            project__workspace__members__user=self.request.user,
            project__workspace__members__is_active=True,
            is_active=True
        ).distinct().select_related('project', 'from_status', 'to_status')
