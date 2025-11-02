"""
AI Assistant ViewSets for RAG and intelligent features.

Provides REST API endpoints for semantic search, Q&A, and summarization.
"""

import logging
from functools import wraps

from drf_spectacular.utils import extend_schema
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
        success = self.rag_service.index_issue(issue_id=pk, force_reindex=force_reindex)

        if success:
            return Response(
                {"message": "Issue indexed successfully", "issue_id": pk},
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {"error": "Failed to index issue"},
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
        description="Find issues similar to a given issue for duplicate detection",
    )
    @action(detail=True, methods=["get"], url_path="similar-issues")
    @handle_ai_service_unavailable
    def similar_issues(self, request, pk=None):
        """Find similar issues."""
        top_k = int(request.query_params.get("top_k", 5))
        same_project_only = request.query_params.get("same_project_only", "true").lower() == "true"

        similar = self.rag_service.find_similar_issues(
            issue_id=pk, top_k=top_k, same_project_only=same_project_only
        )

        return Response({"similar_issues": similar}, status=status.HTTP_200_OK)

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
