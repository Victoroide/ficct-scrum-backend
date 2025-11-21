"""
Angular Diagram Generators.

Generates various diagrams from Angular code analysis:
- Component hierarchy tree
- Service dependency graph
- Module dependency graph
- Routing structure
"""

import logging
from typing import Dict, List

from django.utils import timezone

logger = logging.getLogger(__name__)


class AngularDiagramGenerator:
    """
    Generates diagrams from Angular code analysis.

    Supports:
    - Component hierarchy (parent-child relationships)
    - Service dependencies (injection graph)
    - Module dependencies (imports/exports)
    - Routing structure (route tree)
    """

    def generate_component_hierarchy(self, analysis: Dict) -> Dict:
        """
        Generate component hierarchy diagram.

        Args:
            analysis: Output from AngularAnalyzer

        Returns:
            Component hierarchy in JSON format
        """
        logger.info("[ANGULAR DIAGRAM] Generating component hierarchy")

        components = analysis.get("components", [])

        # Build hierarchy based on template usage
        hierarchy = self._build_component_hierarchy(components)

        return {
            "diagram_type": "component_hierarchy",
            "components": hierarchy,
            "metadata": {
                "generated_at": timezone.now().isoformat(),
                "total_components": len(components),
                "analysis_type": "angular_components",
            },
        }

    def generate_service_dependencies(self, analysis: Dict) -> Dict:
        """
        Generate service dependency graph.

        Args:
            analysis: Output from AngularAnalyzer

        Returns:
            Service dependency graph in JSON format
        """
        logger.info("[ANGULAR DIAGRAM] Generating service dependencies")

        services = analysis.get("services", [])
        dependencies = analysis.get("dependencies", {})

        # Build nodes and edges
        nodes = []
        edges = []

        for service in services:
            service_name = service["name"]

            nodes.append(
                {
                    "id": service_name,
                    "label": service_name,
                    "type": "service",
                    "provided_in": service.get("provided_in", "root"),
                }
            )

            # Add dependency edges
            service_deps = dependencies.get(service_name, [])
            for dep in service_deps:
                edges.append({"from": service_name, "to": dep, "type": "injects"})

        # Add HttpClient and other common services as nodes if referenced
        referenced_services = set()
        for edge in edges:
            referenced_services.add(edge["to"])

        for ref_service in referenced_services:
            if not any(node["id"] == ref_service for node in nodes):
                nodes.append(
                    {
                        "id": ref_service,
                        "label": ref_service,
                        "type": "external",
                        "provided_in": "unknown",
                    }
                )

        return {
            "diagram_type": "service_dependencies",
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "generated_at": timezone.now().isoformat(),
                "total_services": len(services),
                "total_dependencies": len(edges),
                "analysis_type": "angular_services",
            },
        }

    def generate_module_graph(self, analysis: Dict) -> Dict:
        """
        Generate module dependency graph.

        Args:
            analysis: Output from AngularAnalyzer

        Returns:
            Module dependency graph in JSON format
        """
        logger.info("[ANGULAR DIAGRAM] Generating module graph")

        modules = analysis.get("modules", [])

        nodes = []
        edges = []

        for module in modules:
            module_name = module["name"]

            nodes.append(
                {
                    "id": module_name,
                    "label": module_name,
                    "type": "module",
                    "declarations_count": len(module.get("declarations", [])),
                    "imports_count": len(module.get("imports", [])),
                    "providers_count": len(module.get("providers", [])),
                }
            )

            # Add import edges
            imports = module.get("imports", [])
            for imported_module in imports:
                # Filter out Angular core modules for clarity
                if not self._is_core_angular_module(imported_module):
                    edges.append(
                        {"from": module_name, "to": imported_module, "type": "imports"}
                    )

        return {
            "diagram_type": "module_graph",
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "generated_at": timezone.now().isoformat(),
                "total_modules": len(modules),
                "total_imports": len(edges),
                "analysis_type": "angular_modules",
            },
        }

    def generate_routing_structure(self, analysis: Dict) -> Dict:
        """
        Generate routing structure diagram.

        Args:
            analysis: Output from AngularAnalyzer

        Returns:
            Routing structure in JSON format
        """
        logger.info("[ANGULAR DIAGRAM] Generating routing structure")

        routes = analysis.get("routes", [])

        # Build route tree
        route_tree = self._build_route_tree(routes)

        return {
            "diagram_type": "routing_structure",
            "routes": route_tree,
            "metadata": {
                "generated_at": timezone.now().isoformat(),
                "total_routes": len(routes),
                "analysis_type": "angular_routing",
            },
        }

    def _build_component_hierarchy(self, components: List[Dict]) -> List[Dict]:
        """
        Build component hierarchy based on selector usage in templates.

        Args:
            components: List of component info

        Returns:
            Hierarchical component structure
        """
        # For now, return flat list with selectors
        # In a full implementation, would parse templates to find parent-child
        # relationships

        hierarchy = []

        for component in components:
            hierarchy.append(
                {
                    "name": component["name"],
                    "selector": component.get("selector", "unknown"),
                    "template": component.get("template", "unknown"),
                    "dependencies": component.get("dependencies", []),
                    "file_path": component["file_path"],
                }
            )

        return hierarchy

    def _build_route_tree(self, routes: List[Dict]) -> List[Dict]:
        """
        Build hierarchical route structure.

        Args:
            routes: List of route info

        Returns:
            Tree structure of routes
        """
        route_tree = []

        for route in routes:
            route_tree.append(
                {
                    "path": route["path"],
                    "full_path": "/" + route["path"],
                    "component": route.get("component", None),
                    "lazy_module": route.get("lazy_module", None),
                    "is_lazy": bool(route.get("lazy_module")),
                    "file_path": route["file_path"],
                }
            )

        # Sort by path
        route_tree.sort(key=lambda r: r["path"])

        return route_tree

    def _is_core_angular_module(self, module_name: str) -> bool:
        """Check if module is a core Angular module."""
        core_modules = [
            "BrowserModule",
            "CommonModule",
            "FormsModule",
            "ReactiveFormsModule",
            "HttpClientModule",
            "RouterModule",
            "BrowserAnimationsModule",
        ]

        return module_name in core_modules
