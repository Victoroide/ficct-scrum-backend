from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.db import transaction
from apps.projects.models import Project
from apps.projects.serializers import ProjectSerializer
from base.utils.file_handlers import upload_project_file_to_s3


@extend_schema_view(
    list=extend_schema(tags=['Projects'], operation_id='projects_list', summary='List Projects'),
    retrieve=extend_schema(tags=['Projects'], operation_id='projects_retrieve', summary='Get Project Details'),
    create=extend_schema(tags=['Projects'], operation_id='projects_create', summary='Create Project'),
    update=extend_schema(tags=['Projects'], operation_id='projects_update', summary='Update Project'),
    partial_update=extend_schema(tags=['Projects'], operation_id='projects_partial_update', summary='Partial Update Project'),
    destroy=extend_schema(tags=['Projects'], operation_id='projects_destroy', summary='Delete Project'),
)
class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Project.objects.filter(
            workspace__members__user=self.request.user,
            workspace__members__is_active=True
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @extend_schema(tags=['Projects'], operation_id='projects_upload_attachment', summary='Upload Project Attachment')
    @action(detail=True, methods=['post'], url_path='upload-attachment')
    def upload_attachment(self, request, pk=None):
        project = self.get_object()
        if 'attachment' not in request.FILES:
            return Response({'error': 'No attachment file provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        attachment_file = request.FILES['attachment']
        try:
            attachment_path = upload_project_file_to_s3(attachment_file, project.id)
            project.attachments = attachment_path
            project.save()
            return Response({'attachment_url': project.attachments.url}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
