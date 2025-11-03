"""
UML Generator

Generates UML Class Diagrams from analyzed Python code.
"""
import logging
from typing import Dict, List
from django.utils import timezone


logger = logging.getLogger(__name__)


class UMLGenerator:
    """
    Generates UML Class Diagrams from code analysis.
    
    Transforms analyzed code structure into UML JSON format.
    """
    
    def generate_uml_json(self, analysis: Dict, integration) -> Dict:
        """
        Generate UML diagram JSON from code analysis.
        
        Args:
            analysis: Output from PythonCodeAnalyzer
            integration: GitHubIntegration instance
            
        Returns:
            UML diagram in JSON format
        """
        logger.info("Generating UML diagram from code analysis")
        
        classes = []
        relationships = []
        
        # Transform analyzed classes to UML format
        for class_key, class_info in analysis['classes'].items():
            uml_class = self._transform_class_to_uml(class_info)
            classes.append(uml_class)
            
            # Extract relationships from this class
            class_relationships = self._extract_class_relationships(
                class_info,
                analysis['classes']
            )
            relationships.extend(class_relationships)
        
        # Add import-based relationships from dependency graph
        import_relationships = self._extract_import_relationships(
            analysis['dependencies'],
            analysis['classes']
        )
        relationships.extend(import_relationships)
        
        # Remove duplicates
        relationships = self._deduplicate_relationships(relationships)
        
        result = {
            'diagram_type': 'class',
            'repository': {
                'owner': integration.repository_owner,
                'name': integration.repository_name,
                'url': integration.repository_url
            },
            'classes': classes,
            'relationships': relationships,
            'metadata': {
                'generated_at': timezone.now().isoformat(),
                'total_classes': len(classes),
                'total_relationships': len(relationships),
                'total_files_analyzed': analysis['stats']['total_files']
            }
        }
        
        logger.info(
            f"Generated UML: {len(classes)} classes, "
            f"{len(relationships)} relationships"
        )
        
        return result
    
    def _transform_class_to_uml(self, class_info: Dict) -> Dict:
        """
        Transform analyzed class to UML format.
        
        Args:
            class_info: Class information from analyzer
            
        Returns:
            UML class representation
        """
        return {
            'name': class_info['name'],
            'file_path': class_info['file_path'],
            'module': self._extract_module_name(class_info['file_path']),
            'attributes': [
                {
                    'name': attr['name'],
                    'type': attr.get('type', 'Any'),
                    'required': attr.get('required', True)
                }
                for attr in class_info.get('attributes', [])
            ],
            'methods': [
                {
                    'name': method['name'],
                    'visibility': method.get('visibility', 'public')
                }
                for method in class_info.get('methods', [])
            ],
            'parent_classes': class_info.get('parent_classes', [])
        }
    
    def _extract_class_relationships(
        self,
        class_info: Dict,
        all_classes: Dict
    ) -> List[Dict]:
        """
        Extract relationships from a class.
        
        Args:
            class_info: Class information
            all_classes: All classes in analysis
            
        Returns:
            List of relationships
        """
        relationships = []
        
        # Inheritance relationships
        for parent in class_info.get('parent_classes', []):
            # Check if parent is in our analyzed classes
            parent_exists = any(
                cls['name'] == parent
                for cls in all_classes.values()
            )
            
            if parent_exists:
                relationships.append({
                    'from': class_info['name'],
                    'to': parent,
                    'type': 'inherits',
                    'description': f"{class_info['name']} inherits from {parent}"
                })
        
        # Composition relationships (attributes that are other classes)
        for attr in class_info.get('attributes', []):
            attr_type = attr.get('type', '')
            
            # Check if attribute type is another analyzed class
            if attr_type in [cls['name'] for cls in all_classes.values()]:
                relationships.append({
                    'from': class_info['name'],
                    'to': attr_type,
                    'type': 'has_a',
                    'description': f"{class_info['name']} has {attr['name']} of type {attr_type}"
                })
        
        return relationships
    
    def _extract_import_relationships(
        self,
        dependency_graph: Dict,
        all_classes: Dict
    ) -> List[Dict]:
        """
        Extract relationships from import dependencies.
        
        Args:
            dependency_graph: Dependency graph from analyzer
            all_classes: All analyzed classes
            
        Returns:
            List of relationships
        """
        relationships = []
        
        for file_path, dependencies in dependency_graph.items():
            # Get classes in this file
            source_classes = [
                cls['name']
                for cls in all_classes.values()
                if cls['file_path'] == file_path
            ]
            
            for dep in dependencies:
                if dep['type'] == 'inherits':
                    # Already handled in class relationships
                    continue
                
                if dep['type'] == 'imports':
                    # Find target classes
                    target = dep['target']
                    
                    # Find classes in target module
                    target_classes = [
                        cls['name']
                        for cls in all_classes.values()
                        if target in cls['file_path'] or target in cls.get('module', '')
                    ]
                    
                    # Create usage relationships
                    for source_class in source_classes:
                        for target_class in target_classes:
                            relationships.append({
                                'from': source_class,
                                'to': target_class,
                                'type': 'uses',
                                'description': f"{source_class} uses {target_class}"
                            })
        
        return relationships
    
    def _deduplicate_relationships(self, relationships: List[Dict]) -> List[Dict]:
        """
        Remove duplicate relationships.
        
        Args:
            relationships: List of relationships
            
        Returns:
            Deduplicated list
        """
        seen = set()
        unique = []
        
        for rel in relationships:
            # Create unique key
            key = (rel['from'], rel['to'], rel['type'])
            
            if key not in seen:
                seen.add(key)
                unique.append(rel)
        
        return unique
    
    def _extract_module_name(self, file_path: str) -> str:
        """Extract module name from file path."""
        # Remove .py and convert to module notation
        module = file_path.replace('.py', '')
        module = module.replace('/', '.').replace('\\', '.')
        
        # Remove common prefixes
        for prefix in ['apps.', 'src.', 'lib.']:
            if module.startswith(prefix):
                module = module[len(prefix):]
        
        return module
