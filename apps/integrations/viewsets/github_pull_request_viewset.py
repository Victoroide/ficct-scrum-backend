from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.integrations.models import GitHubPullRequest
from apps.integrations.permissions import CanViewIntegrations
from apps.integrations.serializers import (
    GitHubPullRequestDetailSerializer,
    GitHubPullRequestSerializer,
    LinkPullRequestToIssueSerializer,
)


@extend_schema_view(
    list=extend_schema(
        summary="List GitHub pull requests", tags=["GitHub Pull Requests"]
    ),
    retrieve=extend_schema(
        summary="Get pull request details", tags=["GitHub Pull Requests"]
    ),
)
class GitHubPullRequestViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = GitHubPullRequest.objects.all()
    serializer_class = GitHubPullRequestSerializer
    permission_classes = [CanViewIntegrations]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return GitHubPullRequestDetailSerializer
        return GitHubPullRequestSerializer

    def get_queryset(self):
        queryset = GitHubPullRequest.objects.all().select_related("repository__project")

        repository_id = self.request.query_params.get("repository")
        if repository_id:
            queryset = queryset.filter(repository_id=repository_id)

        project_id = self.request.query_params.get("project")
        if project_id:
            queryset = queryset.filter(repository__project_id=project_id)

        state = self.request.query_params.get("state")
        if state:
            queryset = queryset.filter(state=state)

        return queryset

    @extend_schema(
        summary="Link pull request to issue",
        tags=["GitHub Pull Requests"],
        request=LinkPullRequestToIssueSerializer,
        responses={200: {"type": "object"}},
    )
    @action(detail=True, methods=["post"])
    def link_issue(self, request, pk=None):
        pr = self.get_object()
        serializer = LinkPullRequestToIssueSerializer(data=request.data)

        if serializer.is_valid():
            from apps.projects.models import Issue

            issue = Issue.objects.get(id=serializer.validated_data["issue_id"])
            pr.linked_issues.add(issue)

            return Response(
                {"message": f"Successfully linked pull request to issue {issue.key}"},
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
