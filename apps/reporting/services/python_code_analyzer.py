"""
Python Code Analyzer

Analyzes Python source code to extract classes, methods, imports, and relationships.
Uses regex patterns and heuristics (no full AST parsing for simplicity).
"""

import logging
import re
from typing import Dict, List

logger = logging.getLogger(__name__)


class PythonCodeAnalyzer:
    """
    Analyzes Python code to extract structural information.

    Uses regex patterns and heuristics to identify:
    - Classes and their inheritance
    - Methods and their signatures
    - Imports and dependencies
    - Relationships between components
    """

    # Regex patterns
    CLASS_PATTERN = re.compile(r"^class\s+(\w+)(\(([^)]*)\))?:", re.MULTILINE)
    METHOD_PATTERN = re.compile(r"^\s+(def\s+(\w+)\s*\([^)]*\))", re.MULTILINE)
    IMPORT_PATTERN = re.compile(r"^(?:from\s+([\w.]+)\s+)?import\s+(.+)", re.MULTILINE)
    TYPE_HINT_PATTERN = re.compile(r":\s*([\w\[\], ]+)(?:\s*=)?")

    def __init__(self):
        self.analyzed_files = {}
        self.all_classes = {}
        self.dependency_graph = {}

    def analyze_repository(self, files_content: Dict[str, str]) -> Dict:
        """
        Analyze all Python files in repository.

        Args:
            files_content: Dict mapping file path to content

        Returns:
            Complete analysis with classes, dependencies, and relationships
        """
        logger.info(f"Analyzing {len(files_content)} Python files")

        # First pass: analyze each file
        for file_path, content in files_content.items():
            try:
                analysis = self.analyze_python_file(content, file_path)
                self.analyzed_files[file_path] = analysis

                # Register classes
                for cls in analysis["classes"]:
                    class_key = f"{file_path}::{cls['name']}"
                    self.all_classes[class_key] = {**cls, "file_path": file_path}
            except Exception as e:
                logger.warning(f"Failed to analyze {file_path}: {str(e)}")
                continue

        # Second pass: build dependency graph
        self.dependency_graph = self._build_dependency_graph()

        logger.info(
            f"Analysis complete: {len(self.all_classes)} classes, "
            f"{len(self.dependency_graph)} dependencies"
        )

        return {
            "files": self.analyzed_files,
            "classes": self.all_classes,
            "dependencies": self.dependency_graph,
            "stats": {
                "total_files": len(self.analyzed_files),
                "total_classes": len(self.all_classes),
                "total_dependencies": len(self.dependency_graph),
            },
        }

    def analyze_python_file(self, content: str, file_path: str) -> Dict:
        """
        Analyze a single Python file.

        Args:
            content: File content
            file_path: File path

        Returns:
            Analysis result with classes, methods, and imports
        """
        classes = []
        imports = []

        # Extract imports
        imports = self._extract_imports(content)

        # Extract classes
        class_matches = self.CLASS_PATTERN.finditer(content)

        for match in class_matches:
            class_name = match.group(1)
            inheritance = match.group(3) if match.group(3) else None

            # Extract class details
            class_info = self._extract_class_info(class_name, content, inheritance)
            classes.append(class_info)

        return {
            "file_path": file_path,
            "classes": classes,
            "imports": imports,
            "module_name": self._path_to_module(file_path),
        }

    def _extract_class_info(
        self, class_name: str, content: str, inheritance: str
    ) -> Dict:
        """
        Extract detailed information about a class.

        Args:
            class_name: Name of the class
            content: File content
            inheritance: Inheritance string (parent classes)

        Returns:
            Class information dict
        """
        # Find class definition block
        class_pattern = re.compile(
            rf"^class\s+{re.escape(class_name)}.*?(?=^class\s|\Z)",
            re.MULTILINE | re.DOTALL,
        )
        class_match = class_pattern.search(content)

        if not class_match:
            return {
                "name": class_name,
                "attributes": [],
                "methods": [],
                "parent_classes": [],
            }

        class_content = class_match.group(0)

        # Extract methods
        methods = []
        method_matches = self.METHOD_PATTERN.finditer(class_content)

        for method_match in method_matches:
            method_name = method_match.group(2)
            visibility = "private" if method_name.startswith("_") else "public"

            methods.append({"name": method_name, "visibility": visibility})

        # Extract attributes from __init__
        attributes = self._extract_init_attributes(class_content)

        # Parse parent classes
        parent_classes = []
        if inheritance:
            parent_classes = [p.strip() for p in inheritance.split(",") if p.strip()]

        return {
            "name": class_name,
            "attributes": attributes,
            "methods": methods,
            "parent_classes": parent_classes,
        }

    def _extract_init_attributes(self, class_content: str) -> List[Dict]:
        """Extract attributes from __init__ method."""
        attributes = []

        # Find __init__ method
        init_pattern = re.compile(
            r"def\s+__init__\s*\([^)]*\):.*?(?=\n    def\s|\n\nclass\s|\Z)", re.DOTALL
        )
        init_match = init_pattern.search(class_content)

        if not init_match:
            return attributes

        init_content = init_match.group(0)

        # Find self.attribute assignments
        attr_pattern = re.compile(r"self\.(\w+)\s*[=:]")
        attr_matches = attr_pattern.finditer(init_content)

        for match in attr_matches:
            attr_name = match.group(1)

            # Try to infer type from assignment
            attr_type = self._infer_attribute_type(init_content, attr_name)

            attributes.append({"name": attr_name, "type": attr_type, "required": True})

        return attributes

    def _infer_attribute_type(self, content: str, attr_name: str) -> str:
        """Infer attribute type from context."""
        # Look for type hints
        hint_pattern = re.compile(rf"{attr_name}\s*:\s*([\w\[\], ]+)")
        hint_match = hint_pattern.search(content)

        if hint_match:
            return hint_match.group(1).strip()

        # Look for assignment patterns
        assign_pattern = re.compile(rf"self\.{attr_name}\s*=\s*([^\n]+)")
        assign_match = assign_pattern.search(content)

        if assign_match:
            value = assign_match.group(1).strip()

            # Heuristic type inference
            if value.startswith('"') or value.startswith("'"):
                return "str"
            elif value.startswith("["):
                return "list"
            elif value.startswith("{"):
                return "dict"
            elif value.isdigit():
                return "int"
            elif "True" in value or "False" in value:
                return "bool"

        return "Any"

    def _extract_imports(self, content: str) -> List[Dict]:
        """Extract import statements."""
        imports = []

        for match in self.IMPORT_PATTERN.finditer(content):
            from_module = match.group(1)
            import_items = match.group(2)

            # Parse imported items
            items = [item.strip() for item in import_items.split(",")]

            for item in items:
                # Handle "as" aliases
                if " as " in item:
                    original, alias = item.split(" as ")
                    item = original.strip()

                imports.append(
                    {
                        "from_module": from_module,
                        "import_name": item.strip(),
                        "is_relative": (
                            from_module and from_module.startswith(".")
                            if from_module
                            else False
                        ),
                    }
                )

        return imports

    def _build_dependency_graph(self) -> Dict:
        """
        Build dependency graph from analyzed files.

        Returns:
            Dict mapping source to list of dependencies
        """
        graph = {}

        for file_path, analysis in self.analyzed_files.items():
            dependencies = []

            # Map imports to classes
            for imp in analysis["imports"]:
                # Skip standard library and third-party
                if self._is_project_import(imp):
                    dependencies.append(
                        {
                            "type": "imports",
                            "target": imp["from_module"] or imp["import_name"],
                        }
                    )

            # Map inheritance
            for cls in analysis["classes"]:
                for parent in cls["parent_classes"]:
                    # Find parent class
                    parent_file = self._find_class_file(parent)
                    if parent_file:
                        dependencies.append(
                            {
                                "type": "inherits",
                                "source_class": cls["name"],
                                "target": parent,
                                "target_file": parent_file,
                            }
                        )

            if dependencies:
                graph[file_path] = dependencies

        return graph

    def _is_project_import(self, imp: Dict) -> bool:
        """Check if import is from project (not stdlib or third-party)."""
        module = imp["from_module"] or imp["import_name"]

        # Relative imports are always project
        if imp.get("is_relative"):
            return True

        # Check if starts with common project prefixes
        project_prefixes = ["apps", "src", "lib", "core", "services"]
        return any(module.startswith(prefix) for prefix in project_prefixes)

    def _find_class_file(self, class_name: str) -> str:
        """Find file containing a specific class."""
        for key, cls_info in self.all_classes.items():
            if cls_info["name"] == class_name:
                return cls_info["file_path"]
        return None

    def _path_to_module(self, file_path: str) -> str:
        """Convert file path to Python module name."""
        # Remove .py extension
        module = file_path.replace(".py", "")
        # Replace slashes with dots
        module = module.replace("/", ".").replace("\\", ".")
        return module
