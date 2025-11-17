"""
Diagram Data Service - JSON Data Architecture.

This service provides structured data for diagram rendering.
Returns pure JSON data structures instead of SVG markup.

Benefits:
- Frontend renders with D3.js, Cytoscape.js, or similar libraries
- No string escaping issues
- Smaller payload size
- Frontend can add interactivity (zoom, pan, drag)
- Export handled by frontend (SVG, PNG, PDF)
- Separation of concerns: backend = data, frontend = visualization

Diagram Types:
- Workflow: Status nodes with transition edges
- Dependency: Issue nodes with dependency edges
- Roadmap: Sprint timeline with milestones
"""

import logging
from datetime import timedelta
from typing import Dict, List, Optional

from django.db.models import Count, Q
from django.utils import timezone

logger = logging.getLogger(__name__)


class DiagramDataService:
    """
    Generate diagram data structures for frontend rendering.

    All methods return Python dicts that will be JSON-serialized by DRF.
    No SVG generation - pure data computation.
    """

    def get_workflow_data(self, project) -> Dict:
        """
        Generate workflow diagram data structure.

        Returns dict with:
        - nodes: List of status boxes with positions and styling
        - edges: List of transition arrows between statuses
        - metadata: Project info and diagram statistics
        - legend: Color legend for status categories
        - layout: Canvas dimensions and layout type

        Args:
            project: Project instance

        Returns:
            Dict with workflow data structure
        """
        from apps.projects.models import WorkflowStatus, WorkflowTransition

        logger.info(f"Generating workflow data for project {project.name}")

        # Query statuses with issue counts
        statuses = (
            WorkflowStatus.objects.filter(project=project)
            .prefetch_related("issues")
            .order_by("order", "name")
        )

        if not statuses.exists():
            return {
                "diagram_type": "workflow",
                "metadata": {
                    "project_id": str(project.id),
                    "project_name": project.name,
                    "project_key": project.key,
                    "status_count": 0,
                    "transition_count": 0,
                    "total_issues": 0,
                    "error": "No workflow statuses found",
                },
                "nodes": [],
                "edges": [],
                "legend": self._get_workflow_legend(),
                "layout": {
                    "type": "horizontal",
                    "width": 1600,
                    "height": 500,
                    "padding": 60,
                },
            }

        # Build status nodes with positioning
        nodes = []
        status_map = {}  # id -> index for edge references

        # Calculate positioning
        node_width = 220
        node_height = 100
        horizontal_spacing = 300
        start_x = 170
        start_y = 160

        for idx, status in enumerate(statuses):
            issue_count = status.issues.filter(is_active=True).count()

            # Determine colors based on category
            color = self._get_status_color(status.category)
            stroke_color = self._get_stroke_color(status)
            stroke_width = 3 if (status.is_initial or status.is_final) else 2

            node = {
                "id": f"status-{status.id}",
                "name": status.name,
                "type": "status",
                "category": status.category,
                "color": color,
                "stroke_color": stroke_color,
                "stroke_width": stroke_width,
                "issue_count": issue_count,
                "is_start": status.is_initial,
                "is_end": status.is_final,
                "position": {"x": start_x + (idx * horizontal_spacing), "y": start_y},
                "dimensions": {"width": node_width, "height": node_height},
            }

            nodes.append(node)
            status_map[str(status.id)] = idx

        # Query transitions
        transitions = WorkflowTransition.objects.filter(
            from_status__project=project
        ).select_related("from_status", "to_status")

        # Build edges
        edges = []
        for idx, trans in enumerate(transitions):
            from_id = str(trans.from_status.id)
            to_id = str(trans.to_status.id)

            if from_id in status_map and to_id in status_map:
                edge = {
                    "id": f"transition-{idx + 1}",
                    "source": f"status-{from_id}",
                    "target": f"status-{to_id}",
                    "label": f"{trans.from_status.name} → {trans.to_status.name}",
                    "type": "transition",
                    "color": "#42526E",
                    "width": 2,
                }
                edges.append(edge)

        # Calculate total issues
        total_issues = sum(node["issue_count"] for node in nodes)

        # Calculate canvas width based on node count
        canvas_width = max(1600, start_x * 2 + (len(nodes) * horizontal_spacing))

        return {
            "diagram_type": "workflow",
            "metadata": {
                "project_id": str(project.id),
                "project_name": project.name,
                "project_key": project.key,
                "status_count": len(nodes),
                "transition_count": len(edges),
                "total_issues": total_issues,
            },
            "nodes": nodes,
            "edges": edges,
            "legend": self._get_workflow_legend(),
            "layout": {
                "type": "horizontal",
                "width": canvas_width,
                "height": 500,
                "padding": 60,
            },
        }

    def get_dependency_data(self, project, filters: Optional[Dict] = None) -> Dict:
        """
        Generate dependency graph data structure.

        Returns dict with:
        - nodes: List of issue boxes with details
        - edges: List of dependency connections
        - metadata: Project info and filter details
        - layout: Canvas dimensions and layout type

        Args:
            project: Project instance
            filters: Optional dict with filter keys:
                - sprint_id: Sprint UUID or 'backlog'
                - status_ids: List of status UUIDs
                - priorities: List of priority strings
                - assignee_id: Assignee UUID or 'unassigned'
                - issue_type_ids: List of issue type UUIDs
                - search: Search term

        Returns:
            Dict with dependency graph data structure
        """
        from apps.projects.models import Issue, IssueLink

        logger.info(f"Generating dependency data for project {project.name}")

        filters = filters or {}

        # Build queryset with filters
        queryset = (
            Issue.objects.filter(project=project, is_active=True)
            .select_related("status", "assignee", "issue_type", "sprint")
            .prefetch_related("source_links", "target_links")
        )

        # Apply filters
        if filters.get("sprint_id"):
            if filters["sprint_id"] == "backlog":
                queryset = queryset.filter(sprint__isnull=True)
            else:
                queryset = queryset.filter(sprint_id=filters["sprint_id"])

        if filters.get("status_ids"):
            queryset = queryset.filter(status_id__in=filters["status_ids"])

        if filters.get("priorities"):
            queryset = queryset.filter(priority__in=filters["priorities"])

        if filters.get("assignee_id"):
            if filters["assignee_id"] == "unassigned":
                queryset = queryset.filter(assignee__isnull=True)
            else:
                queryset = queryset.filter(assignee_id=filters["assignee_id"])

        if filters.get("issue_type_ids"):
            queryset = queryset.filter(issue_type_id__in=filters["issue_type_ids"])

        if filters.get("search"):
            search = filters["search"]
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(key__icontains=search)
            )

        issues = list(queryset[:100])  # Limit to 100 for performance

        if not issues:
            return {
                "diagram_type": "dependency",
                "metadata": {
                    "project_id": str(project.id),
                    "project_name": project.name,
                    "issue_count": 0,
                    "dependency_count": 0,
                    "filters_applied": list(filters.keys()) if filters else [],
                },
                "nodes": [],
                "edges": [],
                "layout": {"type": "force-directed", "width": 1400, "height": 800},
            }

        # Build issue nodes
        nodes = []
        issue_ids = set()

        for issue in issues:
            issue_ids.add(str(issue.id))

            # Get assignee info
            assignee = None
            if issue.assignee:
                assignee = {
                    "id": issue.assignee.id,
                    "name": issue.assignee.get_full_name(),
                    "avatar_url": getattr(issue.assignee, "avatar_url", None),
                }

            node = {
                "id": f"issue-{issue.id}",
                "key": issue.key,
                "summary": issue.title,
                "status": issue.status.name if issue.status else "Unknown",
                "status_color": self._get_status_color(issue.status.category)
                if issue.status
                else "#5E6C84",
                "priority": issue.priority or "none",
                "priority_color": self._get_priority_color(issue.priority),
                "assignee": assignee,
                "type": issue.issue_type.category if issue.issue_type else "task",
                "estimate": issue.story_points,
                "issue_url": f"/projects/{project.id}/issues/{issue.id}",
            }

            nodes.append(node)

        # Build dependency edges
        edges = []
        edge_id = 1

        logger.debug(f"Building edges for {len(issues)} issues")
        logger.debug(f"Issue IDs for filtering: {list(issue_ids)[:5]}...")

        # Get all issue links for these issues
        # Use ID list for better performance and explicit filtering
        issue_uuid_list = [issue.id for issue in issues]

        logger.debug(
            f"Querying IssueLinks where source or target in {len(issue_uuid_list)} issues"
        )

        links = IssueLink.objects.filter(
            Q(source_issue_id__in=issue_uuid_list)
            | Q(target_issue_id__in=issue_uuid_list),
            source_issue__is_active=True,
            target_issue__is_active=True,
        ).select_related("source_issue", "target_issue")

        link_count = links.count()
        logger.info(f"Found {link_count} IssueLinks in database")

        if link_count == 0:
            # Diagnostic: Check if ANY links exist in project
            total_links = IssueLink.objects.filter(
                Q(source_issue__project=project) | Q(target_issue__project=project)
            ).count()
            logger.warning(
                f"No links found for filtered issues. Total links in project: {total_links}"
            )

        for link in links:
            source_id = str(link.source_issue.id)
            target_id = str(link.target_issue.id)

            logger.debug(
                f"Processing link: {link.source_issue.key} {link.link_type} {link.target_issue.key}"
            )

            # Only include if both nodes are in the filtered set
            if source_id in issue_ids and target_id in issue_ids:
                # Determine edge color and type
                if link.link_type == "blocks":
                    color = "#DE350B"  # Red for blocking
                    label = "Blocks"
                elif link.link_type == "blocked_by":
                    color = "#DE350B"  # Red for blocking (reverse)
                    label = "Blocked By"
                elif link.link_type == "depends_on":
                    color = "#0052CC"  # Blue for dependency
                    label = "Depends On"
                elif link.link_type == "dependency_of":
                    color = "#0052CC"  # Blue for dependency (reverse)
                    label = "Dependency Of"
                elif link.link_type == "relates_to":
                    color = "#6554C0"  # Purple for relation
                    label = "Relates To"
                elif link.link_type == "duplicates":
                    color = "#FF991F"  # Orange for duplicate
                    label = "Duplicates"
                elif link.link_type == "duplicated_by":
                    color = "#FF991F"  # Orange for duplicate (reverse)
                    label = "Duplicated By"
                else:
                    color = "#42526E"  # Gray for other
                    label = link.link_type.replace("_", " ").title()

                edge = {
                    "id": f"dep-{edge_id}",
                    "source": f"issue-{source_id}",
                    "target": f"issue-{target_id}",
                    "type": link.link_type,
                    "label": label,
                    "color": color,
                }
                edges.append(edge)
                edge_id += 1
                logger.debug(
                    f"Added edge: {edge['source']} -> {edge['target']} ({edge['type']})"
                )
            else:
                logger.debug(
                    f"Skipped link (nodes not in filtered set): {source_id} -> {target_id}"
                )

        logger.info(f"Built {len(edges)} edges from {link_count} links")

        # Build metadata with diagnostic info
        metadata = {
            "project_id": str(project.id),
            "project_name": project.name,
            "issue_count": len(nodes),
            "dependency_count": len(edges),
            "filters_applied": list(filters.keys()) if filters else [],
            "has_dependencies": len(edges) > 0,
        }

        # Add diagnostic info if no dependencies found
        if len(edges) == 0 and len(nodes) > 0:
            total_project_links = IssueLink.objects.filter(
                Q(source_issue__project=project) | Q(target_issue__project=project)
            ).count()
            metadata["debug"] = {
                "total_links_in_project": total_project_links,
                "message": "No dependencies found between filtered issues"
                if total_project_links > 0
                else "No issue links exist in this project yet",
            }

        return {
            "diagram_type": "dependency",
            "metadata": metadata,
            "nodes": nodes,
            "edges": edges,
            "layout": {"type": "force-directed", "width": 1400, "height": 800},
        }

    def get_roadmap_data(self, project) -> Dict:
        """
        Generate roadmap timeline data structure.

        Returns dict with:
        - sprints: List of sprint bars with dates and progress
        - milestones: List of milestone markers
        - metadata: Project info and date range
        - layout: Canvas dimensions and layout type

        Args:
            project: Project instance

        Returns:
            Dict with roadmap timeline data structure
        """
        from apps.projects.models import Sprint

        logger.info(f"Generating roadmap data for project {project.name}")

        # Query sprints ordered by start date
        sprints = (
            Sprint.objects.filter(project=project)
            .prefetch_related("issues")
            .order_by("start_date")
        )

        if not sprints.exists():
            return {
                "diagram_type": "roadmap",
                "metadata": {
                    "project_id": str(project.id),
                    "project_name": project.name,
                    "sprint_count": 0,
                    "start_date": None,
                    "end_date": None,
                    "today": timezone.now().date().isoformat(),
                },
                "sprints": [],
                "milestones": [],
                "layout": {"type": "timeline", "width": 1800, "height": 600},
            }

        # Build sprint data
        sprint_data = []
        earliest_date = None
        latest_date = None

        for sprint in sprints:
            # Track date range
            if not earliest_date or sprint.start_date < earliest_date:
                earliest_date = sprint.start_date
            if not latest_date or sprint.end_date > latest_date:
                latest_date = sprint.end_date

            # Count issues
            total_issues = sprint.issues.filter(is_active=True).count()
            completed_issues = sprint.issues.filter(
                is_active=True, status__is_final=True
            ).count()

            # Calculate progress
            progress = 0
            if total_issues > 0:
                progress = int((completed_issues / total_issues) * 100)

            # Determine status and color
            today = timezone.now().date()
            if sprint.end_date < today:
                status = "completed"
                color = "#00875A"  # Green
            elif sprint.start_date <= today <= sprint.end_date:
                status = "active"
                color = "#0052CC"  # Blue
            else:
                status = "planned"
                color = "#5E6C84"  # Gray

            # Calculate velocity (only for completed sprints)
            velocity = None
            if status == "completed" and sprint.issues.exists():
                velocity = (
                    sprint.issues.filter(
                        is_active=True, status__is_final=True
                    ).aggregate(total=Count("id"))["total"]
                    or 0
                )

            sprint_item = {
                "id": f"sprint-{sprint.id}",
                "name": sprint.name,
                "start_date": sprint.start_date.isoformat(),
                "end_date": sprint.end_date.isoformat(),
                "status": status,
                "color": color,
                "issue_count": total_issues,
                "completed_count": completed_issues,
                "progress": progress,
                "velocity": velocity,
            }

            sprint_data.append(sprint_item)

        # Build milestones (can be extended to query actual milestone model if exists)
        milestones = []

        # Add project creation as milestone
        if hasattr(project, "created_at"):
            milestones.append(
                {
                    "id": "milestone-project-start",
                    "name": "Project Start",
                    "date": project.created_at.date().isoformat(),
                    "color": "#00875A",
                }
            )

        # Calculate timeline range
        if earliest_date and latest_date:
            start_date = earliest_date.isoformat()
            end_date = latest_date.isoformat()
        else:
            start_date = None
            end_date = None

        return {
            "diagram_type": "roadmap",
            "metadata": {
                "project_id": str(project.id),
                "project_name": project.name,
                "sprint_count": len(sprint_data),
                "start_date": start_date,
                "end_date": end_date,
                "today": timezone.now().date().isoformat(),
            },
            "sprints": sprint_data,
            "milestones": milestones,
            "layout": {"type": "timeline", "width": 1800, "height": 600},
        }

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _get_status_color(self, category: str) -> str:
        """Get color for status category."""
        color_map = {
            "todo": "#5E6C84",  # Gray
            "backlog": "#5E6C84",  # Gray
            "inprogress": "#0052CC",  # Blue
            "in_progress": "#0052CC",
            "done": "#00875A",  # Green
            "complete": "#00875A",
            "blocked": "#DE350B",  # Red
            "review": "#6554C0",  # Purple
            "testing": "#FF991F",  # Orange
        }
        return color_map.get(category.lower(), "#5E6C84")

    def _get_stroke_color(self, status) -> str:
        """Get stroke color for status based on its properties."""
        if status.is_initial:
            return "#00875A"  # Green for start
        elif status.is_final:
            return "#00875A"  # Green for end
        else:
            return "#DFE1E6"  # Light gray for normal

    def _get_priority_color(self, priority: Optional[str]) -> str:
        """Get color for priority level."""
        if not priority:
            return "#5E6C84"  # Gray

        color_map = {
            "highest": "#DE350B",  # Red
            "high": "#FF5630",  # Orange-red
            "medium": "#FF991F",  # Orange
            "low": "#0052CC",  # Blue
            "lowest": "#5E6C84",  # Gray
            "p1": "#DE350B",
            "p2": "#FF5630",
            "p3": "#FF991F",
            "p4": "#0052CC",
            "p5": "#5E6C84",
        }
        return color_map.get(priority.lower(), "#5E6C84")

    def _get_workflow_legend(self) -> Dict:
        """Get legend for workflow diagram."""
        return {
            "title": "Status Colors",
            "items": [
                {"label": "To Do / Backlog", "color": "#5E6C84"},
                {"label": "In Progress", "color": "#0052CC"},
                {"label": "Done / Complete", "color": "#00875A"},
                {"label": "Blocked", "color": "#DE350B"},
                {"label": "Review", "color": "#6554C0"},
                {"label": "Testing", "color": "#FF991F"},
            ],
        }
