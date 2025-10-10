import hashlib
from datetime import timedelta
from typing import Dict, Optional

from django.utils import timezone


class DiagramService:
    def __init__(self):
        self.cache_duration_hours = 1

    def generate_workflow_diagram(self, project) -> Dict:
        from apps.projects.models import WorkflowStatus, WorkflowTransition

        cache_key = self._generate_cache_key("workflow", project.id)
        cached = self._get_cached_diagram(cache_key)
        if cached:
            return cached

        statuses = WorkflowStatus.objects.filter(project=project)
        transitions = WorkflowTransition.objects.filter(from_status__project=project)

        nodes = []
        edges = []

        for status in statuses:
            nodes.append(
                {
                    "id": str(status.id),
                    "label": status.name,
                    "category": status.category,
                    "color": self._get_status_color(status.category),
                }
            )

        for transition in transitions:
            edges.append(
                {
                    "from": str(transition.from_status.id),
                    "to": str(transition.to_status.id),
                    "label": transition.name or "",
                }
            )

        diagram_data = {
            "type": "workflow",
            "nodes": nodes,
            "edges": edges,
            "layout": "hierarchical",
        }

        svg_data = self._generate_svg_from_graph(diagram_data)

        self._cache_diagram(cache_key, svg_data, "workflow", project, "svg")

        return {"diagram_type": "workflow", "data": svg_data, "format": "svg"}

    def generate_dependency_diagram(self, project) -> Dict:
        from apps.projects.models import Issue, IssueLink

        cache_key = self._generate_cache_key("dependency", project.id)
        cached = self._get_cached_diagram(cache_key)
        if cached:
            return cached

        issues = Issue.objects.filter(project=project, is_active=True)[:50]
        links = IssueLink.objects.filter(
            source_issue__project=project, link_type__in=["depends_on", "blocks"]
        )

        nodes = []
        edges = []

        for issue in issues:
            nodes.append(
                {
                    "id": str(issue.id),
                    "label": f"{issue.key} - {issue.title[:30]}",
                    "status": issue.status.name,
                    "color": self._get_status_color(issue.status.category),
                }
            )

        for link in links:
            edges.append(
                {
                    "from": str(link.source_issue.id),
                    "to": str(link.target_issue.id),
                    "label": link.link_type,
                }
            )

        diagram_data = {"type": "dependency", "nodes": nodes, "edges": edges}

        svg_data = self._generate_svg_from_graph(diagram_data)

        self._cache_diagram(cache_key, svg_data, "dependency", project, "svg")

        return {"diagram_type": "dependency", "data": svg_data, "format": "svg"}

    def generate_roadmap(self, project) -> Dict:
        from apps.projects.models import Issue, Sprint

        cache_key = self._generate_cache_key("roadmap", project.id)
        cached = self._get_cached_diagram(cache_key)
        if cached:
            return cached

        sprints = Sprint.objects.filter(project=project).order_by("start_date")[:10]

        roadmap_data = {"type": "roadmap", "sprints": []}

        for sprint in sprints:
            issues = Issue.objects.filter(sprint=sprint, is_active=True)
            epics = issues.filter(issue_type__category="epic")

            sprint_data = {
                "id": str(sprint.id),
                "name": sprint.name,
                "start_date": str(sprint.start_date) if sprint.start_date else None,
                "end_date": str(sprint.end_date) if sprint.end_date else None,
                "status": sprint.status,
                "epics": [],
            }

            for epic in epics:
                epic_data = {
                    "id": str(epic.id),
                    "key": epic.key,
                    "title": epic.title,
                    "status": epic.status.name,
                    "progress": self._calculate_epic_progress(epic),
                }
                sprint_data["epics"].append(epic_data)

            roadmap_data["sprints"].append(sprint_data)

        svg_data = self._generate_roadmap_svg(roadmap_data)

        self._cache_diagram(cache_key, svg_data, "roadmap", project, "svg")

        return {"diagram_type": "roadmap", "data": svg_data, "format": "svg"}

    def generate_uml_from_code(self, repository) -> Dict:
        cache_key = self._generate_cache_key("uml", repository.project.id)
        cached = self._get_cached_diagram(cache_key)
        if cached:
            return cached

        uml_data = {
            "type": "uml",
            "classes": [
                {
                    "name": "Example",
                    "methods": ["__init__", "process"],
                    "attributes": ["id", "name"],
                }
            ],
            "relationships": [],
        }

        svg_data = self._generate_uml_svg(uml_data)

        self._cache_diagram(cache_key, svg_data, "uml", repository.project, "svg")

        return {"diagram_type": "uml", "data": svg_data, "format": "svg"}

    def generate_architecture_diagram(self, repository) -> Dict:
        cache_key = self._generate_cache_key("architecture", repository.project.id)
        cached = self._get_cached_diagram(cache_key)
        if cached:
            return cached

        arch_data = {
            "type": "architecture",
            "modules": [
                {"name": "Frontend", "components": ["UI", "Components"]},
                {"name": "Backend", "components": ["API", "Services", "Models"]},
                {"name": "Database", "components": ["PostgreSQL"]},
            ],
        }

        svg_data = self._generate_architecture_svg(arch_data)

        self._cache_diagram(
            cache_key, svg_data, "architecture", repository.project, "svg"
        )

        return {"diagram_type": "architecture", "data": svg_data, "format": "svg"}

    def _generate_cache_key(self, diagram_type: str, project_id) -> str:
        data = f"{diagram_type}_{project_id}_{timezone.now().date()}"
        return hashlib.md5(data.encode()).hexdigest()

    def _get_cached_diagram(self, cache_key: str) -> Optional[Dict]:
        from apps.reporting.models import DiagramCache

        try:
            cache = DiagramCache.objects.get(cache_key=cache_key)
            if not cache.is_expired:
                cache.increment_access_count()
                return {
                    "diagram_type": cache.diagram_type,
                    "data": cache.diagram_data,
                    "format": cache.format,
                    "cached": True,
                }
        except DiagramCache.DoesNotExist:
            pass
        return None

    def _cache_diagram(
        self, cache_key: str, data: str, diagram_type: str, project, format: str
    ):
        from apps.reporting.models import DiagramCache

        expires_at = timezone.now() + timedelta(hours=self.cache_duration_hours)

        DiagramCache.objects.update_or_create(
            cache_key=cache_key,
            defaults={
                "project": project,
                "diagram_type": diagram_type,
                "diagram_data": data,
                "format": format,
                "expires_at": expires_at,
            },
        )

    def _get_status_color(self, category: str) -> str:
        colors = {
            "todo": "#6c757d",
            "in_progress": "#007bff",
            "done": "#28a745",
            "backlog": "#ffc107",
        }
        return colors.get(category, "#6c757d")

    def _calculate_epic_progress(self, epic) -> float:
        sub_issues = epic.sub_issues.filter(is_active=True)
        total = sub_issues.count()
        if total == 0:
            return 0.0

        completed = sub_issues.filter(status__category="done").count()
        return round((completed / total) * 100, 2)

    def _generate_svg_from_graph(self, graph_data: Dict) -> str:
        nodes = graph_data.get("nodes", [])

        svg_parts = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600">'
        ]

        y_offset = 50
        for i, node in enumerate(nodes):
            x = 100 + (i % 5) * 150
            y = y_offset + (i // 5) * 100

            svg_parts.append(
                f'<rect x="{x}" y="{y}" width="120" height="60" '
                f'fill="{node.get("color", "#007bff")}" stroke="#333" stroke-width="2" rx="5"/>'
            )
            svg_parts.append(
                f'<text x="{x + 60}" y="{y + 35}" text-anchor="middle" '
                f'fill="white" font-size="12">{node.get("label", "")[:15]}</text>'
            )

        svg_parts.append("</svg>")
        return "\n".join(svg_parts)

    def _generate_roadmap_svg(self, roadmap_data: Dict) -> str:
        svg_parts = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="600">'
        ]
        title = (
            '<text x="500" y="30" text-anchor="middle" '
            'font-size="20" font-weight="bold">Project roadmap</text>'
        )
        svg_parts.append(title)

        sprints = roadmap_data.get("sprints", [])
        for i, sprint in enumerate(sprints[:5]):
            x = 50 + i * 200
            y = 80
            svg_parts.append(
                f'<rect x="{x}" y="{y}" width="180" height="400" '
                f'fill="#f8f9fa" stroke="#333" stroke-width="1"/>'
            )
            svg_parts.append(
                f'<text x="{x + 90}" y="{y + 20}" text-anchor="middle" '
                f'font-size="14" font-weight="bold">{sprint.get("name", "")}</text>'
            )

        svg_parts.append("</svg>")
        return "\n".join(svg_parts)

    def _generate_uml_svg(self, uml_data: Dict) -> str:
        svg_parts = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400">'
        ]
        svg_parts.append(
            '<text x="300" y="30" text-anchor="middle" font-size="18">UML Class Diagram</text>'
        )
        svg_parts.append("</svg>")
        return "\n".join(svg_parts)

    def _generate_architecture_svg(self, arch_data: Dict) -> str:
        svg_parts = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500">'
        ]
        svg_parts.append(
            '<text x="400" y="30" text-anchor="middle" font-size="18">Architecture Diagram</text>'
        )
        svg_parts.append("</svg>")
        return "\n".join(svg_parts)
