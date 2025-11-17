"""
AI Assistant service for answering questions using RAG.

Combines semantic search with Azure OpenAI chat completion.
"""

import logging
from typing import Any, Dict, List, Optional

from base.services.llm_proxy import get_llm_proxy

from .query_router import QueryRouter
from .rag_service import RAGService

logger = logging.getLogger(__name__)


class AssistantService:
    """Service for AI assistant question answering."""

    def __init__(self):
        """Initialize assistant with RAG, LLM proxy, and query router."""
        self.available = False
        self.error_message = None

        try:
            self.llm_proxy = get_llm_proxy()  # LLM proxy for chat
            self.rag = RAGService()  # RAG keeps Azure for embeddings
            self.query_router = QueryRouter()  # Intelligent query routing
            self.available = self.rag.available  # Inherit RAG availability
            self.error_message = self.rag.error_message
        except Exception as e:
            self.error_message = f"Failed to initialize Assistant service: {str(e)}"
            logger.error(f"AssistantService initialization failed: {e}")

    def _check_available(self):
        """Check if service is available, raise exception if not."""
        if not self.available:
            from apps.ai_assistant.exceptions import ServiceUnavailable

            raise ServiceUnavailable(
                detail=self.error_message or "Assistant service is not available"
            )

    def answer_question(
        self,
        question: str,
        project_id: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Answer user question using RAG.

        Args:
            question: User's question
            project_id: Optional project context
            conversation_history: Previous conversation messages

        Returns:
            Dictionary with answer, sources, and confidence
        """
        self._check_available()
        try:
            # Step 1: Classify query intent and build search strategy
            logger.info(f"Assistant query: '{question}'")
            intent = self.query_router.classify_query_intent(question)
            strategy = self.query_router.build_search_strategy(
                query=question, project_id=project_id, intent=intent
            )

            logger.info(f"Query strategy: {strategy['description']}")

            # Step 2: Execute intelligent semantic search
            relevant_issues = self.rag.semantic_search(
                query=question,
                project_id=project_id,
                top_k=strategy["top_k"],
                filters=strategy.get("filters", {}),
            )

            # Step 3: Build enhanced context from retrieved issues
            context = self._build_context(relevant_issues, strategy)

            # Step 3: Construct prompt with context
            messages = self._build_messages(question, context, conversation_history)

            # Step 4: Get response from LLM proxy (Llama 4 → Azure fallback)
            response = self.llm_proxy.generate(
                messages=messages,
                task_type="answer_question",
                temperature=0.7,
                max_tokens=16000,  # High budget to prevent empty responses
                reasoning_effort="low",  # For Azure o-series fallback
                fallback_enabled=True,
            )

            logger.info(
                f"[ASSISTANT] Answer generated with {response.provider}/"
                f"{response.model}, cost=${response.cost_usd:.4f}"
            )

            # Step 5: Prepare response with sources
            return {
                "answer": response.content,
                "sources": [
                    {
                        "issue_id": issue["issue_id"],
                        "title": issue["title"],
                        "project_key": issue["project_key"],
                        "similarity": issue["similarity_score"],
                    }
                    for issue in relevant_issues[:3]
                ],
                "confidence": self._calculate_confidence(relevant_issues),
                "tokens_used": response.total_tokens,
                "provider": response.provider,
                "model": response.model,
                "cost_usd": response.cost_usd,
            }

        except Exception as e:
            logger.exception(f"Error answering question: {str(e)}")
            raise

    def suggest_solutions(
        self, issue_description: str, project_id: str
    ) -> Dict[str, Any]:
        """
        Suggest solutions based on similar past issues.

        Args:
            issue_description: Description of the problem
            project_id: Project context

        Returns:
            Suggested approaches with historical references
        """
        try:
            # Find similar resolved issues
            similar_issues = self.rag.semantic_search(
                query=issue_description,
                project_id=project_id,
                top_k=10,
                filters={"status": "Done"},  # Only completed issues
            )

            if not similar_issues:
                return {
                    "suggestions": [],
                    "message": "No similar historical issues found.",
                }

            # Build prompt for solution extraction
            context = self._build_context(similar_issues)

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an expert software development assistant. "
                        "Based on similar past issues and their resolutions, "
                        "suggest actionable approaches to solve the current problem."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Current issue: {issue_description}\n\n"
                        f"Similar resolved issues:\n{context}\n\n"
                        "Provide 2-3 suggested approaches to solve this issue."
                    ),
                },
            ]

            # Use LLM proxy for solution suggestions
            response = self.llm_proxy.generate(
                messages=messages,
                task_type="suggest_solutions",
                temperature=0.5,
                max_tokens=16000,
                reasoning_effort="low",  # For Azure fallback
                fallback_enabled=True,
            )

            logger.info(
                f"[ASSISTANT] Solutions suggested with {response.provider}/"
                f"{response.model}, cost=${response.cost_usd:.4f}"
            )

            return {
                "suggestions": response.content,
                "similar_issues": similar_issues[:5],
                "confidence": self._calculate_confidence(similar_issues),
                "provider": response.provider,
                "model": response.model,
                "cost_usd": response.cost_usd,
            }

        except Exception as e:
            logger.exception(f"Error suggesting solutions: {str(e)}")
            raise

    def _build_context(self, issues: List[Dict[str, Any]]) -> str:
        """Build context string from retrieved issues."""
        if not issues:
            return "No relevant issues found."

        context_parts = []
        for i, issue in enumerate(issues[:5], 1):
            context_parts.append(
                f"{i}. [{issue['project_key']}] {issue['title']}\n"
                f"   Type: {issue['issue_type']} | Status: {issue['status']}\n"
                f"   Description: {issue.get('description', 'N/A')[:200]}\n"
            )

        return "\n".join(context_parts)

    def _build_messages(
        self,
        question: str,
        context: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, str]]:
        """Build message list for chat completion."""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful project management assistant for FICCT-SCRUM. "
                    "Answer questions based on the provided context about project"
                    " issues. Be concise, accurate, and cite specific issues when"
                    " relevant. If you don't know the answer based on the context,"
                    " say so."
                ),
            },
        ]

        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history[-5:])  # Last 5 messages

        # Add current question with context
        messages.append(
            {
                "role": "user",
                "content": f"Context (relevant issues):\n{context}\n\n"
                f"Question: {question}",
            }
        )

        return messages

    def _calculate_confidence(self, issues: List[Dict[str, Any]]) -> float:
        """Calculate confidence score based on similarity scores."""
        if not issues:
            return 0.0

        # Average of top 3 similarity scores
        top_scores = [issue["similarity_score"] for issue in issues[:3]]
        return round(sum(top_scores) / len(top_scores), 2)
