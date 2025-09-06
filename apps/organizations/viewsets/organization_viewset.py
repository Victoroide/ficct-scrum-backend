from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.db import transaction
from apps.organizations.models import Organization
from apps.organizations.serializers import OrganizationSerializer
from base.utils.file_handlers import upload_organization_logo_to_s3


@extend_schema_view(
    list=extend_schema(tags=['Organizations'], operation_id='organizations_list', summary='List Organizations'),
    retrieve=extend_schema(tags=['Organizations'], operation_id='organizations_retrieve', summary='Get Organization Details'),
    create=extend_schema(tags=['Organizations'], operation_id='organizations_create', summary='Create Organization'),
    update=extend_schema(tags=['Organizations'], operation_id='organizations_update', summary='Update Organization'),
    partial_update=extend_schema(tags=['Organizations'], operation_id='organizations_partial_update', summary='Partial Update Organization'),
    destroy=extend_schema(tags=['Organizations'], operation_id='organizations_destroy', summary='Delete Organization'),
)
class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Organization.objects.filter(
            memberships__user=self.request.user,
            memberships__is_active=True
        ).distinct()

    @transaction.atomic
    def perform_create(self, serializer):
        organization = serializer.save(owner=self.request.user)
        from apps.organizations.models import OrganizationMembership
        OrganizationMembership.objects.create(
            organization=organization,
            user=self.request.user,
            role='owner',
            status='active'
        )

    @extend_schema(tags=['Organizations'], operation_id='organizations_upload_logo', summary='Upload Organization Logo')
    @action(detail=True, methods=['post'], url_path='upload-logo')
    def upload_logo(self, request, pk=None):
        organization = self.get_object()
        if 'logo' not in request.FILES:
            return Response({'error': 'No logo file provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        logo_file = request.FILES['logo']
        try:
            logo_path = upload_organization_logo_to_s3(logo_file, organization.id)
            organization.logo = logo_path
            organization.save()
            return Response({'logo_url': organization.logo.url}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
