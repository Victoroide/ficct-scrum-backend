"""
Query Router for Intelligent Intent Classification.

Analyzes user queries to determine intent and routing strategy
for multi-namespace search.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class QueryRouter:
    """
    Intelligent query router for semantic search.

    Classifies query intent and determines:
    - Which namespaces to search
    - What metadata filters to apply
    - How to aggregate results
    """

    PRIORITY_KEYWORDS = [
        "priority",
        "critical",
        "urgent",
        "high",
        "low",
        "p1",
        "p2",
        "p3",
        "p4",
        "importante",
        "urgente",
        "critico",
    ]

    MEMBER_KEYWORDS = [
        "who",
        "assignee",
        "assigned",
        "working on",
        "doing",  # "What is X doing?"
        "member",
        "team",
        "activity",
        "tasks",
        "quien",
        "asignado",
        "trabajando",
        "haciendo",  # Spanish "doing"
        "miembro",
        "equipo",
        "actividad",
        "tareas",
    ]

    SPRINT_KEYWORDS = [
        "sprint",
        "iteration",
        "current",
        "active",
        "this week",
        "this month",
        "iteracion",
        "actual",
        "activo",
        "esta semana",
        "este mes",
    ]

    STATUS_KEYWORDS = [
        "status",
        "done",
        "completed",
        "in progress",
        "todo",
        "backlog",
        "estado",
        "hecho",
        "completado",
        "en progreso",
        "pendiente",
    ]

    TEMPORAL_KEYWORDS = [
        "recent",
        "recently",
        "latest",
        "last",
        "today",
        "yesterday",
        "reciente",
        "ultimo",
        "hoy",
        "ayer",
        "recientemente",
    ]

    def classify_query_intent(self, query: str) -> str:
        """
        Classify query intent based on keyword patterns.

        Args:
            query: User's natural language query

        Returns:
            Intent type: priority_query, member_query, sprint_query, status_query,
                        temporal_query, or general_query
        """
        query_lower = query.lower()

        # Priority query detection
        if any(keyword in query_lower for keyword in self.PRIORITY_KEYWORDS):
            logger.info(f"[ROUTER] Classified as priority_query: '{query}'")
            return "priority_query"

        # Check for person names FIRST (both full names and single names)
        # Full name pattern: "Victor Cuellar", "John Doe"
        full_name_pattern = r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b"
        if re.search(full_name_pattern, query):
            logger.info(
                f"[ROUTER] Detected full person name, classified as "
                f"member_query: '{query}'"
            )
            return "member_query"

        # Single capitalized name pattern: "Sebastian", "Victor", "Maria"
        # Check for capitalized word that's not at sentence start and is likely a name
        single_name_pattern = r"(?<!^)(?<!\. )\b[A-Z][a-z]{2,}\b"
        single_names = re.findall(single_name_pattern, query)
        # Filter out common words that shouldn't be names
        common_words = {
            "What",
            "Who",
            "How",
            "Where",
            "When",
            "Why",
            "Which",
            "This",
            "That",
            "These",
            "Those",
            "The",
            "Sprint",
            "Project",
        }
        potential_names = [name for name in single_names if name not in common_words]
        if potential_names:
            logger.info(
                f"[ROUTER] Detected single name(s) {potential_names}, "
                f"classified as member_query: '{query}'"
            )
            return "member_query"

        # Member query detection by keywords
        if any(keyword in query_lower for keyword in self.MEMBER_KEYWORDS):
            logger.info(f"[ROUTER] Classified as member_query by keyword: '{query}'")
            return "member_query"

        # Sprint query detection
        if any(keyword in query_lower for keyword in self.SPRINT_KEYWORDS):
            logger.info(f"[ROUTER] Classified as sprint_query: '{query}'")
            return "sprint_query"

        # Status query detection
        if any(keyword in query_lower for keyword in self.STATUS_KEYWORDS):
            logger.info(f"[ROUTER] Classified as status_query: '{query}'")
            return "status_query"

        # Temporal query detection
        if any(keyword in query_lower for keyword in self.TEMPORAL_KEYWORDS):
            logger.info(f"[ROUTER] Classified as temporal_query: '{query}'")
            return "temporal_query"

        logger.info(f"[ROUTER] Classified as general_query: '{query}'")
        return "general_query"

    def build_search_strategy(
        self, query: str, project_id: Optional[str] = None, intent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build comprehensive search strategy based on query intent.

        Args:
            query: User's query
            project_id: Optional project filter
            intent: Pre-classified intent (or will classify)

        Returns:
            Search strategy dictionary with namespaces, filters, and config
        """
        if not intent:
            intent = self.classify_query_intent(query)

        query_lower = query.lower()

        if intent == "priority_query":
            return self._build_priority_strategy(query_lower, project_id)

        elif intent == "member_query":
            return self._build_member_strategy(query, query_lower, project_id)

        elif intent == "sprint_query":
            return self._build_sprint_strategy(query_lower, project_id)

        elif intent == "status_query":
            return self._build_status_strategy(query_lower, project_id)

        elif intent == "temporal_query":
            return self._build_temporal_strategy(query_lower, project_id)

        else:
            return self._build_general_strategy(project_id)

    def _build_priority_strategy(
        self, query_lower: str, project_id: Optional[str]
    ) -> Dict:
        """Build search strategy for priority-based queries."""

        # Detect priority level
        priority_filters = []
        if any(
            word in query_lower
            for word in ["critical", "urgent", "p1", "critico", "urgente"]
        ):
            priority_filters = ["P1", "P2"]
        elif "high" in query_lower or "alto" in query_lower:
            priority_filters = ["P2"]
        elif "low" in query_lower or "bajo" in query_lower:
            priority_filters = ["P4"]
        elif any(word in query_lower for word in ["medium", "medio"]):
            priority_filters = ["P3"]

        filters = {}
        if project_id:
            filters["project_id"] = project_id
        if priority_filters:
            # Pinecone filter syntax: {"$in": [...]}
            filters["priority"] = {"$in": priority_filters}

        logger.debug(f"[ROUTER] Priority strategy: filters={filters}")

        return {
            "intent": "priority_query",
            "namespaces": ["issues"],
            "filters": filters,
            "top_k": 10,
            "description": (
                f"Searching for issues with priority "
                f"{priority_filters if priority_filters else 'any'}"
            ),
        }

    def _build_member_strategy(
        self, query: str, query_lower: str, project_id: Optional[str]
    ) -> Dict:
        """Build search strategy for team member queries."""

        # Extract person names from query (both full and single names)
        names = []

        # Full names: "Victor Cuellar", "John Doe"
        full_name_pattern = r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b"
        full_names = re.findall(full_name_pattern, query)
        names.extend(full_names)

        # Single names: "Sebastian", "Victor", "Maria"
        single_name_pattern = r"(?<!^)(?<!\.\s)\b[A-Z][a-z]{2,}\b"
        single_names = re.findall(single_name_pattern, query)
        # Filter out common words
        common_words = {
            "What",
            "Who",
            "How",
            "Where",
            "When",
            "Why",
            "Which",
            "This",
            "That",
            "These",
            "Those",
            "The",
            "Sprint",
            "Project",
        }
        single_names = [name for name in single_names if name not in common_words]
        names.extend(single_names)

        # Remove duplicates
        names = list(set(names))

        filters = {}
        if project_id:
            filters["project_id"] = project_id

        # Multi-namespace search: team_members + issues + sprints
        # Include sprints to see what sprint the person is working on
        namespaces = ["team_members", "issues", "sprints"]

        logger.debug(
            f"[ROUTER] Member strategy: names={names}, namespaces={namespaces}"
        )

        return {
            "intent": "member_query",
            "namespaces": namespaces,
            "filters": filters,
            "member_names": names,  # Will use for filtering results
            "top_k": 10,
            "description": (
                f"Searching for team member activity"
                f"{' for ' + ', '.join(names) if names else ''}"
            ),
        }

    def _build_sprint_strategy(
        self, query_lower: str, project_id: Optional[str]
    ) -> Dict:
        """Build search strategy for sprint-based queries."""

        filters = {}
        if project_id:
            filters["project_id"] = project_id

        # Check if looking for current/active sprint
        if any(
            word in query_lower
            for word in ["current", "active", "this", "actual", "activo"]
        ):
            filters["status"] = "active"

        # Multi-namespace: sprints + issues in sprint
        namespaces = ["sprints", "issues"]

        logger.debug(
            f"[ROUTER] Sprint strategy: filters={filters}, namespaces={namespaces}"
        )

        return {
            "intent": "sprint_query",
            "namespaces": namespaces,
            "filters": filters,
            "top_k": 10,
            "description": "Searching for sprint context and related issues",
        }

    def _build_status_strategy(
        self, query_lower: str, project_id: Optional[str]
    ) -> Dict:
        """Build search strategy for status-based queries."""

        filters = {}
        if project_id:
            filters["project_id"] = project_id

        # Detect status category
        if any(
            word in query_lower for word in ["done", "completed", "hecho", "completado"]
        ):
            filters["status_category"] = "done"
        elif any(
            word in query_lower
            for word in ["in progress", "working", "en progreso", "trabajando"]
        ):
            filters["status_category"] = "in_progress"
        elif any(word in query_lower for word in ["todo", "pending", "pendiente"]):
            filters["status_category"] = "todo"

        logger.debug(f"[ROUTER] Status strategy: filters={filters}")

        return {
            "intent": "status_query",
            "namespaces": ["issues"],
            "filters": filters,
            "top_k": 10,
            "description": "Searching for issues by status",
        }

    def _build_temporal_strategy(
        self, query_lower: str, project_id: Optional[str]
    ) -> Dict:
        """Build search strategy for temporal queries (recent, latest)."""

        filters = {}
        if project_id:
            filters["project_id"] = project_id

        # Calculate time threshold
        now = datetime.now()
        if "today" in query_lower or "hoy" in query_lower:
            threshold = now - timedelta(days=1)
        elif "yesterday" in query_lower or "ayer" in query_lower:
            threshold = now - timedelta(days=2)
        elif "recent" in query_lower or "reciente" in query_lower:
            threshold = now - timedelta(days=7)
        elif "latest" in query_lower or "ultimo" in query_lower:
            threshold = now - timedelta(days=7)
        else:
            threshold = now - timedelta(days=14)

        # Pinecone filter for updated_at >= threshold
        filters["updated_at"] = {"$gte": threshold.isoformat()}

        logger.debug(
            f"[ROUTER] Temporal strategy: threshold={threshold}, filters={filters}"
        )

        return {
            "intent": "temporal_query",
            "namespaces": ["issues"],
            "filters": filters,
            "top_k": 10,
            "description": (
                f"Searching for recently updated issues " f"(since {threshold.date()})"
            ),
        }

    def _build_general_strategy(self, project_id: Optional[str]) -> Dict:
        """Build general search strategy."""

        filters = {}
        if project_id:
            filters["project_id"] = project_id

        return {
            "intent": "general_query",
            "namespaces": ["issues", "project_context"],
            "filters": filters,
            "top_k": 10,
            "description": "General semantic search across issues and project context",
        }
