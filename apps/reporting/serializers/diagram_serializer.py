from rest_framework import serializers


class DiagramRequestSerializer(serializers.Serializer):
    DIAGRAM_TYPE_CHOICES = [
        ("workflow", "Workflow"),
        ("dependency", "Dependency"),
        ("roadmap", "Roadmap"),
        ("uml", "UML"),
        ("architecture", "Architecture"),
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
        
        return data


class DiagramResponseSerializer(serializers.Serializer):
    diagram_type = serializers.CharField()
    data = serializers.CharField()
    format = serializers.CharField()
    cached = serializers.BooleanField(default=False)
