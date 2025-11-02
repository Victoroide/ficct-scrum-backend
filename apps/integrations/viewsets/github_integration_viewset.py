import logging
import secrets
from datetime import timedelta

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import redirect

logger = logging.getLogger(__name__)

from apps.integrations.models import GitHubIntegration
from apps.integrations.permissions import CanManageIntegrations, CanViewIntegrations
from apps.integrations.serializers import (
    GitHubIntegrationDetailSerializer,
    GitHubIntegrationSerializer,
)
from apps.integrations.services.github_service import GitHubService


@extend_schema_view(
    list=extend_schema(
        summary="List GitHub integrations", 
        tags=["Integrations"],
        description="Returns all GitHub integrations the user has access to. Filter by project using ?project={uuid}"
    ),
    retrieve=extend_schema(
        summary="Get GitHub integration details", 
        tags=["Integrations"],
        description="Returns detailed information about a specific GitHub integration including commit and PR counts"
    ),
    create=extend_schema(
        summary="Connect GitHub repository (Direct - Use OAuth flow instead)", 
        tags=["Integrations"],
        description="""
        **IMPORTANT**: This endpoint requires a GitHub Personal Access Token. 
        For production use, prefer the OAuth flow: POST /oauth/initiate/
        
        **Required Fields**:
        - project (UUID): Project to connect integration to
        - repository_url (string): GitHub repository URL (https://github.com/owner/repo)
        - access_token (string): GitHub Personal Access Token with 'repo' and 'read:user' scopes
        
        **Optional Fields**:
        - sync_commits (boolean): Auto-sync commits (default: true)
        - sync_pull_requests (boolean): Auto-sync pull requests (default: true)
        - auto_link_commits (boolean): Auto-link commits to issues (default: true)
        
        **Permissions**: User must be Project owner/admin, Workspace admin, or Organization owner/admin
        
        **Recommended**: Use POST /oauth/initiate/ for secure OAuth flow
        """,
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "format": "uuid",
                        "description": "Project UUID (REQUIRED)"
                    },
                    "repository_url": {
                        "type": "string",
                        "description": "GitHub repository URL (REQUIRED)",
                        "example": "https://github.com/Victoroide/ficct-scrum-backend"
                    },
                    "access_token": {
                        "type": "string",
                        "description": "GitHub Personal Access Token (REQUIRED)",
                        "example": "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                    },
                    "sync_commits": {
                        "type": "boolean",
                        "default": True,
                        "description": "Auto-sync commits from repository"
                    },
                    "sync_pull_requests": {
                        "type": "boolean",
                        "default": True,
                        "description": "Auto-sync pull requests from repository"
                    },
                    "auto_link_commits": {
                        "type": "boolean",
                        "default": True,
                        "description": "Auto-link commits to issues based on commit messages"
                    }
                },
                "required": ["project", "repository_url", "access_token"]
            }
        },
        responses={
            201: {
                "description": "GitHub integration created successfully",
                "content": {
                    "application/json": {
                        "example": {
                            "id": "uuid-of-integration",
                            "project": "uuid-of-project",
                            "repository_url": "https://github.com/Victoroide/ficct-scrum-backend",
                            "repository_owner": "Victoroide",
                            "repository_name": "ficct-scrum-backend",
                            "repository_full_name": "Victoroide/ficct-scrum-backend",
                            "is_active": True,
                            "connected_at": "2025-11-02T15:30:00Z"
                        }
                    }
                }
            },
            400: {
                "description": "Bad Request - Missing required fields",
                "content": {
                    "application/json": {
                        "examples": {
                            "missing_project": {
                                "value": {
                                    "project": ["Field 'project' is required to create GitHub integration"]
                                }
                            },
                            "missing_token": {
                                "value": {
                                    "access_token": ["Field 'access_token' is required to create GitHub integration. Use OAuth flow (/oauth/initiate/) for automatic token handling."]
                                }
                            },
                            "invalid_url": {
                                "value": {
                                    "repository_url": ["Repository URL must be a valid GitHub repository URL"]
                                }
                            }
                        }
                    }
                }
            },
            403: {
                "description": "Forbidden - Insufficient permissions",
                "content": {
                    "application/json": {
                        "examples": {
                            "missing_project_field": {
                                "value": {
                                    "detail": "Missing required field 'project'. Please provide project ID in request body."
                                }
                            },
                            "no_permission": {
                                "value": {
                                    "detail": "You do not have permission to manage integrations for this project. Required role: Project owner/admin, Workspace admin, or Organization owner/admin."
                                }
                            }
                        }
                    }
                }
            },
            404: {
                "description": "Project not found",
                "content": {
                    "application/json": {
                        "example": {
                            "detail": "Project with ID 'xxx' does not exist."
                        }
                    }
                }
            }
        }
    ),
    destroy=extend_schema(
        summary="Disconnect GitHub repository", 
        tags=["Integrations"],
        description="Removes GitHub integration from project. Commits and PRs are preserved but no longer synced."
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
        tags=["Integrations"],
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
        tags=["Integrations"],
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
        tags=["Integrations"],
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
        tags=["Integrations"],
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
        tags=["Integrations"],
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
        tags=["Integrations"],
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
            logger.warning("[OAuth Init] Missing project field")
            return Response(
                {"error": "project field is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate secure random state for CSRF protection
        state = secrets.token_urlsafe(32)

        # Store state in Redis cache with 10-minute TTL for validation
        cache_key = f"github_oauth_state_{state}"
        cache_data = {
            "project_id": project_id,
            "user_id": str(request.user.id),
            "created_at": timezone.now().isoformat(),
            "redirect_uri": redirect_uri,
        }
        
        # TTL: 600 seconds (10 minutes) - generous timeout for user authorization
        cache.set(cache_key, cache_data, timeout=600)
        
        logger.info(
            f"[OAuth Init] State generated: {state[:10]}... for project {project_id}, "
            f"user {request.user.email}, TTL: 600s"
        )
        logger.debug(f"[OAuth Init] Cache key: {cache_key}")
        logger.debug(f"[OAuth Init] Stored data: {cache_data}")

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
        tags=["Integrations"],
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

        logger.info(f"[OAuth Callback] Received callback with state: {state[:10] if state else 'None'}...")

        if not code or not state:
            logger.error("[OAuth Callback] Missing code or state parameter")
            return Response(
                {"status": "error", "error": "Missing code or state parameter"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate state from Redis cache (CSRF protection)
        cache_key = f"github_oauth_state_{state}"
        logger.debug(f"[OAuth Callback] Looking up cache key: {cache_key}")
        
        stored_data = cache.get(cache_key)
        
        if not stored_data:
            logger.error(
                f"[OAuth Callback] State not found in cache or expired. "
                f"State: {state[:10]}..., Cache key: {cache_key}"
            )
            return Response(
                {
                    "status": "error",
                    "error": "Invalid or expired state parameter. Please restart the OAuth flow.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        logger.info(f"[OAuth Callback] State validated successfully from cache")
        logger.debug(f"[OAuth Callback] Retrieved data: {stored_data}")

        # Validate state age (extra security - should not exceed 15 minutes)
        try:
            created_at = timezone.datetime.fromisoformat(stored_data["created_at"])
            if timezone.now() - created_at > timedelta(minutes=15):
                cache.delete(cache_key)
                logger.warning(
                    f"[OAuth Callback] State expired (older than 15 minutes). "
                    f"Created: {created_at}"
                )
                return Response(
                    {"status": "error", "error": "State expired. Please restart the OAuth flow."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except (KeyError, ValueError) as e:
            logger.error(f"[OAuth Callback] Error parsing created_at: {e}")

        # Extract data from cache
        project_id = stored_data.get("project_id")
        user_id = stored_data.get("user_id")

        if not project_id or not user_id:
            logger.error(
                f"[OAuth Callback] Missing project_id or user_id in cached data. "
                f"Data: {stored_data}"
            )
            cache.delete(cache_key)
            return Response(
                {"status": "error", "error": "Invalid OAuth state data"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Delete state immediately to prevent reuse (security best practice)
        cache.delete(cache_key)
        logger.info(
            f"[OAuth Callback] State consumed and deleted. "
            f"Project: {project_id}, User: {user_id}"
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
                # Redirect to frontend with error
                frontend_url = settings.FRONTEND_URL
                error_url = f"{frontend_url}/projects/{project_id}/settings/integrations?github=error&message=no_token"
                return redirect(error_url)

            # Store access_token temporarily in Redis for repository selection
            # Generate a temporary token ID
            import secrets
            temp_token_id = secrets.token_urlsafe(32)
            temp_cache_key = f"github_temp_token_{temp_token_id}"
            
            temp_token_data = {
                "access_token": access_token,
                "project_id": project_id,
                "user_id": user_id,
                "created_at": timezone.now().isoformat(),
            }
            
            # Store with 5-minute TTL (enough time to select repository)
            cache.set(temp_cache_key, temp_token_data, timeout=300)
            
            logger.info(
                f"[OAuth Callback] Access token stored temporarily. "
                f"Temp ID: {temp_token_id[:10]}..., Project: {project_id}, User: {user_id}"
            )

            # Redirect to frontend repository selection page
            frontend_url = settings.FRONTEND_URL
            redirect_url = f"{frontend_url}/projects/{project_id}/settings/integrations?github=select&token={temp_token_id}"
            
            logger.info(f"[OAuth Callback] Redirecting to frontend: {redirect_url}")
            return redirect(redirect_url)

        except Exception as e:
            logger.exception(
                f"[OAuth Callback] Unexpected error during OAuth callback: {str(e)}"
            )
            # Redirect to frontend with error
            frontend_url = settings.FRONTEND_URL
            error_url = f"{frontend_url}/projects/{project_id}/settings/integrations?github=error&message=server_error"
            return redirect(error_url)

    @extend_schema(
        summary="List user's GitHub repositories",
        tags=["Integrations"],
        parameters=[
            {
                "name": "temp_token",
                "in": "query",
                "required": True,
                "schema": {"type": "string"},
                "description": "Temporary token ID from OAuth callback redirect",
            }
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "repositories": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "name": {"type": "string"},
                                "full_name": {"type": "string"},
                                "html_url": {"type": "string"},
                                "description": {"type": "string"},
                                "private": {"type": "boolean"},
                                "default_branch": {"type": "string"},
                            },
                        },
                    },
                    "project_id": {"type": "string"},
                },
            },
            400: {
                "type": "object",
                "properties": {
                    "error": {"type": "string"},
                },
            },
        },
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="oauth/repositories",
        permission_classes=[IsAuthenticated],
    )
    def list_repositories(self, request):
        """
        List user's accessible GitHub repositories using temporary OAuth token.
        Called by frontend after OAuth callback redirect.
        """
        temp_token = request.query_params.get("temp_token")
        
        if not temp_token:
            logger.error("[List Repos] Missing temp_token parameter")
            return Response(
                {"error": "Missing temp_token parameter"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Retrieve temporary token data from cache
        temp_cache_key = f"github_temp_token_{temp_token}"
        temp_token_data = cache.get(temp_cache_key)
        
        if not temp_token_data:
            logger.error(f"[List Repos] Temp token not found or expired: {temp_token[:10]}...")
            return Response(
                {"error": "Temporary token expired or invalid. Please restart OAuth flow."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        access_token = temp_token_data.get("access_token")
        project_id = temp_token_data.get("project_id")
        user_id = temp_token_data.get("user_id")
        
        # Verify the requesting user is the same as the one who initiated OAuth
        if str(request.user.id) != str(user_id):
            logger.warning(
                f"[List Repos] User mismatch. Expected: {user_id}, Got: {request.user.id}"
            )
            return Response(
                {"error": "Unauthorized. Token belongs to different user."},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        try:
            # Get user's repositories from GitHub
            from github import Github
            
            gh = Github(access_token)
            user = gh.get_user()
            
            # Get all accessible repositories
            repos_data = []
            for repo in user.get_repos():
                repos_data.append({
                    "id": repo.id,
                    "name": repo.name,
                    "full_name": repo.full_name,
                    "html_url": repo.html_url,
                    "description": repo.description or "",
                    "private": repo.private,
                    "default_branch": repo.default_branch,
                })
            
            logger.info(
                f"[List Repos] Retrieved {len(repos_data)} repositories for user {user_id}"
            )
            
            return Response(
                {
                    "repositories": repos_data,
                    "project_id": project_id,
                },
                status=status.HTTP_200_OK,
            )
        
        except Exception as e:
            logger.exception(f"[List Repos] Error fetching repositories: {str(e)}")
            return Response(
                {"error": f"Failed to fetch repositories: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Complete GitHub OAuth integration with selected repository",
        tags=["Integrations"],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "temp_token": {"type": "string"},
                    "repository_url": {"type": "string"},
                    "repository_name": {"type": "string"},
                },
                "required": ["temp_token", "repository_url", "repository_name"],
            }
        },
        responses={
            201: {
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
                    "error": {"type": "string"},
                },
            },
        },
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="oauth/complete",
        permission_classes=[IsAuthenticated],
    )
    def complete_integration(self, request):
        """
        Complete GitHub integration by creating GitHubIntegration with selected repository.
        Called by frontend after user selects a repository.
        """
        temp_token = request.data.get("temp_token")
        repository_url = request.data.get("repository_url")
        repository_name = request.data.get("repository_name")
        
        if not temp_token or not repository_url or not repository_name:
            logger.error("[Complete Integration] Missing required fields")
            return Response(
                {"error": "Missing required fields: temp_token, repository_url, repository_name"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Retrieve and delete temporary token from cache (one-time use)
        temp_cache_key = f"github_temp_token_{temp_token}"
        temp_token_data = cache.get(temp_cache_key)
        
        if not temp_token_data:
            logger.error(f"[Complete Integration] Temp token not found: {temp_token[:10]}...")
            return Response(
                {"error": "Temporary token expired or invalid. Please restart OAuth flow."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Delete token immediately (one-time use)
        cache.delete(temp_cache_key)
        
        access_token = temp_token_data.get("access_token")
        project_id = temp_token_data.get("project_id")
        user_id = temp_token_data.get("user_id")
        
        # Verify the requesting user is the same as the one who initiated OAuth
        if str(request.user.id) != str(user_id):
            logger.warning(
                f"[Complete Integration] User mismatch. Expected: {user_id}, Got: {request.user.id}"
            )
            return Response(
                {"error": "Unauthorized. Token belongs to different user."},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        try:
            # Create GitHubIntegration
            from apps.projects.models import Project
            
            project = Project.objects.get(id=project_id)
            
            integration = GitHubIntegration.objects.create(
                project=project,
                repository_url=repository_url,
                repository_name=repository_name,
                is_active=True,
            )
            
            # Set encrypted access token
            integration.set_access_token(access_token)
            integration.save()
            
            logger.info(
                f"[Complete Integration] Integration created successfully. "
                f"ID: {integration.id}, Repo: {repository_name}, Project: {project_id}"
            )
            
            return Response(
                {
                    "status": "success",
                    "message": "GitHub connected successfully",
                    "integration_id": str(integration.id),
                    "repository": repository_name,
                },
                status=status.HTTP_201_CREATED,
            )
        
        except Exception as e:
            logger.exception(f"[Complete Integration] Error creating integration: {str(e)}")
            return Response(
                {"error": f"Failed to create integration: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
