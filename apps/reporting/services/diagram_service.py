import hashlib
import inspect
import logging
from datetime import timedelta
from typing import Dict, Optional, Tuple

from django.apps import apps
from django.db import models as django_models
from django.utils import timezone

from .angular_analyzer import AngularAnalyzer
from .angular_diagram_generator import AngularDiagramGenerator
from .architecture_generator import ArchitectureGenerator
from .diagram_data_service import DiagramDataService
from .github_code_fetcher import GitHubCodeFetcher
from .python_code_analyzer import PythonCodeAnalyzer

logger = logging.getLogger(__name__)


class DiagramService:
    """
    Orchestrates diagram generation with caching.

    Uses modular diagram generators from diagram_generators.py.
    """

    def __init__(self):
        # Dynamic TTL based on diagram type
        self.cache_ttl_minutes = {
            "workflow": 30,  # Less dynamic
            "dependency": 10,  # More dynamic with filters
            "roadmap": 15,  # Medium dynamism
            "uml": 60,  # Very stable
            "architecture": 60,  # Very stable
        }

        # Initialize data service for JSON generation
        self.data_service = DiagramDataService()

    def generate_workflow_diagram(self, project, force_refresh: bool = False) -> Dict:
        """
        Generate workflow diagram as JSON data structure.

        Returns dict with structured data for frontend rendering.
        No SVG generation - frontend handles visualization.
        """
        # Generate cache key with data version hash
        version_hash = self._get_data_version_hash(project, "workflow")
        cache_key = self._generate_cache_key("workflow", project.id, version_hash)

        # Check cache unless force refresh
        if not force_refresh:
            cached = self._get_cached_diagram(cache_key)
            if cached:
                cached["cache_age"] = self._get_cache_age(cache_key)
                logger.debug(
                    f"Workflow diagram cache HIT (age: {cached.get('cache_age')}s)"
                )
                return cached

        # Generate JSON data structure
        import time

        start_time = time.time()
        data = self.data_service.get_workflow_data(project)
        generation_time = int((time.time() - start_time) * 1000)  # milliseconds

        logger.info(
            f"Generated workflow data: {data['metadata']['status_count']} statuses, "
            f"{data['metadata']['transition_count']} transitions"
        )
        logger.debug(f"Data type before caching: {type(data).__name__}")

        # Cache the data as dict (JSONField handles serialization)
        self._cache_diagram(cache_key, data, "workflow", project, "json")

        return {
            "diagram_type": "workflow",
            "data": data,  # Return dict directly - DRF handles JSON serialization
            "format": "json",
            "cached": False,
            "generation_time_ms": generation_time,
            "cache_key": cache_key,
        }

    def generate_dependency_diagram(
        self, project, filters=None, force_refresh: bool = False
    ) -> Dict:
        """
        Generate dependency graph as JSON data structure.

        Args:
            project: Project instance
            filters: Dict with optional filter keys:
                - sprint_id: Filter by sprint UUID or 'backlog'
                - status_ids: List of status UUIDs
                - priorities: List of priority strings ['P1', 'P2', etc]
                - assignee_id: Assignee UUID or 'unassigned'
                - issue_type_ids: List of issue type UUIDs
                - search: Search term for title/key

        Returns:
            Dict with structured data for frontend rendering
        """
        # Generate cache key including filters and version hash
        filter_str = str(sorted(filters.items())) if filters else ""
        version_hash = self._get_data_version_hash(project, "dependency")
        cache_key = self._generate_cache_key(
            f"dependency_{filter_str}", project.id, version_hash
        )

        # Check cache unless force refresh
        if not force_refresh:
            cached = self._get_cached_diagram(cache_key)
            if cached:
                cached["cache_age"] = self._get_cache_age(cache_key)
                return cached

        # Generate JSON data structure with filters
        import time

        start_time = time.time()
        data = self.data_service.get_dependency_data(project, filters)
        generation_time = int((time.time() - start_time) * 1000)

        logger.info(
            f"Generated dependency data: {data['metadata']['issue_count']} issues, "
            f"{data['metadata']['dependency_count']} dependencies"
        )
        logger.debug(f"Data type before caching: {type(data).__name__}")

        # Cache the data as dict (JSONField handles serialization)
        self._cache_diagram(cache_key, data, "dependency", project, "json")

        return {
            "diagram_type": "dependency",
            "data": data,  # Return dict directly - DRF handles JSON serialization
            "format": "json",
            "cached": False,
            "generation_time_ms": generation_time,
            "cache_key": cache_key,
            "filters": filters,
        }

    def generate_roadmap(self, project, force_refresh: bool = False) -> Dict:
        """
        Generate roadmap timeline as JSON data structure.

        Returns dict with structured data for frontend rendering.
        No SVG generation - frontend handles visualization.
        """
        # Generate cache key with version hash
        version_hash = self._get_data_version_hash(project, "roadmap")
        cache_key = self._generate_cache_key("roadmap", project.id, version_hash)

        # Check cache unless force refresh
        if not force_refresh:
            cached = self._get_cached_diagram(cache_key)
            if cached:
                cached["cache_age"] = self._get_cache_age(cache_key)
                return cached

        # Generate JSON data structure
        import time

        start_time = time.time()
        data = self.data_service.get_roadmap_data(project)
        generation_time = int((time.time() - start_time) * 1000)

        logger.info(
            f"Generated roadmap data: {data['metadata']['sprint_count']} sprints"
        )
        logger.debug(f"Data type before caching: {type(data).__name__}")

        # Cache the data as dict (JSONField handles serialization)
        self._cache_diagram(cache_key, data, "roadmap", project, "json")

        return {
            "diagram_type": "roadmap",
            "data": data,  # Return dict directly - DRF handles JSON serialization
            "format": "json",
            "cached": False,
            "generation_time_ms": generation_time,
            "cache_key": cache_key,
        }

    def generate_uml_diagram(
        self, project, diagram_format: str = "json", parameters: Dict = None
    ) -> Dict:
        """
        Generate UML diagram by analyzing Django ORM models in the application.

        Uses Django internals (apps.get_models()) to introspect actual database models.
        This shows the REAL structure of ficct-scrum-backend, not GitHub repository code.  # noqa: E501

        Args:
            project: Project instance (used for context, not filtering)
            diagram_format: Output format (json or svg)
            parameters: Additional parameters

        Returns:
            UML diagram data with Django models only (User, Project, Issue, etc.)

        Raises:
            ValueError: On analysis errors
        """
        logger.info("Generating UML diagram - analyzing local Django models")

        # Check cache first
        cache_key = self._generate_cache_key("uml", project.id)
        cached = self._get_cached_diagram(cache_key)
        if cached:
            logger.info("Returning cached UML diagram")
            return cached

        # Analyze LOCAL Django models using Django internals
        analysis = self._analyze_local_django_models()

        # Build UML JSON structure
        uml_data = self._build_uml_json(analysis, project)

        import json

        data_str = json.dumps(uml_data, indent=2)

        # Cache the result
        self._cache_diagram(cache_key, data_str, "uml", project, "json")

        logger.info(
            f"UML diagram generated: {analysis['total_models']} models, "
            f"{analysis['total_relationships']} relationships"
        )

        return {
            "diagram_type": "uml",
            "data": data_str,
            "format": "json",
            "cached": False,
        }

    def generate_architecture_diagram(
        self, project, diagram_format: str = "json", parameters: Dict = None
    ) -> Dict:
        """
        Generate architecture diagram by analyzing LOCAL Django application.

        Classifies components by architectural responsibility:
        - Presentation Layer: ViewSets, Serializers
        - Business Logic Layer: Services, Managers
        - Data Access Layer: Models
        - Infrastructure Layer: Middleware, Auth

        Args:
            project: Project instance
            diagram_format: Output format (json or svg)
            parameters: Additional parameters

        Returns:
            Architecture diagram data
        """
        logger.info(f"Generating architecture diagram for project {project.name}")

        # Check cache first
        cache_key = self._generate_cache_key("architecture", project.id)
        cached = self._get_cached_diagram(cache_key)
        if cached:
            logger.info("Returning cached architecture diagram")
            return cached

        # Generate architecture from LOCAL Django app
        generator = ArchitectureGenerator()
        arch_data = generator.generate_architecture_json(project)

        import json

        data_str = json.dumps(arch_data, indent=2)

        # Cache the result
        self._cache_diagram(cache_key, data_str, "architecture", project, "json")

        logger.info("Architecture diagram generated successfully")

        return {
            "diagram_type": "architecture",
            "data": data_str,
            "format": "json",
            "cached": False,
        }

    def generate_angular_diagram(
        self,
        project,
        diagram_type: str,
        diagram_format: str = "json",
        parameters: Dict = None,
    ) -> Dict:
        """
        Generate Angular/TypeScript diagram.

        Supports:
        - component_hierarchy: Component tree
        - service_dependencies: Service dependency graph
        - module_graph: Module imports/exports
        - routing_structure: Route tree

        Args:
            project: Project instance
            diagram_type: Type of Angular diagram
            diagram_format: Output format (json)
            parameters: Additional parameters

        Returns:
            Angular diagram data

        Raises:
            ValueError: On analysis errors
        """
        logger.info(
            f"Generating Angular {diagram_type} diagram for project {project.name}"
        )

        # Check cache first
        cache_key = self._generate_cache_key(f"angular_{diagram_type}", project.id)
        cached = self._get_cached_diagram(cache_key)
        if cached:
            logger.info("Returning cached Angular diagram")
            return cached

        # Get GitHub integration and analyze Angular code
        integration = self._get_github_integration(project)

        try:
            # Fetch TypeScript files from GitHub
            fetcher = GitHubCodeFetcher(integration)

            # Get Angular-specific files
            all_files = fetcher.list_files()

            ts_files = [
                f for f in all_files if f.endswith(".ts") and not f.endswith(".spec.ts")
            ]

            if not ts_files:
                raise ValueError(
                    "No TypeScript files found in repository. "
                    "Please ensure this is an Angular project."
                )

            logger.info(f"Found {len(ts_files)} TypeScript files")

            # Fetch file contents (limit to 100 files)
            files_content = fetcher.fetch_multiple_files(ts_files, max_files=100)

            if not files_content:
                raise ValueError(
                    "Could not fetch TypeScript files. "
                    "Please check repository access."
                )

            # Analyze Angular code
            analyzer = AngularAnalyzer()
            analysis = analyzer.analyze_angular_code(files_content)

            # Generate specific diagram type
            generator = AngularDiagramGenerator()

            if diagram_type == "component_hierarchy":
                diagram_data = generator.generate_component_hierarchy(analysis)
            elif diagram_type == "service_dependencies":
                diagram_data = generator.generate_service_dependencies(analysis)
            elif diagram_type == "module_graph":
                diagram_data = generator.generate_module_graph(analysis)
            elif diagram_type == "routing_structure":
                diagram_data = generator.generate_routing_structure(analysis)
            else:
                raise ValueError(
                    f"Unknown Angular diagram type: {diagram_type}. "
                    f"Supported: component_hierarchy, service_dependencies, "
                    f"module_graph, routing_structure"
                )

            import json

            data_str = json.dumps(diagram_data, indent=2)

            # Cache the result
            self._cache_diagram(
                cache_key, data_str, f"angular_{diagram_type}", project, "json"
            )

            logger.info(f"Angular {diagram_type} diagram generated successfully")

            return {
                "diagram_type": f"angular_{diagram_type}",
                "data": data_str,
                "format": "json",
                "cached": False,
            }

        except ValueError as e:  # noqa: F841
            # Re-raise ValueError as-is
            raise
        except Exception as e:
            logger.error(f"Error generating Angular diagram: {str(e)}", exc_info=True)
            raise ValueError(
                f"Failed to generate Angular diagram: {str(e)}. "
                "Please check GitHub integration and ensure this is an Angular project."
            )

    def _generate_cache_key(
        self, diagram_type: str, project_id, version_hash: str = ""
    ) -> str:
        """Generate cache key with version hash for automatic invalidation."""
        data = f"diagram:{project_id}:{diagram_type}:{version_hash}"
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
        self, cache_key: str, data, diagram_type: str, project, format: str
    ):
        """
        Cache diagram data.

        Args:
            cache_key: Unique cache identifier
            data: Diagram data (dict for JSON format, str for SVG/PNG)
            diagram_type: Type of diagram
            project: Project instance
            format: Output format (json, svg, png)
        """
        from apps.reporting.models import DiagramCache

        # Get TTL for this diagram type
        ttl_minutes = self.cache_ttl_minutes.get(diagram_type, 30)
        expires_at = timezone.now() + timedelta(minutes=ttl_minutes)

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

        logger.debug(
            f"Cached {diagram_type} diagram with key {cache_key[:8]}... (TTL: {ttl_minutes}min)"  # noqa: E501
        )

    def _get_data_version_hash(self, project, diagram_type: str) -> str:
        """
        Generate version hash based on relevant data timestamps.
        When data changes, hash changes, invalidating cache automatically.

        Args:
            project: Project instance
            diagram_type: Type of diagram (workflow, dependency, roadmap)

        Returns:
            MD5 hash of timestamps
        """
        from django.db.models import Max

        from apps.projects.models import Issue, Sprint, WorkflowStatus

        timestamps = []

        # Common: Project modified timestamp
        if hasattr(project, "updated_at"):
            timestamps.append(str(project.updated_at))

        # Workflow: Status and transition changes
        if diagram_type == "workflow":
            status_updated = WorkflowStatus.objects.filter(project=project).aggregate(
                Max("updated_at")
            )["updated_at__max"]
            if status_updated:
                timestamps.append(str(status_updated))

        # Dependency and Roadmap: Issue changes
        if diagram_type in ["dependency", "roadmap"]:
            issue_updated = Issue.objects.filter(
                project=project, is_active=True
            ).aggregate(Max("updated_at"))["updated_at__max"]
            if issue_updated:
                timestamps.append(str(issue_updated))

        # Roadmap: Sprint changes
        if diagram_type == "roadmap":
            sprint_updated = Sprint.objects.filter(project=project).aggregate(
                Max("updated_at")
            )["updated_at__max"]
            if sprint_updated:
                timestamps.append(str(sprint_updated))

        # Generate hash from timestamps
        version_data = (
            "|".join(timestamps) if timestamps else str(timezone.now().date())
        )
        return hashlib.md5(version_data.encode()).hexdigest()[:8]

    def _get_cache_age(self, cache_key: str) -> int:
        """
        Get age of cached diagram in seconds.

        Args:
            cache_key: Cache key

        Returns:
            Age in seconds, or 0 if not found
        """
        from apps.reporting.models import DiagramCache

        try:
            cache = DiagramCache.objects.get(cache_key=cache_key)
            age = (timezone.now() - cache.generated_at).total_seconds()
            return int(age)
        except DiagramCache.DoesNotExist:
            return 0

    @staticmethod
    def invalidate_project_cache(project):
        """
        Invalidate all cached diagrams for a project.
        Call this when project data changes significantly.

        Args:
            project: Project instance
        """
        from apps.reporting.models import DiagramCache

        deleted_count = DiagramCache.objects.filter(project=project).delete()[0]
        logger.info(
            f"Invalidated {deleted_count} cached diagrams for project {project.id}"
        )
        return deleted_count

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
            integration = GitHubIntegration.objects.get(project=project, is_active=True)

            # Validate that access token exists (is_connected is a property)
            if not integration.access_token:
                logger.error(
                    f"GitHub integration exists but has no access token for project {project.id}"  # noqa: E501
                )
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
            f"Analyzing repository: {integration.repository_owner}/{integration.repository_name}"  # noqa: E501
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

        except ValueError as e:  # noqa: F841
            # Re-raise ValueError as-is (these are user-facing errors)
            raise
        except Exception as e:
            logger.error(f"Error analyzing repository: {str(e)}", exc_info=True)
            raise ValueError(
                f"Failed to analyze repository: {str(e)}. "
                "Please check GitHub integration and try again."
            )

    def _is_valid_django_model(self, model_class) -> Tuple[bool, str]:
        """
        Universal validation: Determine if a class is a valid Django ORM model.

        This method is LOCATION-AGNOSTIC - it works regardless of file structure.
        Uses Django internals and Python introspection to validate.

        Validation Criteria (ALL must pass):
        1. Inherits from django.db.models.Model (but not Model itself)
        2. Has _meta attribute (Django models signature)
        3. Has valid app_label (Django assigns this automatically)
        4. Is NOT abstract model (_meta.abstract == False)
        5. Name does NOT contain excluded patterns
        6. Name does NOT start with reserved words

        Args:
            model_class: Python class to validate

        Returns:
            Tuple of (is_valid: bool, reason: str)
            - (True, "valid") if all checks pass
            - (False, "reason") if any check fails
        """
        class_name = model_class.__name__

        # VALIDATION 1: Must inherit from models.Model (but not BE models.Model)
        try:
            if not issubclass(model_class, django_models.Model):
                return (False, "does not inherit from models.Model")

            # Exclude the base Model class itself
            if model_class == django_models.Model:
                return (False, "is base Model class")
        except TypeError:
            return (False, "not a class or inheritance check failed")

        # VALIDATION 2: Must have _meta attribute (Django models signature)
        if not hasattr(model_class, "_meta"):
            return (False, "missing _meta attribute")

        # VALIDATION 3: Must have valid app_label (Django assigns automatically)
        try:
            app_label = model_class._meta.app_label
            if not app_label:
                return (False, "missing app_label")
        except AttributeError:
            return (False, "cannot access _meta.app_label")

        # VALIDATION 4: Must NOT be abstract
        if hasattr(model_class._meta, "abstract") and model_class._meta.abstract:
            return (False, "is abstract model")

        # VALIDATION 5: Name must NOT contain excluded patterns
        excluded_patterns = [
            "test",
            "factory",
            "fixture",
            "mock",
            "admin",
            "middleware",
            "migration",
        ]
        class_name_lower = class_name.lower()
        for pattern in excluded_patterns:
            if pattern in class_name_lower:
                return (False, f"contains excluded pattern: {pattern}")

        # VALIDATION 6: Name must NOT start with reserved words
        if class_name.startswith("Abstract"):
            return (False, "starts with 'Abstract' (likely base class)")
        if class_name.startswith("Base"):
            return (False, "starts with 'Base' (likely base class)")

        # ALL VALIDATIONS PASSED
        return (True, "valid")

    def _analyze_local_django_models(self) -> Dict:
        """
        Analyze Django ORM models using Django internals (LOCATION-AGNOSTIC).

        Strategy:
        1. Use django.apps.get_models() as PRIMARY SOURCE
           - Returns ONLY registered Django models
           - Does NOT depend on file location
           - Django already identified them correctly

        2. Apply universal validation to ensure quality
        3. Extract information for each valid model
        4. Build relationships between models

        Returns:
            Dict with:
            - models: List of model information dicts
            - relationships: List of relationship dicts
            - total_models: Count of valid models
            - total_relationships: Count of relationships
            - excluded_count: Count of excluded classes
            - exclusion_breakdown: Dict of exclusion reasons
        """
        logger.info("Starting Django model analysis using apps.get_models()")

        models_info = []
        relationships = []
        excluded_count = 0
        exclusion_breakdown = {}

        # Get ALL registered Django models (PRIMARY SOURCE)
        all_models = apps.get_models()
        logger.info(f"Found {len(all_models)} registered Django models")

        # Validate and extract info for each model
        for model_class in all_models:
            is_valid, reason = self._is_valid_django_model(model_class)

            if not is_valid:
                excluded_count += 1
                exclusion_breakdown[reason] = exclusion_breakdown.get(reason, 0) + 1
                logger.debug(f"Excluded {model_class.__name__}: {reason}")
                continue

            # Extract model information
            model_info = self._extract_model_info(model_class)
            models_info.append(model_info)

            # Extract relationships for this model
            model_relationships = self._extract_model_relationships(model_class)
            relationships.extend(model_relationships)

        # Log analysis results
        logger.info(
            f"Django Model Analysis Complete:\n"
            f"  - Valid models found: {len(models_info)}\n"
            f"  - Excluded classes: {excluded_count}\n"
            f"  - Total relationships: {len(relationships)}"
        )

        if exclusion_breakdown:
            logger.info("Exclusion breakdown:")
            for reason, count in sorted(exclusion_breakdown.items()):
                logger.info(f"  * {reason}: {count}")

        return {
            "models": models_info,
            "relationships": relationships,
            "total_models": len(models_info),
            "total_relationships": len(relationships),
            "excluded_count": excluded_count,
            "exclusion_breakdown": exclusion_breakdown,
        }

    def _extract_model_info(self, model_class) -> Dict:
        """
        Extract complete information from a Django model.

        Extracts:
        - Basic info: name, app_label, table name
        - Attributes: from _meta.fields (name, type, constraints)
        - Methods: from inspect (public and private)
        - Parent classes: from __bases__ (Django models only)

        Args:
            model_class: Django model class

        Returns:
            Dict with model information
        """
        class_name = model_class.__name__
        app_label = model_class._meta.app_label
        table_name = model_class._meta.db_table

        # Extract attributes from Django fields
        attributes = []
        for field in model_class._meta.get_fields():
            # Skip reverse relations
            if hasattr(field, "related_model") and field.related_model:
                if hasattr(field, "remote_field") and field.remote_field:
                    continue

            attr_info = {
                "name": field.name,
                "type": (
                    field.get_internal_type()
                    if hasattr(field, "get_internal_type")
                    else "Unknown"
                ),
                "required": not getattr(field, "null", True),
                "primary_key": getattr(field, "primary_key", False),
            }
            attributes.append(attr_info)

        # Extract methods using inspect
        methods = []
        for name, method in inspect.getmembers(
            model_class, predicate=inspect.isfunction
        ):
            # Skip Django internal methods
            if name.startswith("_") and name not in ["__str__", "__repr__"]:
                continue

            # Determine visibility
            visibility = "private" if name.startswith("_") else "public"

            methods.append({"name": name, "visibility": visibility})

        # Extract parent classes (Django models only)
        parent_classes = []
        for base in model_class.__bases__:
            # Only include if it's a Django model (not Model itself)
            if hasattr(base, "_meta") and base != django_models.Model:
                parent_classes.append(base.__name__)

        return {
            "name": class_name,
            "app_label": app_label,
            "table_name": table_name,
            "module": f"{app_label}.models",
            "attributes": attributes,
            "methods": methods,
            "parent_classes": parent_classes,
        }

    def _extract_model_relationships(self, model_class) -> list:
        """
        Extract relationships (ForeignKey, ManyToMany, OneToOne) from model.

        Args:
            model_class: Django model class

        Returns:
            List of relationship dicts
        """
        relationships = []
        class_name = model_class.__name__

        for field in model_class._meta.get_fields():
            relationship_type = None
            target_model = None

            # ForeignKey (many-to-one)
            if isinstance(field, django_models.ForeignKey):
                relationship_type = "many_to_one"
                target_model = field.related_model.__name__

            # ManyToManyField
            elif isinstance(field, django_models.ManyToManyField):
                relationship_type = "many_to_many"
                target_model = field.related_model.__name__

            # OneToOneField
            elif isinstance(field, django_models.OneToOneField):
                relationship_type = "one_to_one"
                target_model = field.related_model.__name__

            if relationship_type and target_model:
                relationships.append(
                    {
                        "from": class_name,
                        "to": target_model,
                        "type": relationship_type,
                        "field": field.name,
                    }
                )

        return relationships

    def _build_uml_json(self, analysis: Dict, project) -> Dict:
        """
        Build final UML JSON structure from analysis.

        Args:
            analysis: Result from _analyze_local_django_models()
            project: Project instance for context

        Returns:
            UML JSON structure
        """
        # PRE-OUTPUT VALIDATION (7 checks)
        models_count = analysis["total_models"]

        # Check 1: Valid model count (15-50 is reasonable for Django apps)
        if not (15 <= models_count <= 50):
            logger.warning(
                f"Unusual model count: {models_count}. "
                f"Expected 15-50. Verify results."
            )

        # Check 2-6: No excluded patterns in final models
        excluded_patterns = ["Test", "Middleware", "Admin", "Factory", "Mock"]
        for model in analysis["models"]:
            model_name = model["name"]
            for pattern in excluded_patterns:
                if pattern.lower() in model_name.lower():
                    raise ValueError(
                        f"Validation failed: Model '{model_name}' contains "
                        f"excluded pattern '{pattern}'. This should not happen."
                    )

        # Check 7: All models have app_label
        for model in analysis["models"]:
            if not model.get("app_label"):
                raise ValueError(
                    f"Validation failed: Model '{model['name']}' missing app_label"
                )

        logger.info("Pre-output validation passed")

        return {
            "diagram_type": "class",
            "project": {
                "id": str(project.id),
                "name": project.name,
                "key": project.key,
            },
            "classes": analysis["models"],
            "relationships": analysis["relationships"],
            "metadata": {
                "generated_at": timezone.now().isoformat(),
                "total_classes": analysis["total_models"],
                "total_relationships": analysis["total_relationships"],
                "excluded_count": analysis["excluded_count"],
                "exclusion_breakdown": analysis["exclusion_breakdown"],
                "analysis_type": "django_orm_models_local",
                "description": "Django ORM models from ficct-scrum-backend application",
            },
        }
