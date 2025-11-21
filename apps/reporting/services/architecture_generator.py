"""
Architecture Generator

Analyzes LOCAL Django application architecture by component RESPONSIBILITY.
Uses Django introspection to classify ViewSets, Services, Models, etc.
"""

import inspect
import logging
from typing import Dict, List

from django.apps import apps
from django.utils import timezone

from rest_framework import serializers as drf_serializers
from rest_framework import viewsets

logger = logging.getLogger(__name__)


class ArchitectureGenerator:
    """
    Generates Architecture Diagrams from LOCAL Django application.

    Classifies components by RESPONSIBILITY (what they do), not file location.
    """

    # Apps to analyze (exclude Django/DRF internal apps)
    EXCLUDED_APPS = [
        "django",
        "rest_framework",
        "drf_spectacular",
        "corsheaders",
        "admin",
        "auth",
        "contenttypes",
        "sessions",
        "messages",
        "staticfiles",
        "channels",
        "celery",
    ]

    def generate_architecture_json(self, project) -> Dict:
        """
        Generate architecture diagram JSON from LOCAL Django app analysis.

        Args:
            project: Project instance for context

        Returns:
            Architecture diagram in JSON format with 4 layers
        """
        logger.info("Generating architecture diagram from local Django application")

        # Analyze LOCAL Django application by architectural layers
        layers = self._analyze_django_architecture()

        # Build connections between components
        connections = self._build_layer_connections(layers)

        result = {
            "project": {
                "id": str(project.id),
                "name": project.name,
                "key": project.key,
            },
            "architecture_pattern": self._detect_architecture_pattern(layers),
            "layers": layers,
            "connections": connections,
            "metadata": {
                "generated_at": timezone.now().isoformat(),
                "total_layers": len(layers),
                "total_components": sum(len(layer["components"]) for layer in layers),
                "total_connections": len(connections),
                "analysis_type": "django_local_architecture",
            },
        }

        logger.info(
            f"Architecture diagram generated: {len(layers)} layers, "
            f"{result['metadata']['total_components']} components, "
            f"{len(connections)} connections"
        )

        return result

    def _analyze_django_architecture(self) -> List[Dict]:
        """
        Analyze Django application and classify components by architectural layers.

        Uses Django introspection to identify:
        - Presentation Layer: ViewSets, Serializers
        - Business Logic Layer: Services, Managers, Validators
        - Data Access Layer: Models
        - Infrastructure Layer: Middleware, Authentication, Integrations

        Returns:
            List of layers with components
        """
        logger.info("Analyzing Django architecture by component responsibility")

        presentation_components = []
        business_components = []
        data_components = []
        infrastructure_components = []

        # Iterate through all Django apps
        for app_config in apps.get_app_configs():
            app_label = app_config.label

            # Skip excluded apps
            if any(excluded in app_label for excluded in self.EXCLUDED_APPS):
                continue

            logger.debug(f"Analyzing app: {app_label}")

            # Get all classes from this app's modules
            try:
                # Analyze viewsets module
                if hasattr(app_config.module, "viewsets"):
                    viewsets_module = app_config.module.viewsets
                    presentation_components.extend(
                        self._extract_viewsets(viewsets_module, app_label)
                    )

                # Analyze serializers module
                if hasattr(app_config.module, "serializers"):
                    serializers_module = app_config.module.serializers
                    presentation_components.extend(
                        self._extract_serializers(serializers_module, app_label)
                    )

                # Analyze services module
                if hasattr(app_config.module, "services"):
                    services_module = app_config.module.services
                    business_components.extend(
                        self._extract_services(services_module, app_label)
                    )

                # Analyze models
                models = app_config.get_models()
                data_components.extend(self._extract_models(models, app_label))

                # Analyze middleware (if exists)
                if hasattr(app_config.module, "middleware"):
                    middleware_module = app_config.module.middleware
                    infrastructure_components.extend(
                        self._extract_middleware(middleware_module, app_label)
                    )

            except Exception as e:
                logger.warning(f"Error analyzing app {app_label}: {str(e)}")
                continue

        # Build layers list
        layers = []

        if presentation_components:
            layers.append(
                {
                    "name": "Presentation Layer",
                    "description": "Handles HTTP requests, API endpoints, data serialization",  # noqa: E501
                    "components": presentation_components,
                }
            )

        if business_components:
            layers.append(
                {
                    "name": "Business Logic Layer",
                    "description": "Contains business rules, services, and domain logic",  # noqa: E501
                    "components": business_components,
                }
            )

        if data_components:
            layers.append(
                {
                    "name": "Data Access Layer",
                    "description": "Manages data persistence and database models",
                    "components": data_components,
                }
            )

        if infrastructure_components:
            layers.append(
                {
                    "name": "Infrastructure Layer",
                    "description": "Cross-cutting concerns: auth, middleware, integrations",  # noqa: E501
                    "components": infrastructure_components,
                }
            )

        logger.info(
            f"Architecture analysis complete: {len(layers)} layers, "
            f"{sum(len(l['components']) for l in layers)} total components"
        )

        return layers

    def _extract_viewsets(self, module, app_label: str) -> List[Dict]:
        """Extract ViewSet components from module."""
        components = []

        for name in dir(module):
            try:
                obj = getattr(module, name)
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, viewsets.ViewSet)
                    and obj != viewsets.ViewSet
                ):
                    # Skip if from another module
                    if obj.__module__ != module.__name__:
                        continue

                    components.append(
                        {
                            "name": name,
                            "type": "viewset",
                            "app": app_label,
                            "description": f"API ViewSet in {app_label}",
                            "methods_count": len(
                                [m for m in dir(obj) if not m.startswith("_")]
                            ),
                        }
                    )
            except Exception:
                continue

        return components

    def _extract_serializers(self, module, app_label: str) -> List[Dict]:
        """Extract Serializer components from module."""
        components = []

        for name in dir(module):
            try:
                obj = getattr(module, name)
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, drf_serializers.Serializer)
                    and obj != drf_serializers.Serializer
                ):
                    if obj.__module__ != module.__name__:
                        continue

                    components.append(
                        {
                            "name": name,
                            "type": "serializer",
                            "app": app_label,
                            "description": f"Data Serializer in {app_label}",
                            "methods_count": len(
                                [m for m in dir(obj) if not m.startswith("_")]
                            ),
                        }
                    )
            except Exception:
                continue

        return components

    def _extract_services(self, module, app_label: str) -> List[Dict]:
        """Extract Service components from module."""
        components = []

        for name in dir(module):
            try:
                obj = getattr(module, name)
                if inspect.isclass(obj):
                    if obj.__module__ != module.__name__:
                        continue

                    # Service classes typically have 'Service' in name
                    if "Service" in name or "Manager" in name or "Handler" in name:
                        components.append(
                            {
                                "name": name,
                                "type": "service",
                                "app": app_label,
                                "description": f"Business Logic Service in {app_label}",
                                "methods_count": len(
                                    [m for m in dir(obj) if not m.startswith("_")]
                                ),
                            }
                        )
            except Exception:
                continue

        return components

    def _extract_models(self, models, app_label: str) -> List[Dict]:
        """Extract Model components."""
        components = []

        for model in models:
            # Skip abstract models
            if hasattr(model._meta, "abstract") and model._meta.abstract:
                continue

            components.append(
                {
                    "name": model.__name__,
                    "type": "model",
                    "app": app_label,
                    "description": f"Database Model in {app_label}",
                    "methods_count": len(
                        [m for m in dir(model) if not m.startswith("_")]
                    ),
                }
            )

        return components

    def _extract_middleware(self, module, app_label: str) -> List[Dict]:
        """Extract Middleware components from module."""
        components = []

        for name in dir(module):
            try:
                obj = getattr(module, name)
                if inspect.isclass(obj) and "Middleware" in name:
                    if obj.__module__ != module.__name__:
                        continue

                    components.append(
                        {
                            "name": name,
                            "type": "middleware",
                            "app": app_label,
                            "description": f"Middleware component in {app_label}",
                            "methods_count": len(
                                [m for m in dir(obj) if not m.startswith("_")]
                            ),
                        }
                    )
            except Exception:
                continue

        return components

    def _build_layer_connections(self, layers: List[Dict]) -> List[Dict]:
        """
        Build architectural connections between layers.

        Standard flow in Django:
        - Presentation Layer (ViewSets) → uses → Business Layer (Services)
        - Presentation Layer (ViewSets) → accesses → Data Layer (Models)
        - Business Layer (Services) → accesses → Data Layer (Models)
        - Infrastructure Layer (Middleware) → intercepts → Presentation Layer

        Returns:
            List of connections between layers
        """
        connections = []

        # Find layer indices
        layer_map = {layer["name"]: layer for layer in layers}

        # Presentation → Business Logic
        if "Presentation Layer" in layer_map and "Business Logic Layer" in layer_map:
            pres_comps = layer_map["Presentation Layer"]["components"]
            bus_comps = layer_map["Business Logic Layer"]["components"]

            # ViewSets use Services
            for pres in pres_comps:
                if pres["type"] == "viewset" and bus_comps:
                    # Create generic connection
                    connections.append(
                        {
                            "from": pres["name"],
                            "to": f"{pres['app'].title()} Services",
                            "type": "uses",
                            "from_layer": "Presentation Layer",
                            "to_layer": "Business Logic Layer",
                        }
                    )
                    break  # One example per layer

        # Presentation → Data Access
        if "Presentation Layer" in layer_map and "Data Access Layer" in layer_map:
            pres_comps = layer_map["Presentation Layer"]["components"]
            data_comps = layer_map["Data Access Layer"]["components"]

            if pres_comps and data_comps:
                connections.append(
                    {
                        "from": pres_comps[0]["name"],
                        "to": data_comps[0]["name"],
                        "type": "accesses",
                        "from_layer": "Presentation Layer",
                        "to_layer": "Data Access Layer",
                    }
                )

        # Business Logic → Data Access
        if "Business Logic Layer" in layer_map and "Data Access Layer" in layer_map:
            bus_comps = layer_map["Business Logic Layer"]["components"]
            data_comps = layer_map["Data Access Layer"]["components"]

            if bus_comps and data_comps:
                connections.append(
                    {
                        "from": bus_comps[0]["name"],
                        "to": data_comps[0]["name"],
                        "type": "queries",
                        "from_layer": "Business Logic Layer",
                        "to_layer": "Data Access Layer",
                    }
                )

        return connections

    def _detect_architecture_pattern(self, layers: List[Dict]) -> str:
        """
        Detect architecture pattern based on layers.

        Args:
            layers: List of layers

        Returns:
            Architecture pattern name
        """
        layer_names = {layer["name"] for layer in layers}

        # Check for layered architecture
        has_presentation = any("Presentation" in name for name in layer_names)
        has_business = any(
            "Business" in name or "Logic" in name for name in layer_names
        )
        has_data = any("Data" in name for name in layer_names)

        if has_presentation and has_business and has_data:
            return "Layered Architecture (3-tier)"
        elif has_business and has_data:
            return "Layered Architecture (2-tier)"
        elif len(layers) >= 4:
            return "Multi-layer Architecture"
        else:
            return "Simple Architecture"

    def _get_layer_description(self, layer_name: str) -> str:
        """Get description for a layer."""
        descriptions = {
            "Presentation Layer": "Handles HTTP requests, API endpoints, views, and serializers",  # noqa: E501
            "Business Logic Layer": "Contains business rules, services, and use cases",
            "Data Access Layer": "Manages data persistence, models, and repositories",
            "Utilities": "Common utilities, helpers, and shared functions",
            "Integration Layer": "External service integrations and adapters",
        }
        return descriptions.get(layer_name, "Application components")

    def _extract_module_display_name(self, file_path: str) -> str:
        """Extract display name from file path."""
        name = file_path.split("/")[-1].replace(".py", "")
        return name.replace("_", " ").title()
