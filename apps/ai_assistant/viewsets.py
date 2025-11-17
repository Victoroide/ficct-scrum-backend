"""
AI Assistant ViewSets for RAG and intelligent features.

Provides REST API endpoints for semantic search, Q&A, and summarization.
"""

import logging
import uuid
from functools import wraps

from django.core.exceptions import ValidationError

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.ai_assistant.exceptions import ServiceUnavailable
from apps.ai_assistant.services import (
    AssistantService,
    RAGService,
    SummarizationService,
)
from apps.projects.permissions import CanAccessProject

logger = logging.getLogger(__name__)


def handle_ai_service_unavailable(func):
    """Decorator to handle ServiceUnavailable exceptions from AI services."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ServiceUnavailable:
            # Re-raise to return proper 503 response
            raise
        except Exception as e:
            # Log and return 500 for other errors
            logger.exception(f"Error in {func.__name__}: {str(e)}")
            return Response(
                {"error": f"Failed to execute {func.__name__}."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    return wrapper


class AIAssistantViewSet(viewsets.ViewSet):
    """AI-powered features (RAG, search, summarization)."""

    permission_classes = [IsAuthenticated, CanAccessProject]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rag_service = None
        self._assistant_service = None
        self._summarization_service = None

    @property
    def rag_service(self):
        """Lazy load RAG service to avoid Windows readline import error."""
        if self._rag_service is None:
            self._rag_service = RAGService()
        return self._rag_service

    @property
    def assistant_service(self):
        """Lazy load Assistant service."""
        if self._assistant_service is None:
            self._assistant_service = AssistantService()
        return self._assistant_service

    @property
    def summarization_service(self):
        """Lazy load Summarization service."""
        if self._summarization_service is None:
            self._summarization_service = SummarizationService()
        return self._summarization_service

    @extend_schema(
        tags=["AI Assistant"],
        summary="Index issue in vector database",
        description="Index a single issue for semantic search",
    )
    @action(detail=True, methods=["post"], url_path="index-issue")
    @handle_ai_service_unavailable
    def index_issue(self, request, pk=None):
        """Index single issue in Pinecone."""
        force_reindex = request.data.get("force_reindex", False)
        success, error_msg = self.rag_service.index_issue(
            issue_id=pk, force_reindex=force_reindex
        )

        if success:
            return Response(
                {
                    "status": "success",
                    "message": "Issue indexed successfully",
                    "issue_id": pk,
                },
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {
                    "status": "error",
                    "error": error_msg or "Failed to index issue",
                    "issue_id": pk,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        tags=["AI Assistant"],
        summary="Batch index project issues",
        description="Index all issues in a project for semantic search",
    )
    @action(detail=True, methods=["post"], url_path="index-project")
    @handle_ai_service_unavailable
    def index_project(self, request, pk=None):
        """Batch index all issues in project."""
        batch_size = request.data.get("batch_size", 50)
        result = self.rag_service.index_project_issues(
            project_id=pk, batch_size=batch_size
        )

        return Response(result, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["AI Assistant"],
        summary="Semantic search for issues",
        description="Natural language search across indexed issues",
    )
    @action(detail=False, methods=["post"], url_path="search-issues")
    @handle_ai_service_unavailable
    def search_issues(self, request):
        """Semantic search across issues."""
        query = request.data.get("query")
        if not query:
            return Response(
                {"error": "Query is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project_id = request.data.get("project_id")
        top_k = request.data.get("top_k", 10)
        filters = request.data.get("filters", {})

        results = self.rag_service.semantic_search(
            query=query, project_id=project_id, top_k=top_k, filters=filters
        )

        return Response({"results": results}, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["AI Assistant"],
        summary="Find similar issues",
        description="Find issues similar to a given issue for duplicate detection using semantic search.",
        parameters=[
            OpenApiParameter(
                name="top_k",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Number of similar issues to return (default: 5, max: 20)",
            ),
            OpenApiParameter(
                name="same_project_only",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Limit results to same project only (default: true)",
            ),
        ],
        responses={
            200: OpenApiResponse(description="List of similar issues found"),
            400: OpenApiResponse(description="Invalid UUID format or parameters"),
            404: OpenApiResponse(description="Issue not found"),
            503: OpenApiResponse(description="AI service unavailable"),
        },
    )
    @action(detail=True, methods=["get"], url_path="similar-issues")
    @handle_ai_service_unavailable
    def similar_issues(self, request, pk=None):
        """
        Find similar issues using semantic search.

        Returns issues with similar content for duplicate detection.
        Requires Pinecone AI service to be available.
        """
        # Validate UUID format
        try:
            uuid.UUID(str(pk))
        except (ValueError, AttributeError, TypeError):
            return Response(
                {
                    "error": "Invalid issue ID format",
                    "detail": "Issue ID must be a valid UUID",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate and parse parameters
        try:
            top_k = int(request.query_params.get("top_k", 5))
            if top_k < 1 or top_k > 20:
                return Response(
                    {
                        "error": "Invalid top_k parameter",
                        "detail": "top_k must be between 1 and 20",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except (ValueError, TypeError):
            return Response(
                {
                    "error": "Invalid top_k parameter",
                    "detail": "top_k must be an integer",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        same_project_only = (
            request.query_params.get("same_project_only", "true").lower() == "true"
        )

        # Find similar issues
        similar = self.rag_service.find_similar_issues(
            issue_id=pk, top_k=top_k, same_project_only=same_project_only
        )

        # Check if issue exists
        if similar is None:
            return Response(
                {
                    "error": "Issue not found",
                    "detail": f"Issue with ID {pk} does not exist",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({"similar_issues": similar}, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["AI Assistant"],
        summary="Pinecone diagnostics",
        description="Get Pinecone index statistics and connection status for debugging",
        responses={
            200: OpenApiResponse(description="Pinecone diagnostics information"),
            503: OpenApiResponse(description="AI service unavailable"),
        },
    )
    @action(detail=False, methods=["get"], url_path="pinecone-diagnostics")
    @handle_ai_service_unavailable
    def pinecone_diagnostics(self, request):
        """
        Get Pinecone diagnostics information.

        Returns connection status, index stats, and embedding model info.
        Useful for debugging indexing issues.
        """
        try:
            import logging

            logger = logging.getLogger(__name__)

            diagnostics = {
                "status": "checking",
                "pinecone": {},
                "azure_openai": {},
                "errors": [],
            }

            # Test Pinecone connection
            try:
                logger.info("[DIAGNOSTICS] Testing Pinecone connection...")
                stats = self.rag_service.pinecone.get_index_stats()

                diagnostics["pinecone"] = {
                    "status": "connected",
                    "index_name": self.rag_service.pinecone.index_name,
                    "dimension": stats.get("dimension"),
                    "total_vectors": stats.get("total_vector_count"),
                    "index_fullness": stats.get("index_fullness"),
                    "namespaces": stats.get("namespaces", {}),
                    "environment": self.rag_service.pinecone.environment,
                    "metric": self.rag_service.pinecone.metric,
                }
                logger.info(
                    f"[DIAGNOSTICS] Pinecone connected: {stats.get('total_vector_count')} vectors"
                )
            except Exception as e:
                error_msg = f"Pinecone connection failed: {type(e).__name__}: {str(e)}"
                diagnostics["pinecone"]["status"] = "error"
                diagnostics["pinecone"]["error"] = str(e)
                diagnostics["errors"].append(error_msg)
                logger.error(f"[DIAGNOSTICS] {error_msg}")

            # Test Azure OpenAI
            try:
                logger.info(
                    "[DIAGNOSTICS] Testing Azure OpenAI embedding generation..."
                )
                test_text = "This is a test sentence for embedding generation."
                embedding = self.rag_service.openai.generate_embedding(test_text)

                diagnostics["azure_openai"] = {
                    "status": "connected",
                    "embedding_deployment": self.rag_service.openai.embedding_deployment,
                    "embedding_dimension": len(embedding),
                    "endpoint": self.rag_service.openai.endpoint,
                    "api_version": self.rag_service.openai.api_version,
                }
                logger.info(
                    f"[DIAGNOSTICS] Azure OpenAI connected: embedding dimension {len(embedding)}"
                )

                # Verify dimension matches Pinecone
                if diagnostics["pinecone"].get("dimension"):
                    if len(embedding) != diagnostics["pinecone"]["dimension"]:
                        error_msg = (
                            f"DIMENSION MISMATCH: Azure OpenAI returns {len(embedding)} dimensions "
                            f"but Pinecone expects {diagnostics['pinecone']['dimension']}"
                        )
                        diagnostics["errors"].append(error_msg)
                        logger.error(f"[DIAGNOSTICS] {error_msg}")

            except Exception as e:
                error_msg = f"Azure OpenAI test failed: {type(e).__name__}: {str(e)}"
                diagnostics["azure_openai"]["status"] = "error"
                diagnostics["azure_openai"]["error"] = str(e)
                diagnostics["errors"].append(error_msg)
                logger.error(f"[DIAGNOSTICS] {error_msg}")

            # Overall status
            if not diagnostics["errors"]:
                diagnostics["status"] = "healthy"
            else:
                diagnostics["status"] = "error"

            # Add recommendation if errors exist
            if diagnostics["errors"]:
                diagnostics["recommendations"] = [
                    "Check .env file for correct PINECONE_API_KEY and AZURE_OPENAI_API_KEY",
                    "Verify Pinecone index exists and dimension matches Azure OpenAI model",
                    "Check server logs for detailed error messages",
                    "Ensure Pinecone index dimension is 1536 for text-embedding-3-small model",
                ]

            logger.info(
                f"[DIAGNOSTICS] Complete: status={diagnostics['status']}, errors={len(diagnostics['errors'])}"
            )

            return Response(diagnostics, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"[DIAGNOSTICS] Critical error: {str(e)}")
            return Response(
                {
                    "status": "error",
                    "error": f"Diagnostics failed: {type(e).__name__}: {str(e)}",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        tags=["AI Assistant"],
        summary="AI assistant query",
        description="Ask questions about project data using RAG",
    )
    @action(detail=False, methods=["post"], url_path="query")
    @handle_ai_service_unavailable
    def assistant_query(self, request):
        """Answer question using RAG."""
        question = request.data.get("question")
        if not question:
            return Response(
                {"error": "Question is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project_id = request.data.get("project_id")
        conversation_history = request.data.get("conversation_history", [])

        response = self.assistant_service.answer_question(
            question=question,
            project_id=project_id,
            conversation_history=conversation_history,
        )

        return Response(response, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["AI Assistant"],
        summary="Full Pinecone Synchronization",
        description=(
            "⚠️ DESTRUCTIVE: Clears Pinecone 'issues' namespace and reindexes ALL active issues from DB. "
            "Use for initial setup or full resync after schema changes."
        ),
        request={
            "type": "object",
            "properties": {
                "clear_existing": {
                    "type": "boolean",
                    "default": True,
                    "description": "Clear existing vectors before sync (default: true)",
                }
            },
        },
    )
    @action(detail=False, methods=["post"], url_path="sync-all")
    @handle_ai_service_unavailable
    def sync_all_issues(self, request):
        """
        Full synchronization: Clear Pinecone and reindex ALL issues.

        This operation:
        1. Clears all vectors in 'issues' namespace
        2. Reindexes all active issues from all projects
        3. Updates IssueEmbedding records

        ⚠️ WARNING: This is a DESTRUCTIVE operation that clears existing data.
        """
        clear_existing = request.data.get("clear_existing", True)

        logger.warning(
            f"[SYNC-ALL] User {request.user.email} initiated full Pinecone sync "
            f"(clear_existing={clear_existing})"
        )

        result = self.rag_service.sync_all_issues(clear_existing=clear_existing)

        return Response(result, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["AI Assistant"],
        summary="Suggest solutions",
        description="Recommend solutions based on similar past issues",
    )
    @action(detail=False, methods=["post"], url_path="suggest-solutions")
    @handle_ai_service_unavailable
    def suggest_solutions(self, request):
        """Suggest solutions based on history."""
        issue_description = request.data.get("issue_description")
        project_id = request.data.get("project_id")

        if not all([issue_description, project_id]):
            return Response(
                {"error": "issue_description and project_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        suggestions = self.assistant_service.suggest_solutions(
            issue_description=issue_description, project_id=project_id
        )

        return Response(suggestions, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["AI Assistant"],
        summary="Summarize issue discussion",
        description="Generate summary of issue comments and discussion",
    )
    @action(detail=True, methods=["post"], url_path="summarize-issue")
    @handle_ai_service_unavailable
    def summarize_issue(self, request, pk=None):
        """Summarize issue discussion."""
        length = request.data.get("length", "medium")
        use_cache = request.data.get("use_cache", True)

        summary = self.summarization_service.summarize_issue_discussion(
            issue_id=pk, length=length, use_cache=use_cache
        )

        return Response(summary, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["AI Assistant"],
        summary="Summarize sprint retrospective",
        description="Generate sprint retrospective summary",
    )
    @action(detail=True, methods=["post"], url_path="summarize-sprint")
    @handle_ai_service_unavailable
    def summarize_sprint(self, request, pk=None):
        """Summarize sprint retrospective."""
        length = request.data.get("length", "medium")

        summary = self.summarization_service.summarize_sprint_retrospective(
            sprint_id=pk, length=length
        )

        return Response(summary, status=status.HTTP_200_OK)
