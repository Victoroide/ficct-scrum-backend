from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, extend_schema_view
from apps.projects.models import ProjectConfiguration
from apps.projects.serializers import ProjectConfigSerializer


@extend_schema_view(
    list=extend_schema(tags=['Projects'], operation_id='project_configs_list', summary='List Project Configurations'),
    retrieve=extend_schema(tags=['Projects'], operation_id='project_configs_retrieve', summary='Get Project Configuration'),
    create=extend_schema(tags=['Projects'], operation_id='project_configs_create', summary='Create Project Configuration'),
    update=extend_schema(tags=['Projects'], operation_id='project_configs_update', summary='Update Project Configuration'),
    partial_update=extend_schema(tags=['Projects'], operation_id='project_configs_partial_update', summary='Partial Update Project Configuration'),
    destroy=extend_schema(tags=['Projects'], operation_id='project_configs_destroy', summary='Delete Project Configuration'),
)
class ProjectConfigViewSet(viewsets.ModelViewSet):
    queryset = ProjectConfiguration.objects.all()
    serializer_class = ProjectConfigSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ProjectConfiguration.objects.filter(
            project__workspace__members__user=self.request.user,
            project__workspace__members__is_active=True
        ).distinct()
