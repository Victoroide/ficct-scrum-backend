import hashlib
import logging
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
from .github_code_fetcher import GitHubCodeFetcher
from .python_code_analyzer import PythonCodeAnalyzer
from .uml_generator import UMLGenerator
from .architecture_generator import ArchitectureGenerator


logger = logging.getLogger(__name__)


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

    def generate_uml_diagram(self, project, diagram_format: str = "json", parameters: Dict = None) -> Dict:
        """
        Generate UML diagram by analyzing code from GitHub repository.
        
        Requires active GitHub integration. Analyzes Python code only.
        
        Args:
            project: Project instance
            diagram_format: Output format (json or svg)
            parameters: Additional parameters
            
        Returns:
            UML diagram data
            
        Raises:
            ValueError: If no GitHub integration or repository has no Python files
        """
        logger.info(f"Generating UML diagram for project {project.name}")
        
        # Get GitHub integration
        integration = self._get_github_integration(project)
        
        # Analyze code from GitHub
        analysis = self._analyze_github_repository(integration)
        
        # Generate UML
        generator = UMLGenerator()
        uml_data = generator.generate_uml_json(analysis, integration)
        
        import json
        data_str = json.dumps(uml_data, indent=2)
        
        logger.info("UML diagram generated successfully")
        
        return {
            "diagram_type": "uml",
            "data": data_str,
            "format": "json",
            "cached": False
        }

    def generate_architecture_diagram(self, project, diagram_format: str = "json", parameters: Dict = None) -> Dict:
        """
        Generate architecture diagram by analyzing code from GitHub repository.
        
        Requires active GitHub integration. Analyzes Python code only.
        
        Args:
            project: Project instance
            diagram_format: Output format (json or svg)
            parameters: Additional parameters
            
        Returns:
            Architecture diagram data
            
        Raises:
            ValueError: If no GitHub integration or repository has no Python files
        """
        logger.info(f"Generating architecture diagram for project {project.name}")
        
        # Get GitHub integration
        integration = self._get_github_integration(project)
        
        # Analyze code from GitHub
        analysis = self._analyze_github_repository(integration)
        
        # Generate architecture
        generator = ArchitectureGenerator()
        arch_data = generator.generate_architecture_json(analysis, integration)
        
        import json
        data_str = json.dumps(arch_data, indent=2)
        
        logger.info("Architecture diagram generated successfully")
        
        return {
            "diagram_type": "architecture",
            "data": data_str,
            "format": "json",
            "cached": False
        }

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

    def _get_github_integration(self, project):
        """
        Get GitHub integration for project.
        
        Args:
            project: Project instance
            
        Returns:
            GitHubIntegration instance
            
        Raises:
            ValueError: If no active GitHub integration
        """
        from apps.integrations.models import GitHubIntegration
        
        try:
            integration = GitHubIntegration.objects.get(
                project=project,
                is_active=True
            )
            
            # Validate that access token exists (is_connected is a property)
            if not integration.access_token:
                logger.error(f"GitHub integration exists but has no access token for project {project.id}")
                raise ValueError(
                    "GitHub integration is not properly configured. "
                    "Access token is missing. Please reconnect the repository."
                )
            
            return integration
            
        except GitHubIntegration.DoesNotExist:
            logger.error(f"No active GitHub integration found for project {project.id}")
            raise ValueError(
                "No GitHub repository connected. "
                "To generate diagrams, connect a GitHub repository first. "
                "Go to Project Settings → GitHub Integration and connect a repository."
            )
    
    def _analyze_github_repository(self, integration):
        """
        Analyze code from GitHub repository.
        
        Args:
            integration: GitHubIntegration instance
            
        Returns:
            Analysis result with classes, dependencies, etc.
            
        Raises:
            ValueError: On analysis errors
        """
        logger.info(
            f"Analyzing repository: {integration.repository_owner}/{integration.repository_name}"
        )
        
        try:
            # Fetch code from GitHub
            fetcher = GitHubCodeFetcher(integration)
            python_files = fetcher.list_python_files()
            
            # Limit to 100 files for performance
            files_content = fetcher.fetch_multiple_files(python_files, max_files=100)
            
            if not files_content:
                raise ValueError(
                    "No Python files could be fetched from repository. "
                    "Please check repository access and try again."
                )
            
            # Analyze Python code
            analyzer = PythonCodeAnalyzer()
            analysis = analyzer.analyze_repository(files_content)
            
            logger.info(
                f"Analysis complete: {analysis['stats']['total_classes']} classes found"
            )
            
            return analysis
            
        except ValueError as e:
            # Re-raise ValueError as-is (these are user-facing errors)
            raise
        except Exception as e:
            logger.error(f"Error analyzing repository: {str(e)}", exc_info=True)
            raise ValueError(
                f"Failed to analyze repository: {str(e)}. "
                "Please check GitHub integration and try again."
            )
