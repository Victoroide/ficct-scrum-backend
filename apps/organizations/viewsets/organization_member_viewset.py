from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.db import transaction
from apps.organizations.models import OrganizationMembership, Organization
from apps.organizations.serializers import OrganizationMemberSerializer
from apps.authentication.models import User


@extend_schema_view(
    list=extend_schema(tags=['Organizations'], operation_id='organization_members_list', summary='List Organization Members'),
    retrieve=extend_schema(tags=['Organizations'], operation_id='organization_members_retrieve', summary='Get Organization Member Details'),
    create=extend_schema(tags=['Organizations'], operation_id='organization_members_create', summary='Invite Member to Organization'),
    update=extend_schema(tags=['Organizations'], operation_id='organization_members_update', summary='Update Member Role'),
    partial_update=extend_schema(tags=['Organizations'], operation_id='organization_members_partial_update', summary='Partial Update Member'),
    destroy=extend_schema(tags=['Organizations'], operation_id='organization_members_destroy', summary='Remove Member from Organization'),
)
class OrganizationMemberViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationMemberSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return OrganizationMembership.objects.filter(
            organization__memberships__user=self.request.user,
            organization__memberships__is_active=True
        ).distinct()

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save(invited_by=self.request.user)

    @extend_schema(tags=['Organizations'], operation_id='organization_members_update_role', summary='Update Member Role')
    @action(detail=True, methods=['patch'], url_path='update-role')
    def update_role(self, request, pk=None):
        membership = self.get_object()
        new_role = request.data.get('role')
        
        if new_role not in dict(OrganizationMembership.ROLE_CHOICES):
            return Response({'error': 'Invalid role'}, status=status.HTTP_400_BAD_REQUEST)
        
        membership.role = new_role
        membership.save()
        
        serializer = self.get_serializer(membership)
        return Response(serializer.data, status=status.HTTP_200_OK)
