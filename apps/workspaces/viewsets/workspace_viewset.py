from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.db import transaction
from apps.workspaces.models import Workspace
from apps.workspaces.serializers import WorkspaceSerializer
from base.utils.file_handlers import upload_workspace_asset_to_s3


@extend_schema_view(
    list=extend_schema(tags=['Workspaces'], operation_id='workspaces_list', summary='List Workspaces'),
    retrieve=extend_schema(tags=['Workspaces'], operation_id='workspaces_retrieve', summary='Get Workspace Details'),
    create=extend_schema(tags=['Workspaces'], operation_id='workspaces_create', summary='Create Workspace'),
    update=extend_schema(tags=['Workspaces'], operation_id='workspaces_update', summary='Update Workspace'),
    partial_update=extend_schema(tags=['Workspaces'], operation_id='workspaces_partial_update', summary='Partial Update Workspace'),
    destroy=extend_schema(tags=['Workspaces'], operation_id='workspaces_destroy', summary='Delete Workspace'),
)
class WorkspaceViewSet(viewsets.ModelViewSet):
    queryset = Workspace.objects.all()
    serializer_class = WorkspaceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Workspace.objects.filter(
            members__user=self.request.user,
            members__is_active=True
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @extend_schema(tags=['Workspaces'], operation_id='workspaces_upload_cover', summary='Upload Workspace Cover Image')
    @action(detail=True, methods=['post'], url_path='upload-cover')
    def upload_cover(self, request, pk=None):
        workspace = self.get_object()
        if 'cover_image' not in request.FILES:
            return Response({'error': 'No cover image file provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        cover_file = request.FILES['cover_image']
        try:
            cover_path = upload_workspace_asset_to_s3(cover_file, workspace.id)
            workspace.cover_image = cover_path
            workspace.save()
            return Response({'cover_image_url': workspace.cover_image.url}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
