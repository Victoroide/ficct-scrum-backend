from django.db.models import Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.integrations.models import GitHubCommit
from apps.integrations.permissions import CanViewIntegrations
from apps.integrations.serializers import (
    GitHubCommitDetailSerializer,
    GitHubCommitSerializer,
    LinkCommitToIssueSerializer,
)


@extend_schema_view(
    list=extend_schema(
        summary="List GitHub commits",
        tags=["Integrations"],
        parameters=[
            OpenApiParameter(
                name="project",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Filter commits by project UUID",
                required=False,
            ),
            OpenApiParameter(
                name="repository",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Filter commits by repository UUID",
                required=False,
            ),
            OpenApiParameter(
                name="author_email",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter commits by author email",
                required=False,
            ),
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Search in commit message, author name, author email, or SHA. Example: 'Raul', 'fix bug', 'abc123'",
                required=False,
            ),
        ],
    ),
    retrieve=extend_schema(summary="Get commit details", tags=["Integrations"]),
)
class GitHubCommitViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = GitHubCommit.objects.all()
    serializer_class = GitHubCommitSerializer
    permission_classes = [CanViewIntegrations]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return GitHubCommitDetailSerializer
        return GitHubCommitSerializer

    def get_queryset(self):
        queryset = GitHubCommit.objects.all().select_related("repository__project")

        # Filter by repository
        repository_id = self.request.query_params.get("repository")
        if repository_id:
            queryset = queryset.filter(repository_id=repository_id)

        # Filter by project
        project_id = self.request.query_params.get("project")
        if project_id:
            queryset = queryset.filter(repository__project_id=project_id)

        # Filter by author email
        author_email = self.request.query_params.get("author_email")
        if author_email:
            queryset = queryset.filter(author_email=author_email)

        # Search across multiple fields (efficient with Q objects)
        search = self.request.query_params.get("search")
        if search:
            search_term = search.strip()
            queryset = queryset.filter(
                Q(message__icontains=search_term)
                | Q(author_name__icontains=search_term)
                | Q(author_email__icontains=search_term)
                | Q(sha__icontains=search_term)
            )

        return queryset

    @extend_schema(
        summary="Link commit to issue",
        tags=["Integrations"],
        request=LinkCommitToIssueSerializer,
        responses={200: {"type": "object"}},
    )
    @action(detail=True, methods=["post"])
    def link_issue(self, request, pk=None):
        commit = self.get_object()
        serializer = LinkCommitToIssueSerializer(data=request.data)

        if serializer.is_valid():
            from apps.projects.models import Issue

            issue = Issue.objects.get(id=serializer.validated_data["issue_id"])
            commit.linked_issues.add(issue)

            return Response(
                {"message": f"Successfully linked commit to issue {issue.key}"},
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Unlink commit from issue",
        tags=["Integrations"],
        request=LinkCommitToIssueSerializer,
        responses={200: {"type": "object"}},
    )
    @action(detail=True, methods=["post"])
    def unlink_issue(self, request, pk=None):
        commit = self.get_object()
        serializer = LinkCommitToIssueSerializer(data=request.data)

        if serializer.is_valid():
            from apps.projects.models import Issue

            issue = Issue.objects.get(id=serializer.validated_data["issue_id"])
            commit.linked_issues.remove(issue)

            return Response(
                {"message": f"Successfully unlinked commit from issue {issue.key}"},
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
