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

            # Step 2: Execute multi-namespace search using strategy
            namespaces = strategy.get("namespaces", ["issues"])

            logger.info(f"[ASSISTANT] Searching namespaces: {namespaces}")

            if len(namespaces) > 1:
                # Multi-namespace search for comprehensive context
                relevant_data = self.rag.multi_namespace_search(
                    query=question,
                    namespaces=namespaces,
                    project_id=project_id,
                    top_k_per_namespace=15,  # 15 per namespace for rich context
                    filters=strategy.get("filters", {}),
                )
            else:
                # Single namespace fallback to legacy semantic_search
                relevant_data = self.rag.semantic_search(
                    query=question,
                    project_id=project_id,
                    top_k=strategy["top_k"],
                    filters=strategy.get("filters", {}),
                )

            logger.info(f"[ASSISTANT] Retrieved {len(relevant_data)} total results")

            # Log data type distribution
            data_types = {}
            for item in relevant_data:
                item_type = item.get("type", "unknown")
                data_types[item_type] = data_types.get(item_type, 0) + 1
            logger.info(f"[ASSISTANT] Data types: {data_types}")

            # Step 3: Build enhanced context from ALL retrieved data
            context = self._build_context(relevant_data, strategy)

            # Log context to verify it's being built correctly
            context_preview = context[:500] if len(context) > 500 else context
            logger.info(
                f"[ASSISTANT] Context built ({len(context)} chars): "
                f"{context_preview}..."
            )

            # Step 3: Construct prompt with context
            messages = self._build_messages(question, context, conversation_history)
            total_chars = sum(len(m.get('content', '')) for m in messages)
            logger.info(
                f"[ASSISTANT] Prompt contains {len(messages)} messages, "
                f"total {total_chars} chars"
            )

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

            # Step 5: Prepare response with sources (all data types)
            sources = []
            for item in relevant_data[:5]:
                item_type = item.get("type", "unknown")

                if item_type == "team_member":
                    sources.append(
                        {
                            "type": "team_member",
                            "full_name": item["full_name"],
                            "username": item["username"],
                            "email": item["email"],
                            "similarity": item["similarity_score"],
                        }
                    )
                elif item_type == "sprint":
                    sources.append(
                        {
                            "type": "sprint",
                            "sprint_name": item["sprint_name"],
                            "status": item["status"],
                            "project_key": item["project_key"],
                            "similarity": item["similarity_score"],
                        }
                    )
                elif item_type == "project_context":
                    sources.append(
                        {
                            "type": "project_context",
                            "project_name": item["project_name"],
                            "project_key": item["project_key"],
                            "similarity": item["similarity_score"],
                        }
                    )
                else:  # issue
                    sources.append(
                        {
                            "type": "issue",
                            "issue_id": item.get("issue_id"),
                            "title": item.get("title"),
                            "project_key": item.get("project_key"),
                            "similarity": item["similarity_score"],
                        }
                    )

            return {
                "answer": response.content,
                "sources": sources,
                "confidence": self._calculate_confidence(relevant_data),
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

    def _build_context(
        self, data_items: List[Dict[str, Any]], strategy: Dict[str, Any] = None
    ) -> str:
        """
        Build comprehensive context from ALL data types.

        CRITICAL FIX: Handle team_members, sprints, issues, project_context
        instead of just issues.
        """
        if not data_items:
            return "No relevant information found."

        # Group by data type
        grouped = {
            "team_member": [],
            "sprint": [],
            "issue": [],
            "project_context": [],
        }

        for item in data_items:
            item_type = item.get(
                "type", "issue"
            )  # Default to issue for backward compat
            if item_type in grouped:
                grouped[item_type].append(item)

        context_parts = []

        # Team members context (CRITICAL for "Who is X" questions)
        if grouped["team_member"]:
            context_parts.append("## TEAM MEMBERS:")
            for member in grouped["team_member"][:5]:
                context_parts.append(
                    f"• {member['full_name']} (@{member['username']})\n"
                    f"  Email: {member['email']}\n"
                    f"  Assigned Issues: {member['assigned_issues_count']} "
                    f"({member['in_progress_issues_count']} in progress, "
                    f"{member['completed_issues_count']} completed)\n"
                    f"  Story Points: {member['total_story_points']}\n"
                )
            context_parts.append("")

        # Sprint context
        if grouped["sprint"]:
            context_parts.append("## SPRINTS:")
            for sprint in grouped["sprint"][:3]:
                completed = sprint['completed_points']
                committed = sprint['committed_points']
                context_parts.append(
                    f"• {sprint['sprint_name']} ({sprint['status']})\n"
                    f"  Goal: {sprint['sprint_goal'] or 'No goal set'}\n"
                    f"  Progress: {sprint['progress_percentage']}%\n"
                    f"  Points: {completed}/{committed}\n"
                    f"  Issues: {sprint['issue_count']} total\n"
                )
            context_parts.append("")

        # Project context
        if grouped["project_context"]:
            context_parts.append("## PROJECT OVERVIEW:")
            for proj in grouped["project_context"][:2]:
                desc = proj.get('description', 'No description')[:150]
                context_parts.append(
                    f"• {proj['project_name']} ({proj['project_key']})\n"
                    f"  Description: {desc}\n"
                    f"  Total Issues: {proj['total_issues']}\n"
                    f"  Team Size: {proj['team_size']}\n"
                )
            context_parts.append("")

        # Issues context
        if grouped["issue"]:
            context_parts.append("## ISSUES:")
            for i, issue in enumerate(grouped["issue"][:10], 1):
                assignee_info = (
                    f" | Assignee: {issue['assignee']}"
                    if issue.get('assignee') else ""
                )
                priority = issue.get('priority', 'N/A')
                context_parts.append(
                    f"{i}. [{issue['project_key']}] {issue['title']}\n"
                    f"   Type: {issue['issue_type']} | Status: "
                    f"{issue['status']} | Priority: {priority}{assignee_info}\n"
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
                "content": (
                    f"Context (relevant issues):\n{context}\n\n"
                    f"Question: {question}"
                ),
            }
        )

        return messages

    def _calculate_confidence(self, data_items: List[Dict[str, Any]]) -> float:
        """Calculate confidence score based on similarity scores."""
        if not data_items:
            return 0.0

        # Average of top 3 similarity scores (any data type)
        top_scores = [
            item["similarity_score"] for item in data_items[:3]
            if "similarity_score" in item
        ]
        if not top_scores:
            return 0.0
        return round(sum(top_scores) / len(top_scores), 2)
