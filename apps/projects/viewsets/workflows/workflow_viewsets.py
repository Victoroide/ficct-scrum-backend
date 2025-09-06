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
    IssueTypeSerializer,
    WorkflowStatusSerializer,
    WorkflowTransitionSerializer
)
from apps.logging.services import LoggerService


@extend_schema(tags=['Workflows: Issue Types'])
class IssueTypeViewSet(viewsets.ModelViewSet):
    """
    Issue type management for projects.
    """
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

    @extend_schema(responses={200: IssueTypeSerializer(many=True)})
    @action(detail=True, methods=['get'])
    def by_project(self, request, pk=None):
        """Get issue types for a specific project"""
        try:
            project = get_object_or_404(Project, id=pk)
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
    def create_for_project(self, request, pk=None):
        """Create issue type for a specific project"""
        try:
            project = get_object_or_404(Project, id=pk)
            
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


@extend_schema(tags=['Workflows: Statuses'])
class WorkflowStatusViewSet(viewsets.ModelViewSet):
    """
    Workflow status management for projects.
    """
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

    @extend_schema(responses={200: WorkflowStatusSerializer(many=True)})
    @action(detail=True, methods=['get'])
    def by_project(self, request, pk=None):
        """Get workflow statuses for a specific project"""
        try:
            project = get_object_or_404(Project, id=pk)
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


@extend_schema(tags=['Workflows: Transitions'])
class WorkflowTransitionViewSet(viewsets.ModelViewSet):
    """
    Workflow transition management for projects.
    """
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

    @extend_schema(responses={200: WorkflowTransitionSerializer(many=True)})
    @action(detail=True, methods=['get'])
    def by_project(self, request, pk=None):
        """Get workflow transitions for a specific project"""
        try:
            project = get_object_or_404(Project, id=pk)
            transitions = WorkflowTransition.objects.filter(
                project=project,
                is_active=True
            ).select_related('from_status', 'to_status')
            
            serializer = WorkflowTransitionSerializer(transitions, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            LoggerService.log_error(
                action='get_workflow_transitions_error',
                error=str(e),
                user=request.user
            )
            return Response(
                {'error': 'Failed to retrieve workflow transitions'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
