from rest_framework import serializers


class DiagramRequestSerializer(serializers.Serializer):
    DIAGRAM_TYPE_CHOICES = [
        ("workflow", "Workflow"),
        ("dependency", "Dependency"),
        ("roadmap", "Roadmap"),
        ("uml", "UML"),
        ("architecture", "Architecture"),
        ("angular_component_hierarchy", "Angular Component Hierarchy"),
        ("angular_service_dependencies", "Angular Service Dependencies"),
        ("angular_module_graph", "Angular Module Graph"),
        ("angular_routing_structure", "Angular Routing Structure"),
    ]

    FORMAT_CHOICES = [
        ("svg", "SVG"),
        ("png", "PNG"),
        ("json", "JSON"),
    ]

    project = serializers.UUIDField(required=False, help_text="Project UUID")
    project_id = serializers.UUIDField(required=False, help_text="Project UUID (alternative)")
    diagram_type = serializers.ChoiceField(choices=DIAGRAM_TYPE_CHOICES, required=True)
    format = serializers.ChoiceField(choices=FORMAT_CHOICES, default="svg")
    parameters = serializers.JSONField(required=False, default=dict)
    options = serializers.JSONField(required=False, help_text="Diagram options (alias for parameters)")
    
    def validate(self, data):
        # Accept either 'project' or 'project_id'
        project = data.get('project') or data.get('project_id')
        if not project:
            raise serializers.ValidationError({
                "project": "Either 'project' or 'project_id' field is required."
            })
        
        # Normalize to 'project' for internal use
        data['project'] = project
        if 'project_id' in data:
            data.pop('project_id')
        
        # Accept either 'options' or 'parameters' (options takes precedence)
        options = data.get('options') or data.get('parameters', {})
        data['parameters'] = options
        if 'options' in data:
            data.pop('options')
        
        return data


class DiagramResponseSerializer(serializers.Serializer):
    diagram_type = serializers.CharField()
    data = serializers.CharField()
    format = serializers.CharField()
    cached = serializers.BooleanField(default=False)
