import hashlib
from datetime import timedelta
from typing import Dict, Optional

from django.utils import timezone

from .diagram_generators import (
    generate_workflow_diagram_svg,
    generate_dependency_graph_svg,
    generate_burndown_chart_svg,
    generate_velocity_chart_svg,
    generate_roadmap_timeline_svg,
    check_github_integration,
)


class DiagramService:
    """
    Orchestrates diagram generation with caching.
    
    Uses modular diagram generators from diagram_generators.py.
    """
    
    def __init__(self):
        self.cache_duration_hours = 1

    def generate_workflow_diagram(self, project) -> Dict:
        """Generate workflow diagram with status boxes and transition arrows."""
        cache_key = self._generate_cache_key("workflow", project.id)
        cached = self._get_cached_diagram(cache_key)
        if cached:
            return cached

        # Use new generator
        svg_data = generate_workflow_diagram_svg(project)

        self._cache_diagram(cache_key, svg_data, "workflow", project, "svg")

        return {"diagram_type": "workflow", "data": svg_data, "format": "svg", "cached": False}

    def generate_dependency_diagram(self, project) -> Dict:
        """Generate dependency graph showing issue relationships with connections."""
        cache_key = self._generate_cache_key("dependency", project.id)
        cached = self._get_cached_diagram(cache_key)
        if cached:
            return cached

        # Use new generator
        svg_data = generate_dependency_graph_svg(project)

        self._cache_diagram(cache_key, svg_data, "dependency", project, "svg")

        return {"diagram_type": "dependency", "data": svg_data, "format": "svg", "cached": False}

    def generate_roadmap(self, project) -> Dict:
        """Generate roadmap timeline with Gantt-style sprint bars."""
        cache_key = self._generate_cache_key("roadmap", project.id)
        cached = self._get_cached_diagram(cache_key)
        if cached:
            return cached

        # Use new generator
        svg_data = generate_roadmap_timeline_svg(project)

        self._cache_diagram(cache_key, svg_data, "roadmap", project, "svg")

        return {"diagram_type": "roadmap", "data": svg_data, "format": "svg", "cached": False}

    def generate_uml_from_code(self, integration) -> Dict:
        """
        Generate UML diagram from code (requires GitHub integration).
        
        Note: This is a placeholder - full implementation requires code parsing.
        """
        # Check GitHub integration exists
        error = check_github_integration(integration.project)
        if error:
            # Return error dict instead of raising exception
            return error
        
        from .svg_builder import create_empty_state
        
        svg_data = create_empty_state(
            800, 600,
            "UML Diagram - Coming Soon",
            "UML diagram generation from code analysis is under development"
        )
        
        return {"diagram_type": "uml", "data": svg_data, "format": "svg", "cached": False}

    def generate_architecture_diagram(self, integration) -> Dict:
        """
        Generate architecture diagram (requires GitHub integration).
        
        Note: This is a placeholder - full implementation requires code analysis.
        """
        # Check GitHub integration exists
        error = check_github_integration(integration.project)
        if error:
            # Return error dict instead of raising exception
            return error
        
        from .svg_builder import create_empty_state
        
        svg_data = create_empty_state(
            800, 600,
            "Architecture Diagram - Coming Soon",
            "Architecture diagram generation from code analysis is under development"
        )
        
        return {"diagram_type": "architecture", "data": svg_data, "format": "svg", "cached": False}

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

    # All SVG generation logic has been moved to diagram_generators.py
    # for better modularity and maintainability
