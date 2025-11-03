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
            UML diagram in JSON format with ONLY Django ORM models
        """
        logger.info("Generating UML diagram from code analysis")
        
        classes = []
        relationships = []
        filtered_classes = {}
        
        # Filter to include ONLY Django ORM models
        for class_key, class_info in analysis['classes'].items():
            if self._is_django_model(class_info):
                filtered_classes[class_key] = class_info
        
        logger.info(
            f"Filtered {len(analysis['classes'])} classes down to "
            f"{len(filtered_classes)} Django models"
        )
        
        # Transform filtered classes to UML format
        for class_key, class_info in filtered_classes.items():
            uml_class = self._transform_class_to_uml(class_info)
            classes.append(uml_class)
            
            # Extract relationships from this class
            class_relationships = self._extract_class_relationships(
                class_info,
                filtered_classes  # Only consider filtered classes for relationships
            )
            relationships.extend(class_relationships)
        
        # Add import-based relationships from dependency graph
        import_relationships = self._extract_import_relationships(
            analysis['dependencies'],
            filtered_classes  # Only consider filtered classes
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
                'total_files_analyzed': analysis['stats']['total_files'],
                'filter_applied': 'django_orm_models_only',
                'classes_before_filter': len(analysis['classes']),
                'classes_after_filter': len(filtered_classes),
                'filter_description': 'Only Django ORM models (excludes middlewares, tests, serializers, viewsets, etc.)'
            }
        }
        
        logger.info(
            f"Generated UML: {len(classes)} classes, "
            f"{len(relationships)} relationships"
        )
        
        return result
    
    def _is_django_model(self, class_info: Dict) -> bool:
        """
        Determine if a class is a Django ORM model.
        
        Filters out:
        - Middlewares, configs, tests, fixtures
        - Serializers, viewsets, services
        - Abstract classes
        - Any class not in models.py or models/ folder
        
        Args:
            class_info: Class information from analyzer
            
        Returns:
            True if class is a Django model, False otherwise
        """
        class_name = class_info['name']
        file_path = class_info.get('file_path', '')
        file_path_lower = file_path.lower()
        class_name_lower = class_name.lower()
        
        # FILTER 1: Must be in models.py or models/ folder
        if 'models' not in file_path_lower:
            return False
        
        # Exclude specific non-model folders even if they contain "models"
        excluded_folders = ['migrations', 'tests', 'test', 'fixtures']
        if any(folder in file_path_lower for folder in excluded_folders):
            return False
        
        # FILTER 2: Class name patterns to exclude
        excluded_patterns = [
            'test',           # Test classes
            'factory',        # Test factories
            'fixture',        # Test fixtures
            'mock',           # Mock objects
            'middleware',     # Middleware classes
            'config',         # Config classes
            'serializer',     # DRF serializers
            'viewset',        # DRF viewsets
            'view',           # Views
            'service',        # Service classes
            'manager',        # Custom managers (unless it's a model)
            'admin',          # Django admin classes
            'form',           # Django forms
            'mixin',          # Mixin classes
        ]
        
        for pattern in excluded_patterns:
            if pattern in class_name_lower:
                return False
        
        # FILTER 3: Exclude abstract base classes from Django/external libraries
        if class_name.startswith('Abstract'):
            # Check if it's in our codebase vs Django's
            if 'django' in file_path_lower or 'site-packages' in file_path_lower:
                return False
        
        # FILTER 4: Check inheritance - must inherit from models.Model
        parent_classes = class_info.get('parent_classes', [])
        if parent_classes:
            # Look for Model inheritance
            model_inheritance = any(
                'Model' in parent or 'model' in parent.lower()
                for parent in parent_classes
            )
            
            # If no Model inheritance detected, likely not a Django model
            if not model_inheritance:
                # Exception: Could be inheriting from another model in the same app
                # We'll allow classes without explicit Model parent if they're in models.py
                pass
        
        # FILTER 5: Common Django model naming patterns
        # Most Django models are capitalized nouns (User, Project, Issue)
        # Exclude utility classes
        utility_suffixes = ['Utils', 'Helper', 'Base', 'Meta']
        for suffix in utility_suffixes:
            if class_name.endswith(suffix):
                return False
        
        logger.debug(f"Including Django model: {class_name} from {file_path}")
        return True
    
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
