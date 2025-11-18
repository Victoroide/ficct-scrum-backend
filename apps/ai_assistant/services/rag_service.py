"""
RAG (Retrieval-Augmented Generation) service for semantic search.

Handles indexing issues in Pinecone and semantic search operations.
"""

import hashlib
import logging
from typing import Any, Dict, List, Optional

from django.utils import timezone

from apps.ai_assistant.models import IssueEmbedding
from apps.projects.models import Issue
from base.services import get_azure_openai_service, get_pinecone_service

logger = logging.getLogger(__name__)


class RAGService:
    """Service for RAG operations with Pinecone and Azure OpenAI."""

    def __init__(self):
        """Initialize RAG service with Azure OpenAI and Pinecone."""
        self.available = False
        self.error_message = None

        try:
            self.openai = get_azure_openai_service()
            self.pinecone = get_pinecone_service()
            self.available = True
        except ModuleNotFoundError as e:
            if "readline" in str(e):
                self.error_message = (
                    "RAG service unavailable on Windows. "
                    "Pinecone requires Unix/Linux environment or Docker. "
                    "Use Docker to access AI features."
                )
                logger.warning(f"RAGService unavailable: {self.error_message}")
            else:
                raise
        except Exception as e:
            self.error_message = f"Failed to initialize RAG service: {str(e)}"
            logger.error(f"RAGService initialization failed: {e}")

    def _check_available(self):
        """Check if service is available, raise exception if not."""
        if not self.available:
            from apps.ai_assistant.exceptions import ServiceUnavailable

            raise ServiceUnavailable(
                detail=self.error_message or "RAG service is not available"
            )

    def index_issue(
        self, issue_id: str, force_reindex: bool = False
    ) -> tuple[bool, str]:
        """
        Index a single issue in Pinecone.

        Args:
            issue_id: Issue UUID
            force_reindex: Force reindexing even if already indexed

        Returns:
            Tuple of (success: bool, error_message: str)
        """
        self._check_available()
        try:
            logger.info(f"[INDEX] Starting index for issue {issue_id}")
            issue = Issue.objects.select_related(
                "project", "issue_type", "status", "assignee", "reporter", "sprint"
            ).get(id=issue_id)

            logger.debug(f"[INDEX] Issue loaded: {issue.title}")

            # Prepare text for embedding
            text_content = self._prepare_issue_text(issue)
            content_hash = self._calculate_hash(text_content)
            logger.debug(f"[INDEX] Text prepared, length: {len(text_content)} chars")

            # Check if already indexed with same content
            existing_embedding = IssueEmbedding.objects.filter(
                issue_id=issue_id
            ).first()

            if existing_embedding and not force_reindex:
                if existing_embedding.content_hash == content_hash:
                    logger.debug(
                        f"[INDEX] Issue {issue_id} already indexed with same content, skipping"
                    )
                    return True, "Already indexed"

            # Generate embedding
            logger.info(f"[OPENAI] Generating embedding for issue {issue_id}...")
            embedding_vector = self.openai.generate_embedding(text_content)
            logger.info(
                f"[OPENAI] Embedding generated successfully, dimension: "
                f"{len(embedding_vector)}"
            )

            # Prepare metadata
            metadata = self._prepare_metadata(issue)
            logger.debug(f"[INDEX] Metadata prepared: {len(metadata)} fields")
            logger.debug(
                f"[INDEX] Metadata sample: assignee_id={
    metadata.get('assignee_id')}, reporter_id={
        metadata.get('reporter_id')}"
            )

            # Upsert to Pinecone
            vector_id = f"issue_{issue_id}"
            logger.info(f"[PINECONE] Upserting vector {vector_id}...")
            self.pinecone.upsert_vector(
                vector_id=vector_id,
                vector=embedding_vector,
                metadata=metadata,
                namespace="issues",
            )
            logger.info(f"[PINECONE] Upsert successful for {vector_id}")

            # Update or create embedding record
            IssueEmbedding.objects.update_or_create(
                issue_id=issue_id,
                defaults={
                    "vector_id": vector_id,
                    "project_id": issue.project_id,
                    "title": issue.title,
                    "content_hash": content_hash,
                    "is_indexed": True,
                    "indexed_at": timezone.now(),
                },
            )

            logger.info(f"[INDEX] Successfully indexed issue {issue_id}")
            return True, ""

        except Issue.DoesNotExist:
            error_msg = f"Issue {issue_id} not found in database"
            logger.error(f"[INDEX] ERROR: {error_msg}")
            return False, error_msg

        except Exception as e:
            error_type = type(e).__name__
            error_msg = f"{error_type}: {str(e)}"
            logger.exception(
                f"[INDEX] ERROR: Error indexing issue {issue_id}: {error_msg}"
            )
            return False, error_msg

    def index_project_issues(
        self, project_id: str, batch_size: int = 50
    ) -> Dict[str, Any]:
        """
        Index all issues in a project.

        Args:
            project_id: Project UUID
            batch_size: Number of issues to process per batch

        Returns:
            Dictionary with indexing statistics including error details
        """
        self._check_available()
        try:
            logger.info(f"[BATCH INDEX] Starting for project {project_id}")

            issues = Issue.objects.filter(
                project_id=project_id, is_active=True
            ).select_related("project", "issue_type", "status")

            total = issues.count()
            indexed = 0
            failed = 0
            errors = []  # Track individual errors

            logger.info(f"[BATCH INDEX] Found {total} active issues to index")

            for i, issue in enumerate(issues, 1):
                logger.debug(f"[BATCH INDEX] Processing issue {i}/{total}: {issue.id}")

                try:
                    success, error_msg = self.index_issue(str(issue.id))

                    if success:
                        indexed += 1
                        logger.debug(
                            f"[BATCH INDEX] Issue {i}/{total} indexed successfully"
                        )
                    else:
                        failed += 1
                        error_detail = {
                            "issue_id": str(issue.id),
                            "issue_title": issue.title,
                            "error": error_msg or "Unknown error",
                        }
                        errors.append(error_detail)
                        logger.warning(
                            f"[BATCH INDEX] FAILED: Issue {i}/{total} failed: {error_msg}"
                        )

                except Exception as e:
                    failed += 1
                    error_type = type(e).__name__
                    error_detail = {
                        "issue_id": str(issue.id),
                        "issue_title": issue.title,
                        "error": f"{error_type}: {str(e)}",
                    }
                    errors.append(error_detail)
                    logger.error(
                        f"[BATCH INDEX] EXCEPTION: Issue {i}/{total}: {error_type}: {
    str(e)}"
                    )

                if i % batch_size == 0:
                    logger.info(
                        f"[BATCH INDEX] Progress: {i}/{total} processed, {indexed} indexed, {failed} failed"
                    )

            success_rate = round((indexed / total * 100), 1) if total > 0 else 0

            logger.info(
                f"[BATCH INDEX] Complete: {indexed}/{total} indexed ({success_rate}%), "
                f"{failed} failed"
            )

            return {
                "total": total,
                "indexed": indexed,
                "failed": failed,
                "success_rate": success_rate,
                "errors": errors,  # Now includes detailed error information
            }

        except Exception as e:
            logger.exception(f"[BATCH INDEX] Critical error: {str(e)}")
            raise

    def sync_all_issues(self, clear_existing: bool = True) -> Dict[str, Any]:
        """
        Full synchronization: Clear Pinecone and reindex ALL active issues from DB.

        This is a DESTRUCTIVE operation that:
        1. Clears all vectors in the 'issues' namespace (if clear_existing=True)
        2. Reindexes ALL active issues from ALL projects
        3. Updates IssueEmbedding records in DB

        Args:
            clear_existing: Whether to clear existing vectors before sync (default: True)

        Returns:
            Dictionary with sync statistics:
            - projects_processed: Number of projects
            - total_issues: Total issues found
            - indexed: Successfully indexed
            - failed: Failed to index
            - errors: List of error details
            - duration_seconds: Time taken
        """
        self._check_available()
        import time

        from apps.projects.models import Project

        start_time = time.time()

        try:
            logger.warning("=" * 80)
            logger.warning("[FULL SYNC] Starting FULL Pinecone synchronization")
            logger.warning("=" * 80)

            # Step 1: Clear existing vectors if requested
            if clear_existing:
                logger.warning(
                    "[FULL SYNC] Step 1/3: Clearing existing vectors in 'issues' namespace"
                )
                self.pinecone.clear_namespace(namespace="issues")
                logger.info("[FULL SYNC] Namespace cleared")
            else:
                logger.info(
                    "[FULL SYNC] Skipping namespace clear (clear_existing=False)"
                )

            # Step 2: Get all active projects
            logger.info("[FULL SYNC] Step 2/3: Loading all active projects")
            projects = Project.objects.filter(is_active=True).values_list(
                "id", flat=True
            )
            project_count = len(projects)
            logger.info(f"[FULL SYNC] Found {project_count} active projects")

            # Step 3: Index all issues from all projects
            logger.info("[FULL SYNC] Step 3/3: Indexing all issues from all projects")

            total_issues = 0
            total_indexed = 0
            total_failed = 0
            all_errors = []

            for i, project_id in enumerate(projects, 1):
                logger.info(
                    f"[FULL SYNC] Processing project {i}/{project_count}: {project_id}"
                )

                try:
                    result = self.index_project_issues(
                        project_id=str(project_id), batch_size=50
                    )

                    total_issues += result["total"]
                    total_indexed += result["indexed"]
                    total_failed += result["failed"]

                    if result.get("errors"):
                        all_errors.extend(result["errors"])

                    logger.info(
                        f"[FULL SYNC] Project {i}/{project_count} complete: "
                        f"{result['indexed']}/{result['total']} indexed"
                    )

                except Exception as e:
                    logger.error(
                        f"[FULL SYNC] Failed to process project {project_id}: {str(e)}"
                    )
                    all_errors.append(
                        {
                            "project_id": str(project_id),
                            "error": f"Project indexing failed: {str(e)}",
                        }
                    )

            # Calculate stats
            duration = round(time.time() - start_time, 2)
            success_rate = (
                round((total_indexed / total_issues * 100), 1)
                if total_issues > 0
                else 0
            )

            logger.warning("=" * 80)
            logger.warning(
                f"[FULL SYNC] COMPLETE: {total_indexed}/{total_issues} issues indexed "
                f"({success_rate}%) in {duration}s"
            )
            logger.warning(
                f"[FULL SYNC] Projects: {project_count}, Failed issues: {total_failed}"
            )
            logger.warning("=" * 80)

            return {
                "status": "success",
                "projects_processed": project_count,
                "total_issues": total_issues,
                "indexed": total_indexed,
                "failed": total_failed,
                "success_rate": success_rate,
                "duration_seconds": duration,
                "errors": all_errors[:50],  # Limit to first 50 errors
                "total_errors": len(all_errors),
            }

        except Exception as e:
            duration = round(time.time() - start_time, 2)
            logger.exception(f"[FULL SYNC] CRITICAL ERROR after {duration}s: {str(e)}")
            raise

    def semantic_search(
        self,
        query: str,
        project_id: Optional[str] = None,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for issues using natural language query.

        ENHANCED: More robust search strategy:
        1. Query Pinecone with generous top_k (2x requested)
        2. Filter by project_id in Python (not Pinecone filter)
        3. Return top results after project filtering

        Args:
            query: Natural language search query
            project_id: Optional project filter
            top_k: Number of results to return
            filters: Additional metadata filters

        Returns:
            List of matching issues with scores
        """
        self._check_available()
        try:
            # Generate query embedding
            logger.info(f"[RAG] Semantic search: '{query}' (project={project_id})")
            query_vector = self.openai.generate_embedding(query)
            logger.debug(
                f"[RAG] Query embedding generated: {len(query_vector)} dimensions"
            )

            # Query Pinecone with generous top_k (filter in Python later)
            # This prevents empty results due to overly restrictive filters
            pinecone_top_k = top_k * 3  # Get 3x, filter later

            logger.info(
                f"[RAG] Querying Pinecone: namespace='issues', top_k={pinecone_top_k}"
            )

            # Query WITHOUT Pinecone filter (more robust)
            results = self.pinecone.query(
                vector=query_vector,
                top_k=pinecone_top_k,
                filter_dict=None,  # Don't filter at Pinecone level
                namespace="issues",
                include_metadata=True,
            )

            logger.info(f"[RAG] Pinecone returned {len(results)} raw results")

            # Filter by project_id in Python
            filtered_results = []
            for result in results:
                metadata = result.get("metadata", {})
                result_project_id = metadata.get("project_id")

                # Apply project filter
                if project_id and result_project_id != project_id:
                    logger.debug(
                        f"[RAG] Skipping result: project mismatch ({result_project_id} != {project_id})"
                    )
                    continue

                # Apply custom filters
                if filters:
                    match = all(metadata.get(k) == v for k, v in filters.items())
                    if not match:
                        continue

                filtered_results.append(result)

            logger.info(f"[RAG] After project filter: {len(filtered_results)} results")

            # Enrich results with full issue data
            enriched_results = []
            for result in filtered_results[:top_k]:  # Limit to requested top_k
                issue_id = result["metadata"].get("issue_id")
                if issue_id:
                    try:
                        issue = Issue.objects.select_related(
                            "issue_type", "status", "assignee", "project"
                        ).get(id=issue_id)

                        enriched_results.append(
                            {
                                "issue_id": str(issue.id),
                                "title": issue.title,
                                "description": issue.description,
                                "issue_type": issue.issue_type.name,
                                "status": issue.status.name,
                                "priority": issue.priority,
                                "assignee": issue.assignee.get_full_name()
                                if issue.assignee
                                else None,
                                "project_key": issue.project.key,
                                "similarity_score": round(result["score"], 3),
                                "metadata": result["metadata"],
                            }
                        )
                    except Issue.DoesNotExist:
                        logger.warning(f"[RAG] Issue {issue_id} not found in database")

            logger.info(
                f"[RAG] SUCCESS: Returning {len(enriched_results)} enriched results"
            )
            return enriched_results

        except Exception as e:
            logger.exception(f"[RAG] ERROR: Error in semantic search: {str(e)}")
            raise

    def find_similar_issues(
        self,
        issue_id: str,
        top_k: int = 5,
        same_project_only: bool = True,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Find issues similar to a given issue.

        Args:
            issue_id: Source issue UUID
            top_k: Number of similar issues to return
            same_project_only: Limit to same project

        Returns:
            List of similar issues with similarity scores, or None if issue not found
        """
        self._check_available()
        try:
            issue = Issue.objects.get(id=issue_id)

            # Check if issue is indexed
            embedding = IssueEmbedding.objects.filter(issue_id=issue_id).first()
            if not embedding or not embedding.is_indexed:
                # Index it first
                self.index_issue(issue_id)

            # Prepare filters
            filters = (
                {"project_id": str(issue.project_id)} if same_project_only else None
            )

            # Query for similar vectors
            vector_id = f"issue_{issue_id}"
            results = self.pinecone.query_by_id(
                vector_id=vector_id,
                top_k=top_k,
                filter_dict=filters,
                namespace="issues",
                include_metadata=True,
            )

            # Enrich results
            similar_issues = []
            for result in results:
                similar_id = result["metadata"].get("issue_id")
                if similar_id and similar_id != issue_id:
                    try:
                        similar_issue = Issue.objects.select_related(
                            "issue_type", "status", "project"
                        ).get(id=similar_id)

                        similar_issues.append(
                            {
                                "issue_id": str(similar_issue.id),
                                "title": similar_issue.title,
                                "issue_type": similar_issue.issue_type.name,
                                "status": similar_issue.status.name,
                                "project_key": similar_issue.project.key,
                                "similarity_score": round(result["score"], 3),
                            }
                        )
                    except Issue.DoesNotExist:
                        continue

            return similar_issues

        except Issue.DoesNotExist:
            logger.warning(f"Issue {issue_id} not found for similarity search")
            return None

        except Exception as e:
            logger.error(f"Error finding similar issues: {str(e)}")
            raise

    def delete_issue_embedding(self, issue_id: str) -> bool:
        """
        Remove issue from Pinecone index.

        Args:
            issue_id: Issue UUID

        Returns:
            True if successful
        """
        self._check_available()
        try:
            vector_id = f"issue_{issue_id}"
            self.pinecone.delete_vector(vector_id, namespace="issues")

            IssueEmbedding.objects.filter(issue_id=issue_id).delete()

            logger.info(f"Deleted embedding for issue {issue_id}")
            return True

        except Exception as e:
            logger.exception(f"Error deleting embedding: {str(e)}")
            return False

    def _prepare_issue_text(self, issue: Issue) -> str:
        """
        Prepare issue text for embedding generation.

        ENHANCED: Rich context for better semantic matching:
        - Title + Type + Status + Priority
        - Full description
        - Assignee and reporter names
        - Sprint context
        - Labels/tags

        More context = better semantic search results.
        """
        parts = [
            f"Issue: {issue.title}",
            f"Type: {issue.issue_type.name}",
            f"Status: {issue.status.name}",
            f"Priority: {issue.priority or 'Medium'}",
        ]

        # Add full description (critical for semantic matching)
        if issue.description:
            parts.append(f"Description: {issue.description}")

        # Add assignee context
        if issue.assignee:
            parts.append(f"Assigned to: {issue.assignee.get_full_name()}")

        # Add reporter context
        if issue.reporter:
            parts.append(f"Reported by: {issue.reporter.get_full_name()}")

        # Add sprint context
        if hasattr(issue, "sprint") and issue.sprint:
            parts.append(f"Sprint: {issue.sprint.name}")

        # Add labels (if model has labels field)
        if hasattr(issue, "labels"):
            try:
                labels = issue.labels.all()
                if labels.exists():
                    label_names = ", ".join([label.name for label in labels])
                    parts.append(f"Labels: {label_names}")
            except Exception:
                pass  # Skip if labels not available

        text = "\n".join(parts)
        logger.debug(f"[RAG] Prepared text for {issue.key}: {len(text)} chars")

        return text

    def _sanitize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize metadata for Pinecone compatibility.

        Pinecone REJECTS null values in metadata fields.
        This method converts null → appropriate default values.

        Args:
            metadata: Raw metadata dictionary

        Returns:
            Sanitized metadata with no null values
        """
        defaults = {
            "assignee_id": "unassigned",
            "assignee_username": "unassigned",
            "assignee_name": "Unassigned",
            "reporter_id": "unknown",
            "reporter_username": "unknown",
            "reporter_name": "Unknown",
            "sprint_id": "backlog",
            "sprint_name": "Backlog",
            "sprint_status": "backlog",
            "labels": "",
        }

        sanitized = {}
        for key, value in metadata.items():
            if value is None:
                # Use intelligent default or empty string
                sanitized[key] = defaults.get(key, "")
                logger.debug(
                    f"[SANITIZE] Converted null to default: {key} = '{sanitized[key]}'"
                )
            elif isinstance(value, (list, dict)):
                # Convert complex types to string if not empty
                sanitized[key] = str(value) if value else ""
            else:
                sanitized[key] = value

        return sanitized

    def _prepare_metadata(self, issue: Issue) -> Dict[str, Any]:
        """
        Prepare COMPLETE metadata for Pinecone storage.

        ENHANCED with sprint context, labels, status_category, issue_key
        for better semantic search and metadata filtering.

        NOTE: All null values will be sanitized before upsert to prevent
        Pinecone rejection errors.
        """
        metadata = {
            # Core identification
            "issue_id": str(issue.id),
            "project_id": str(issue.project_id),
            "project_key": issue.project.key,
            "issue_key": issue.key,
            "full_key": issue.full_key,
            "title": issue.title[:200],  # Truncate for Pinecone limits
            # Classification
            "issue_type": issue.issue_type.name,
            "issue_type_category": issue.issue_type.category
            if hasattr(issue.issue_type, "category")
            else None,
            "status": issue.status.name,
            "status_category": issue.status.category
            if hasattr(issue.status, "category")
            else None,
            "priority": issue.priority,
            # Assignment context
            "assignee_id": str(issue.assignee_id) if issue.assignee_id else None,
            "assignee_username": issue.assignee.username if issue.assignee else None,
            "assignee_name": issue.assignee.get_full_name() if issue.assignee else None,
            "reporter_id": str(issue.reporter_id) if issue.reporter_id else None,
            "reporter_username": issue.reporter.username if issue.reporter else None,
            "reporter_name": issue.reporter.get_full_name() if issue.reporter else None,
            # Sprint context (CRITICAL for temporal queries)
            "sprint_id": str(issue.sprint_id) if issue.sprint_id else None,
            "sprint_name": issue.sprint.name if issue.sprint else None,
            "sprint_status": issue.sprint.status if issue.sprint else None,
            # Estimation
            "story_points": issue.story_points if issue.story_points else None,
            "estimated_hours": float(issue.estimated_hours)
            if issue.estimated_hours
            else None,
            # Temporal
            "created_at": issue.created_at.isoformat(),
            "updated_at": issue.updated_at.isoformat(),
            "resolved_at": issue.resolved_at.isoformat() if issue.resolved_at else None,
        }

        # Add labels if model supports them
        if hasattr(issue, "labels"):
            try:
                labels = issue.labels.all()
                if labels.exists():
                    label_names = [label.name for label in labels]
                    metadata["labels"] = ",".join(label_names)  # Comma-separated string
                else:
                    metadata["labels"] = None
            except Exception:
                metadata["labels"] = None

        # Sanitize to remove null values (Pinecone requirement)
        return self._sanitize_metadata(metadata)

    def _calculate_hash(self, text: str) -> str:
        """Calculate SHA-256 hash of text content."""
        return hashlib.sha256(text.encode()).hexdigest()

    def index_sprint(self, sprint_id: str) -> tuple[bool, str]:
        """
        Index a single sprint in Pinecone 'sprints' namespace.

        Args:
            sprint_id: Sprint UUID

        Returns:
            Tuple of (success: bool, error_message: str)
        """
        self._check_available()
        try:
            from apps.projects.models import Sprint

            logger.info(f"[INDEX SPRINT] Starting index for sprint {sprint_id}")
            sprint = Sprint.objects.select_related("project", "created_by").get(
                id=sprint_id
            )

            # Prepare text for embedding
            text_content = self._prepare_sprint_text(sprint)
            logger.debug(
                f"[INDEX SPRINT] Text prepared, length: {len(text_content)} chars"
            )

            # Generate embedding
            embedding_vector = self.openai.generate_embedding(text_content)
            logger.info(
                f"[OPENAI] Sprint embedding generated, dimension: {
    len(embedding_vector)}"
            )

            # Prepare metadata
            metadata = self._prepare_sprint_metadata(sprint)
            logger.debug(f"[INDEX SPRINT] Metadata prepared: {len(metadata)} fields")

            # Upsert to Pinecone
            vector_id = f"sprint_{sprint_id}"
            logger.info(f"[PINECONE] Upserting sprint vector {vector_id}...")
            self.pinecone.upsert_vector(
                vector_id=vector_id,
                vector=embedding_vector,
                metadata=metadata,
                namespace="sprints",
            )
            logger.info(f"[PINECONE] Sprint upsert successful for {vector_id}")

            return True, ""

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.exception(f"[INDEX SPRINT] ERROR: {error_msg}")
            return False, error_msg

    def index_project_sprints(self, project_id: str) -> Dict[str, Any]:
        """
        Index all sprints in a project.

        Args:
            project_id: Project UUID

        Returns:
            Dictionary with indexing statistics
        """
        self._check_available()
        try:
            from apps.projects.models import Sprint

            logger.info(f"[BATCH INDEX SPRINTS] Starting for project {project_id}")

            sprints = Sprint.objects.filter(project_id=project_id).select_related(
                "project", "created_by"
            )

            total = sprints.count()
            indexed = 0
            failed = 0
            errors = []

            logger.info(f"[BATCH INDEX SPRINTS] Found {total} sprints to index")

            for i, sprint in enumerate(sprints, 1):
                try:
                    success, error_msg = self.index_sprint(str(sprint.id))

                    if success:
                        indexed += 1
                    else:
                        failed += 1
                        errors.append(
                            {
                                "sprint_id": str(sprint.id),
                                "sprint_name": sprint.name,
                                "error": error_msg,
                            }
                        )
                        logger.warning(
                            f"[BATCH INDEX SPRINTS] FAILED: Sprint {i}/{total} failed: {error_msg}"
                        )

                except Exception as e:
                    failed += 1
                    errors.append(
                        {
                            "sprint_id": str(sprint.id),
                            "sprint_name": sprint.name,
                            "error": f"{type(e).__name__}: {str(e)}",
                        }
                    )

            success_rate = round((indexed / total * 100), 1) if total > 0 else 0

            logger.info(
                f"[BATCH INDEX SPRINTS] Complete: {indexed}/{total} indexed ({success_rate}%), "
                f"{failed} failed"
            )

            return {
                "total": total,
                "indexed": indexed,
                "failed": failed,
                "success_rate": success_rate,
                "errors": errors,
            }

        except Exception as e:
            logger.exception(f"[BATCH INDEX SPRINTS] Critical error: {str(e)}")
            raise

    def index_team_member(self, project_id: str, user_id: int) -> tuple[bool, str]:
        """
        Index a team member's activity/context in Pinecone 'team_members' namespace.

        Args:
            project_id: Project UUID
            user_id: User ID

        Returns:
            Tuple of (success: bool, error_message: str)
        """
        self._check_available()
        try:
            from django.contrib.auth import get_user_model

            from apps.projects.models import Project

            User = get_user_model()

            logger.info(
                f"[INDEX MEMBER] Starting index for user {user_id} in project {project_id}"
            )

            project = Project.objects.get(id=project_id)
            user = User.objects.get(id=user_id)

            # Prepare text for embedding
            text_content = self._prepare_team_member_text(project, user)
            logger.debug(
                f"[INDEX MEMBER] Text prepared, length: {len(text_content)} chars"
            )

            # Generate embedding
            embedding_vector = self.openai.generate_embedding(text_content)
            logger.info(
                f"[OPENAI] Team member embedding generated, dimension: {
    len(embedding_vector)}"
            )

            # Prepare metadata
            metadata = self._prepare_team_member_metadata(project, user)
            logger.debug(f"[INDEX MEMBER] Metadata prepared: {len(metadata)} fields")

            # Upsert to Pinecone
            vector_id = f"member_{project_id}_{user_id}"
            logger.info(f"[PINECONE] Upserting team member vector {vector_id}...")
            self.pinecone.upsert_vector(
                vector_id=vector_id,
                vector=embedding_vector,
                metadata=metadata,
                namespace="team_members",
            )
            logger.info(f"[PINECONE] Team member upsert successful for {vector_id}")

            return True, ""

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.exception(f"[INDEX MEMBER] ERROR: {error_msg}")
            return False, error_msg

    def index_project_context(self, project_id: str) -> tuple[bool, str]:
        """
        Index project-level context in Pinecone 'project_context' namespace.

        Args:
            project_id: Project UUID

        Returns:
            Tuple of (success: bool, error_message: str)
        """
        self._check_available()
        try:
            from apps.projects.models import Project

            logger.info(f"[INDEX PROJECT] Starting index for project {project_id}")
            project = Project.objects.select_related(
                "workspace", "workspace__organization"
            ).get(id=project_id)

            # Prepare text for embedding
            text_content = self._prepare_project_context_text(project)
            logger.debug(
                f"[INDEX PROJECT] Text prepared, length: {len(text_content)} chars"
            )

            # Generate embedding
            embedding_vector = self.openai.generate_embedding(text_content)
            logger.info(
                f"[OPENAI] Project embedding generated, dimension: {
    len(embedding_vector)}"
            )

            # Prepare metadata
            metadata = self._prepare_project_context_metadata(project)
            logger.debug(f"[INDEX PROJECT] Metadata prepared: {len(metadata)} fields")

            # Upsert to Pinecone
            vector_id = f"project_{project_id}"
            logger.info(f"[PINECONE] Upserting project vector {vector_id}...")
            self.pinecone.upsert_vector(
                vector_id=vector_id,
                vector=embedding_vector,
                metadata=metadata,
                namespace="project_context",
            )
            logger.info(f"[PINECONE] Project upsert successful for {vector_id}")

            return True, ""

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.exception(f"[INDEX PROJECT] ERROR: {error_msg}")
            return False, error_msg

    def _prepare_sprint_text(self, sprint) -> str:
        """
        Prepare sprint text for embedding generation.

        Args:
            sprint: Sprint model instance

        Returns:
            Rich text context for embedding
        """
        from apps.projects.models import Sprint

        parts = [
            f"Sprint: {sprint.name}",
            f"Status: {sprint.status}",
            f"Project: {sprint.project.name} ({sprint.project.key})",
        ]

        if sprint.goal:
            parts.append(f"Goal: {sprint.goal}")

        if sprint.start_date and sprint.end_date:
            parts.append(
                f"Duration: {
    sprint.start_date} to {
        sprint.end_date} ({
            sprint.duration_days} days)"
            )

        # Add sprint statistics
        issue_count = sprint.issue_count
        completed_count = sprint.completed_issue_count
        parts.append(f"Issues: {issue_count} total, {completed_count} completed")

        parts.append(
            f"Story Points: {sprint.completed_points}/{sprint.committed_points}"
        )
        parts.append(f"Progress: {sprint.progress_percentage}%")

        return "\n".join(parts)

    def _prepare_sprint_metadata(self, sprint) -> Dict[str, Any]:
        """
        Prepare sprint metadata for Pinecone storage.

        Args:
            sprint: Sprint model instance

        Returns:
            Metadata dictionary
        """
        metadata = {
            "sprint_id": str(sprint.id),
            "project_id": str(sprint.project_id),
            "project_key": sprint.project.key,
            "sprint_name": sprint.name,
            "sprint_goal": sprint.goal[:500] if sprint.goal else None,
            "status": sprint.status,
            "start_date": sprint.start_date.isoformat() if sprint.start_date else None,
            "end_date": sprint.end_date.isoformat() if sprint.end_date else None,
            "duration_days": int(sprint.duration_days) if sprint.duration_days else 0,
            "remaining_days": int(sprint.remaining_days)
            if sprint.is_active and sprint.remaining_days
            else None,
            "committed_points": float(sprint.committed_points),
            "completed_points": float(sprint.completed_points),
            "progress_percentage": float(sprint.progress_percentage)
            if sprint.progress_percentage is not None
            else 0.0,
            "issue_count": int(sprint.issue_count) if sprint.issue_count else 0,
            "completed_issue_count": int(sprint.completed_issue_count)
            if sprint.completed_issue_count
            else 0,
            "created_at": sprint.created_at.isoformat(),
            "completed_at": sprint.completed_at.isoformat()
            if sprint.completed_at
            else None,
            "entity_type": "sprint",
        }

        return self._sanitize_metadata(metadata)

    def _prepare_team_member_text(self, project, user) -> str:
        """
        Prepare team member activity text for embedding.

        Args:
            project: Project instance
            user: User instance

        Returns:
            Rich text context about team member activity
        """
        parts = [
            f"Team Member: {user.get_full_name()} ({user.username})",
            f"Email: {user.email}",
            f"Project: {project.name} ({project.key})",
        ]

        # Get assigned issues statistics
        assigned_issues = Issue.objects.filter(
            project=project, assignee=user, is_active=True
        ).select_related("status", "issue_type")

        assigned_count = assigned_issues.count()
        if assigned_count > 0:
            completed_count = assigned_issues.filter(status__is_final=True).count()
            in_progress_count = assigned_issues.filter(
                status__category="in_progress"
            ).count()

            parts.append(
                f"Assigned Issues: {assigned_count} total, {completed_count} completed, {in_progress_count} in progress"
            )

            # Calculate story points
            total_points = sum(issue.story_points or 0 for issue in assigned_issues)
            parts.append(f"Total Story Points: {total_points}")

            # Recent issues
            recent_issues = assigned_issues.order_by("-updated_at")[:5]
            if recent_issues.exists():
                recent_titles = [
                    f"{issue.full_key}: {issue.title}" for issue in recent_issues
                ]
                parts.append(f"Recent Issues: {', '.join(recent_titles)}")
        else:
            parts.append("No assigned issues currently")

        # Get reported issues
        reported_count = Issue.objects.filter(
            project=project, reporter=user, is_active=True
        ).count()
        parts.append(f"Reported Issues: {reported_count}")

        return "\n".join(parts)

    def _prepare_team_member_metadata(self, project, user) -> Dict[str, Any]:
        """
        Prepare team member metadata for Pinecone storage.

        Args:
            project: Project instance
            user: User instance

        Returns:
            Metadata dictionary
        """
        # Calculate statistics
        assigned_issues = Issue.objects.filter(
            project=project, assignee=user, is_active=True
        )
        completed_count = assigned_issues.filter(status__is_final=True).count()
        in_progress_count = assigned_issues.filter(
            status__category="in_progress"
        ).count()
        total_points = sum(issue.story_points or 0 for issue in assigned_issues)

        # Get recent activity
        recent_updated = assigned_issues.order_by("-updated_at").first()

        metadata = {
            "user_id": str(user.id),
            "project_id": str(project.id),
            "project_key": project.key,
            "username": user.username,
            "full_name": user.get_full_name(),
            "email": user.email,
            "assigned_issues_count": assigned_issues.count(),
            "completed_issues_count": completed_count,
            "in_progress_issues_count": in_progress_count,
            "total_story_points": total_points,
            "reported_issues_count": Issue.objects.filter(
                project=project, reporter=user, is_active=True
            ).count(),
            "last_activity": recent_updated.updated_at.isoformat()
            if recent_updated
            else None,
            "entity_type": "team_member",
        }

        return self._sanitize_metadata(metadata)

    def _prepare_project_context_text(self, project) -> str:
        """
        Prepare project context text for embedding.

        Args:
            project: Project instance

        Returns:
            Rich text context about project
        """
        parts = [
            f"Project: {project.name} ({project.key})",
            f"Description: {
    project.description if project.description else 'No description'}",
        ]

        # Workspace and organization context
        if project.workspace:
            parts.append(
                f"Workspace: {project.workspace.name} ({project.workspace.slug})"
            )
            if project.workspace.organization:
                parts.append(f"Organization: {project.workspace.organization.name}")

        # Project statistics
        total_issues = project.issues.filter(is_active=True).count()
        total_sprints = project.sprints.count()
        active_sprints = project.sprints.filter(status="active").count()

        parts.append(f"Total Issues: {total_issues}")
        parts.append(f"Total Sprints: {total_sprints} ({active_sprints} active)")

        # Team size
        team_size = project.team_members.filter(is_active=True).count()
        parts.append(f"Team Size: {team_size} members")

        return "\n".join(parts)

    def _prepare_project_context_metadata(self, project) -> Dict[str, Any]:
        """
        Prepare project context metadata for Pinecone storage.

        Args:
            project: Project instance

        Returns:
            Metadata dictionary
        """
        total_issues = project.issues.filter(is_active=True).count()
        total_sprints = project.sprints.count()
        active_sprints = project.sprints.filter(status="active").count()
        team_size = project.team_members.filter(is_active=True).count()

        metadata = {
            "project_id": str(project.id),
            "project_key": project.key,
            "project_name": project.name,
            "description": project.description[:1000] if project.description else None,
            "workspace_id": str(project.workspace_id) if project.workspace_id else None,
            "workspace_name": project.workspace.name if project.workspace else None,
            "organization_id": str(project.workspace.organization_id)
            if project.workspace and project.workspace.organization
            else None,
            "organization_name": project.workspace.organization.name
            if project.workspace and project.workspace.organization
            else None,
            "total_issues": total_issues,
            "total_sprints": total_sprints,
            "active_sprints": active_sprints,
            "team_size": team_size,
            "created_at": project.created_at.isoformat()
            if hasattr(project, "created_at")
            else None,
            "entity_type": "project",
        }

        return self._sanitize_metadata(metadata)
