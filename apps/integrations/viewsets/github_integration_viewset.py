import secrets

import requests
from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.integrations.models import GitHubIntegration
from apps.integrations.permissions import CanManageIntegrations, CanViewIntegrations
from apps.integrations.serializers import (
    GitHubIntegrationDetailSerializer,
    GitHubIntegrationSerializer,
)
from apps.integrations.services.github_service import GitHubService


@extend_schema_view(
    list=extend_schema(summary="List GitHub integrations", tags=["GitHub Integration"]),
    retrieve=extend_schema(
        summary="Get GitHub integration details", tags=["GitHub Integration"]
    ),
    create=extend_schema(
        summary="Connect GitHub repository", tags=["GitHub Integration"]
    ),
    destroy=extend_schema(
        summary="Disconnect GitHub repository", tags=["GitHub Integration"]
    ),
)
class GitHubIntegrationViewSet(viewsets.ModelViewSet):
    queryset = GitHubIntegration.objects.all()
    serializer_class = GitHubIntegrationSerializer
    permission_classes = [CanManageIntegrations]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return GitHubIntegrationDetailSerializer
        return GitHubIntegrationSerializer

    def get_queryset(self):
        queryset = GitHubIntegration.objects.all()

        project_id = self.request.query_params.get("project")
        if project_id:
            queryset = queryset.filter(project_id=project_id)

        return queryset

    @extend_schema(
        summary="Sync commits from GitHub",
        tags=["GitHub Integration"],
        request=None,
        responses={200: {"type": "object"}},
    )
    @action(detail=True, methods=["post"])
    def sync_commits(self, request, pk=None):
        integration = self.get_object()
        service = GitHubService()

        try:
            count = service.sync_commits(integration)
            return Response(
                {
                    "message": f"Successfully synced {count} commits",
                    "synced_count": count,
                    "last_sync_at": timezone.now(),
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Sync pull requests from GitHub",
        tags=["GitHub Integration"],
        request=None,
        responses={200: {"type": "object"}},
    )
    @action(detail=True, methods=["post"])
    def sync_pull_requests(self, request, pk=None):
        integration = self.get_object()
        service = GitHubService()

        try:
            count = service.sync_pull_requests(integration)
            return Response(
                {
                    "message": f"Successfully synced {count} pull requests",
                    "synced_count": count,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Get code metrics",
        tags=["GitHub Integration"],
        responses={200: {"type": "object"}},
    )
    @action(detail=True, methods=["get"], permission_classes=[CanViewIntegrations])
    def metrics(self, request, pk=None):
        integration = self.get_object()
        service = GitHubService()

        try:
            metrics = service.calculate_code_metrics(integration)
            return Response(metrics, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Get commits for integration",
        tags=["GitHub Integration"],
        responses={200: {"type": "array"}},
    )
    @action(detail=True, methods=["get"], permission_classes=[CanViewIntegrations])
    def commits(self, request, pk=None):
        from apps.integrations.serializers import GitHubCommitSerializer

        integration = self.get_object()
        commits = integration.commits.all()[:50]
        serializer = GitHubCommitSerializer(commits, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Get pull requests for integration",
        tags=["GitHub Integration"],
        responses={200: {"type": "array"}},
    )
    @action(detail=True, methods=["get"], permission_classes=[CanViewIntegrations])
    def pull_requests(self, request, pk=None):
        from apps.integrations.serializers import GitHubPullRequestSerializer

        integration = self.get_object()
        prs = integration.pull_requests.all()[:50]
        serializer = GitHubPullRequestSerializer(prs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Initiate GitHub OAuth flow",
        tags=["GitHub Integration"],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "project": {"type": "string", "format": "uuid"},
                    "redirect_uri": {"type": "string"},
                },
                "required": ["project"],
            }
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "authorization_url": {"type": "string"},
                    "state": {"type": "string"},
                },
            }
        },
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="oauth/initiate",
        permission_classes=[IsAuthenticated],
    )
    def initiate_oauth(self, request):
        """
        Initiate GitHub OAuth flow by generating authorization URL.
        Frontend should redirect user to this URL.
        """
        project_id = request.data.get("project")
        redirect_uri = request.data.get(
            "redirect_uri", settings.GITHUB_OAUTH_CALLBACK_URL
        )

        if not project_id:
            return Response(
                {"error": "project field is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate secure random state for CSRF protection
        state = secrets.token_urlsafe(32)

        # Store state in session for validation
        request.session["github_oauth_state"] = state
        request.session["github_oauth_project"] = project_id
        request.session["github_oauth_user"] = str(request.user.id)

        # Build GitHub authorization URL
        authorization_url = (
            f"https://github.com/login/oauth/authorize"
            f"?client_id={settings.GITHUB_CLIENT_ID}"
            f"&redirect_uri={redirect_uri}"
            f"&scope=repo,read:user"
            f"&state={state}"
        )

        return Response(
            {
                "authorization_url": authorization_url,
                "state": state,
                "message": "Redirect user to authorization_url to begin OAuth flow",
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="GitHub OAuth callback endpoint",
        tags=["GitHub Integration"],
        parameters=[
            {
                "name": "code",
                "in": "query",
                "required": True,
                "schema": {"type": "string"},
                "description": "Authorization code from GitHub",
            },
            {
                "name": "state",
                "in": "query",
                "required": True,
                "schema": {"type": "string"},
                "description": "State parameter for CSRF protection",
            },
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "message": {"type": "string"},
                    "integration_id": {"type": "string"},
                    "repository": {"type": "string"},
                },
            },
            400: {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "error": {"type": "string"},
                },
            },
        },
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="oauth/callback",
        permission_classes=[AllowAny],
    )
    def oauth_callback(self, request):
        """
        Handle OAuth callback from GitHub.
        Exchanges authorization code for access token.
        """
        code = request.query_params.get("code")
        state = request.query_params.get("state")

        if not code or not state:
            return Response(
                {"status": "error", "error": "Missing code or state parameter"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate state (CSRF protection)
        session_state = request.session.get("github_oauth_state")
        if not session_state or session_state != state:
            return Response(
                {"status": "error", "error": "Invalid state parameter"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get stored project and user from session
        project_id = request.session.get("github_oauth_project")
        user_id = request.session.get("github_oauth_user")

        if not project_id or not user_id:
            return Response(
                {"status": "error", "error": "Session expired or invalid"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Exchange code for access token
            token_response = requests.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": settings.GITHUB_OAUTH_CALLBACK_URL,
                },
            )

            token_data = token_response.json()

            if "error" in token_data:
                return Response(
                    {
                        "status": "error",
                        "error": token_data.get(
                            "error_description", "Failed to obtain access token"
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            access_token = token_data.get("access_token")

            if not access_token:
                return Response(
                    {"status": "error", "error": "No access token received"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get repository information from GitHub
            from github import Github

            gh = Github(access_token)
            user = gh.get_user()

            # For now, let's get the first repository or ask for repo URL
            # In production, you'd want to let user select repository
            repos = list(user.get_repos()[:1])
            if not repos:
                return Response(
                    {
                        "status": "error",
                        "error": "No repositories found for this user",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            repo = repos[0]

            # Create GitHubIntegration
            from apps.projects.models import Project

            project = Project.objects.get(id=project_id)

            integration = GitHubIntegration.objects.create(
                project=project,
                repository_url=repo.html_url,
                repository_name=repo.full_name,
                is_active=True,
            )

            # Set encrypted access token
            integration.set_access_token(access_token)
            integration.save()

            # Clean up session
            del request.session["github_oauth_state"]
            del request.session["github_oauth_project"]
            del request.session["github_oauth_user"]

            return Response(
                {
                    "status": "success",
                    "message": "GitHub connected successfully",
                    "integration_id": str(integration.id),
                    "repository": repo.full_name,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"status": "error", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
