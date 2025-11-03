"""
Architecture Generator

Generates Architecture Diagrams from analyzed Python code.
Detects layers and components based on directory structure and naming patterns.
"""
import logging
from typing import Dict, List, Set
from django.utils import timezone


logger = logging.getLogger(__name__)


class ArchitectureGenerator:
    """
    Generates Architecture Diagrams from code analysis.
    
    Detects architectural layers and components, maps dependencies.
    """
    
    # Layer detection patterns
    LAYER_PATTERNS = {
        'Presentation Layer': [
            'views', 'viewsets', 'controllers', 'handlers', 'api', 'routes', 'endpoints'
        ],
        'Business Logic Layer': [
            'services', 'business', 'logic', 'managers', 'use_cases', 'domain'
        ],
        'Data Access Layer': [
            'models', 'repositories', 'entities', 'database', 'dao', 'orm'
        ],
        'Utilities': [
            'utils', 'helpers', 'common', 'shared', 'lib'
        ],
        'Integration Layer': [
            'integrations', 'clients', 'adapters', 'external'
        ]
    }
    
    def generate_architecture_json(self, analysis: Dict, integration) -> Dict:
        """
        Generate architecture diagram JSON from code analysis.
        
        Args:
            analysis: Output from PythonCodeAnalyzer
            integration: GitHubIntegration instance
            
        Returns:
            Architecture diagram in JSON format
        """
        logger.info("Generating architecture diagram from code analysis")
        
        # Classify components into layers
        layers = self._classify_components_into_layers(
            analysis['files'],
            analysis['classes']
        )
        
        # Build connections between components
        connections = self._build_connections(
            analysis['dependencies'],
            layers
        )
        
        result = {
            'repository': {
                'owner': integration.repository_owner,
                'name': integration.repository_name,
                'url': integration.repository_url
            },
            'architecture_pattern': self._detect_architecture_pattern(layers),
            'layers': layers,
            'connections': connections,
            'metadata': {
                'generated_at': timezone.now().isoformat(),
                'total_layers': len(layers),
                'total_components': sum(len(layer['components']) for layer in layers),
                'total_connections': len(connections),
                'total_files_analyzed': analysis['stats']['total_files']
            }
        }
        
        logger.info(
            f"Generated architecture: {len(layers)} layers, "
            f"{result['metadata']['total_components']} components, "
            f"{len(connections)} connections"
        )
        
        return result
    
    def _classify_components_into_layers(
        self,
        files: Dict,
        classes: Dict
    ) -> List[Dict]:
        """
        Classify components into architectural layers.
        
        Args:
            files: Analyzed files
            classes: All classes
            
        Returns:
            List of layers with components
        """
        layers_dict = {layer: [] for layer in self.LAYER_PATTERNS.keys()}
        unclassified = []
        
        for file_path, file_analysis in files.items():
            # Determine layer for this file
            layer = self._determine_file_layer(file_path)
            
            # Extract components from file
            components = self._extract_components_from_file(
                file_path,
                file_analysis,
                classes
            )
            
            if layer:
                layers_dict[layer].extend(components)
            else:
                unclassified.extend(components)
        
        # Build layer list
        layers = []
        for layer_name, components in layers_dict.items():
            if components:  # Only include non-empty layers
                layers.append({
                    'name': layer_name,
                    'description': self._get_layer_description(layer_name),
                    'components': components
                })
        
        # Add unclassified if any
        if unclassified:
            layers.append({
                'name': 'Other Components',
                'description': 'Components that don\'t fit standard layer patterns',
                'components': unclassified
            })
        
        return layers
    
    def _determine_file_layer(self, file_path: str) -> str:
        """
        Determine which layer a file belongs to based on path.
        
        Args:
            file_path: Path to file
            
        Returns:
            Layer name or None
        """
        path_lower = file_path.lower()
        
        for layer_name, patterns in self.LAYER_PATTERNS.items():
            for pattern in patterns:
                if f'/{pattern}/' in path_lower or path_lower.startswith(f'{pattern}/'):
                    return layer_name
                # Check filename
                if pattern in path_lower.split('/')[-1]:
                    return layer_name
        
        return None
    
    def _extract_components_from_file(
        self,
        file_path: str,
        file_analysis: Dict,
        all_classes: Dict
    ) -> List[Dict]:
        """
        Extract components from a file.
        
        Args:
            file_path: File path
            file_analysis: File analysis result
            all_classes: All analyzed classes
            
        Returns:
            List of components
        """
        components = []
        
        # Each class is a component
        for cls in file_analysis['classes']:
            component_type = self._determine_component_type(cls, file_path)
            
            components.append({
                'name': cls['name'],
                'type': component_type,
                'file_path': file_path,
                'module': file_analysis.get('module_name', ''),
                'description': f"{component_type.title()} component in {file_path}",
                'methods_count': len(cls.get('methods', [])),
                'attributes_count': len(cls.get('attributes', []))
            })
        
        # If no classes, create component for the module itself
        if not components and file_analysis['imports']:
            components.append({
                'name': self._extract_module_display_name(file_path),
                'type': 'module',
                'file_path': file_path,
                'module': file_analysis.get('module_name', ''),
                'description': f"Module file {file_path}",
                'methods_count': 0,
                'attributes_count': 0
            })
        
        return components
    
    def _determine_component_type(self, cls: Dict, file_path: str) -> str:
        """
        Determine component type based on class and file characteristics.
        
        Args:
            cls: Class information
            file_path: File path
            
        Returns:
            Component type string
        """
        class_name = cls['name'].lower()
        path_lower = file_path.lower()
        
        # Check by class name patterns
        if 'viewset' in class_name or 'view' in class_name:
            return 'viewset'
        if 'serializer' in class_name:
            return 'serializer'
        if 'service' in class_name:
            return 'service'
        if 'model' in class_name or 'entity' in class_name:
            return 'model'
        if 'repository' in class_name:
            return 'repository'
        if 'controller' in class_name or 'handler' in class_name:
            return 'controller'
        if 'manager' in class_name:
            return 'manager'
        if 'util' in class_name or 'helper' in class_name:
            return 'utility'
        
        # Check by file path
        if '/models/' in path_lower or 'model.py' in path_lower:
            return 'model'
        if '/views/' in path_lower or '/viewsets/' in path_lower:
            return 'viewset'
        if '/services/' in path_lower:
            return 'service'
        if '/serializers/' in path_lower:
            return 'serializer'
        
        return 'component'
    
    def _build_connections(
        self,
        dependency_graph: Dict,
        layers: List[Dict]
    ) -> List[Dict]:
        """
        Build connections between components.
        
        Args:
            dependency_graph: Dependency graph from analyzer
            layers: Classified layers with components
            
        Returns:
            List of connections
        """
        connections = []
        
        # Create component lookup
        component_lookup = {}
        for layer in layers:
            for comp in layer['components']:
                key = f"{comp['file_path']}::{comp['name']}"
                component_lookup[key] = {
                    **comp,
                    'layer': layer['name']
                }
        
        # Build connections from dependency graph
        for file_path, dependencies in dependency_graph.items():
            for dep in dependencies:
                conn = self._create_connection(
                    dep,
                    file_path,
                    component_lookup
                )
                if conn:
                    connections.append(conn)
        
        # Deduplicate
        connections = self._deduplicate_connections(connections)
        
        return connections
    
    def _create_connection(
        self,
        dependency: Dict,
        source_file: str,
        component_lookup: Dict
    ) -> Dict:
        """Create a connection from dependency information."""
        dep_type = dependency['type']
        
        # Find source component
        source_components = [
            comp for key, comp in component_lookup.items()
            if comp['file_path'] == source_file
        ]
        
        if not source_components:
            return None
        
        source_comp = source_components[0]
        
        # Find target component
        if dep_type == 'inherits':
            target_name = dependency.get('target')
            target_comps = [
                comp for comp in component_lookup.values()
                if comp['name'] == target_name
            ]
            
            if target_comps:
                return {
                    'from': source_comp['name'],
                    'to': target_comps[0]['name'],
                    'type': 'inherits',
                    'from_layer': source_comp['layer'],
                    'to_layer': target_comps[0]['layer']
                }
        
        elif dep_type == 'imports':
            # General import connection
            target = dependency.get('target', '')
            
            # Try to find matching component
            for comp in component_lookup.values():
                if target in comp['module'] or target in comp['file_path']:
                    return {
                        'from': source_comp['name'],
                        'to': comp['name'],
                        'type': 'uses',
                        'from_layer': source_comp['layer'],
                        'to_layer': comp['layer']
                    }
        
        return None
    
    def _deduplicate_connections(self, connections: List[Dict]) -> List[Dict]:
        """Remove duplicate connections."""
        seen = set()
        unique = []
        
        for conn in connections:
            key = (conn['from'], conn['to'], conn['type'])
            if key not in seen:
                seen.add(key)
                unique.append(conn)
        
        return unique
    
    def _detect_architecture_pattern(self, layers: List[Dict]) -> str:
        """
        Detect architecture pattern based on layers.
        
        Args:
            layers: List of layers
            
        Returns:
            Architecture pattern name
        """
        layer_names = {layer['name'] for layer in layers}
        
        # Check for layered architecture
        has_presentation = any('Presentation' in name for name in layer_names)
        has_business = any('Business' in name or 'Logic' in name for name in layer_names)
        has_data = any('Data' in name for name in layer_names)
        
        if has_presentation and has_business and has_data:
            return 'Layered Architecture (3-tier)'
        elif has_business and has_data:
            return 'Layered Architecture (2-tier)'
        elif len(layers) >= 4:
            return 'Multi-layer Architecture'
        else:
            return 'Simple Architecture'
    
    def _get_layer_description(self, layer_name: str) -> str:
        """Get description for a layer."""
        descriptions = {
            'Presentation Layer': 'Handles HTTP requests, API endpoints, views, and serializers',
            'Business Logic Layer': 'Contains business rules, services, and use cases',
            'Data Access Layer': 'Manages data persistence, models, and repositories',
            'Utilities': 'Common utilities, helpers, and shared functions',
            'Integration Layer': 'External service integrations and adapters'
        }
        return descriptions.get(layer_name, 'Application components')
    
    def _extract_module_display_name(self, file_path: str) -> str:
        """Extract display name from file path."""
        name = file_path.split('/')[-1].replace('.py', '')
        return name.replace('_', ' ').title()
