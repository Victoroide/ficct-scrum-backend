"""
Angular TypeScript Code Analyzer.

Analyzes Angular/TypeScript code to extract components, services, modules, and routes.
Uses regex patterns for parsing (no Node.js dependency required).
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AngularAnalyzer:
    """
    Analyzes Angular TypeScript code to extract structural information.

    Extracts:
    - Components (@Component)
    - Services (@Injectable)
    - Modules (@NgModule)
    - Routes (RouterModule.forRoot/forChild)
    - Dependencies (constructor injection)
    """

    # Regex patterns for Angular decorators
    COMPONENT_PATTERN = re.compile(
        r"@Component\s*\(\s*\{([^}]+)\}\s*\)\s*export\s+class\s+(\w+)", re.DOTALL
    )

    SERVICE_PATTERN = re.compile(
        r"@Injectable\s*\(\s*\{([^}]+)?\}\s*\)\s*export\s+class\s+(\w+)", re.DOTALL
    )

    MODULE_PATTERN = re.compile(
        r"@NgModule\s*\(\s*\{([^}]+)\}\s*\)\s*export\s+class\s+(\w+)", re.DOTALL
    )

    IMPORT_PATTERN = re.compile(r'import\s+\{([^}]+)\}\s+from\s+[\'"]([^\'"]+)[\'"]')

    CONSTRUCTOR_PATTERN = re.compile(r"constructor\s*\(([^)]*)\)", re.DOTALL)

    ROUTE_PATTERN = re.compile(
        r"RouterModule\.for(?:Root|Child)\s*\(\s*\[([^\]]+)\]", re.DOTALL
    )

    def __init__(self):
        self.components = []
        self.services = []
        self.modules = []
        self.routes = []
        self.dependencies = {}

    def analyze_angular_code(self, files_content: Dict[str, str]) -> Dict[str, Any]:
        """
        Analyze Angular TypeScript files.

        Args:
            files_content: Dict mapping file path to content

        Returns:
            Complete analysis with components, services, modules, routes
        """
        logger.info(f"[ANGULAR] Analyzing {len(files_content)} TypeScript files")

        for file_path, content in files_content.items():
            try:
                # Determine file type
                if file_path.endswith(".component.ts"):
                    self._analyze_component(file_path, content)
                elif file_path.endswith(".service.ts"):
                    self._analyze_service(file_path, content)
                elif file_path.endswith(".module.ts"):
                    self._analyze_module(file_path, content)
                elif "routing" in file_path.lower():
                    self._analyze_routing(file_path, content)

            except Exception as e:
                logger.warning(f"[ANGULAR] Failed to analyze {file_path}: {str(e)}")
                continue

        logger.info(
            f"[ANGULAR] Analysis complete: {len(self.components)} components, "
            f"{len(self.services)} services, {len(self.modules)} modules, "
            f"{len(self.routes)} routes"
        )

        return {
            "components": self.components,
            "services": self.services,
            "modules": self.modules,
            "routes": self.routes,
            "dependencies": self.dependencies,
            "stats": {
                "total_components": len(self.components),
                "total_services": len(self.services),
                "total_modules": len(self.modules),
                "total_routes": len(self.routes),
            },
        }

    def _analyze_component(self, file_path: str, content: str):
        """Analyze Angular component."""
        matches = self.COMPONENT_PATTERN.findall(content)

        for metadata_str, class_name in matches:
            # Extract selector
            selector_match = re.search(r'selector:\s*[\'"]([^\'"]+)[\'"]', metadata_str)
            selector = selector_match.group(1) if selector_match else None

            # Extract template info
            template_match = re.search(
                r'template(?:Url)?:\s*[\'"]([^\'"]+)[\'"]', metadata_str
            )
            template = template_match.group(1) if template_match else None

            # Extract dependencies from constructor
            dependencies = self._extract_dependencies(content, class_name)

            component_info = {
                "name": class_name,
                "type": "component",
                "selector": selector,
                "template": template,
                "file_path": file_path,
                "dependencies": dependencies,
            }

            self.components.append(component_info)
            self.dependencies[class_name] = dependencies

            logger.debug(f"[ANGULAR] Component: {class_name} (selector: {selector})")

    def _analyze_service(self, file_path: str, content: str):
        """Analyze Angular service."""
        matches = self.SERVICE_PATTERN.findall(content)

        for metadata_str, class_name in matches:
            # Extract providedIn
            provided_in_match = re.search(
                r'providedIn:\s*[\'"]([^\'"]+)[\'"]', metadata_str
            )
            provided_in = provided_in_match.group(1) if provided_in_match else None

            # Extract dependencies
            dependencies = self._extract_dependencies(content, class_name)

            service_info = {
                "name": class_name,
                "type": "service",
                "provided_in": provided_in or "root",
                "file_path": file_path,
                "dependencies": dependencies,
            }

            self.services.append(service_info)
            self.dependencies[class_name] = dependencies

            logger.debug(f"[ANGULAR] Service: {class_name} (providedIn: {provided_in})")

    def _analyze_module(self, file_path: str, content: str):
        """Analyze Angular module."""
        matches = self.MODULE_PATTERN.findall(content)

        for metadata_str, class_name in matches:
            # Extract declarations
            declarations = self._extract_array_values(metadata_str, "declarations")

            # Extract imports
            imports = self._extract_array_values(metadata_str, "imports")

            # Extract providers
            providers = self._extract_array_values(metadata_str, "providers")

            # Extract exports
            exports = self._extract_array_values(metadata_str, "exports")

            module_info = {
                "name": class_name,
                "type": "module",
                "file_path": file_path,
                "declarations": declarations,
                "imports": imports,
                "providers": providers,
                "exports": exports,
            }

            self.modules.append(module_info)

            logger.debug(
                f"[ANGULAR] Module: {class_name} "
                f"({len(declarations)} declarations, {len(imports)} imports)"
            )

    def _analyze_routing(self, file_path: str, content: str):
        """Analyze routing configuration."""
        matches = self.ROUTE_PATTERN.findall(content)

        for routes_str in matches:
            # Extract individual route objects
            route_pattern = re.compile(
                r'\{\s*path:\s*[\'"]([^\'"]*)[\'"][^}]*\}', re.DOTALL
            )
            route_matches = route_pattern.findall(routes_str)

            for path in route_matches:
                # Try to extract component
                comp_pattern = re.compile(
                    re.escape(path) + r"[^}]*component:\s*(\w+)", re.DOTALL
                )
                comp_match = comp_pattern.search(content)
                component = comp_match.group(1) if comp_match else None

                # Check for lazy loading
                lazy_pattern = re.compile(
                    re.escape(path)
                    + r'[^}]*loadChildren:\s*\(\)\s*=>\s*import\([\'"]([^\'"]+)[\'"]',
                    re.DOTALL,
                )
                lazy_match = lazy_pattern.search(content)
                lazy_module = lazy_match.group(1) if lazy_match else None

                route_info = {
                    "path": path,
                    "component": component,
                    "lazy_module": lazy_module,
                    "file_path": file_path,
                }

                self.routes.append(route_info)

                logger.debug(
                    f"[ANGULAR] Route: /{path} "
                    f"(component: {component}, lazy: {bool(lazy_module)})"
                )

    def _extract_dependencies(self, content: str, class_name: str) -> List[str]:
        """Extract constructor dependencies for a class."""
        # Find the class constructor
        class_pattern = (
            r"export\s+class\s+" + re.escape(class_name) + r"[^{]*\{(.+?)\n\s*\}"
        )
        class_match = re.search(class_pattern, content, re.DOTALL)

        if not class_match:
            return []

        class_body = class_match.group(1)

        # Find constructor
        constructor_match = self.CONSTRUCTOR_PATTERN.search(class_body)

        if not constructor_match:
            return []

        constructor_params = constructor_match.group(1)

        # Extract service types from constructor parameters
        # e.g., "private authService: AuthService" -> "AuthService"
        param_pattern = re.compile(r"(?:private|public|protected)?\s*(\w+):\s*(\w+)")
        dependencies = []

        for param_match in param_pattern.finditer(constructor_params):
            param_name = param_match.group(1)
            param_type = param_match.group(2)

            # Filter out primitive types
            if param_type not in ["string", "number", "boolean", "any", "void"]:
                dependencies.append(param_type)

        return dependencies

    def _extract_array_values(self, metadata_str: str, array_name: str) -> List[str]:
        """Extract values from array property in decorator metadata."""
        # Match array property: declarations: [...]
        pattern = rf"{array_name}:\s*\[([^\]]*)\]"
        match = re.search(pattern, metadata_str, re.DOTALL)

        if not match:
            return []

        array_content = match.group(1)

        # Extract individual identifiers
        # Remove comments and whitespace
        array_content = re.sub(r"//[^\n]*", "", array_content)
        array_content = re.sub(r"/\*.*?\*/", "", array_content, flags=re.DOTALL)

        # Extract identifiers
        identifier_pattern = re.compile(r"\b([A-Z]\w+)\b")
        identifiers = identifier_pattern.findall(array_content)

        return identifiers
