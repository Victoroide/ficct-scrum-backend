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

    project = serializers.UUIDField(required=True, help_text="Project UUID")
    diagram_type = serializers.ChoiceField(choices=DIAGRAM_TYPE_CHOICES, required=True)
    format = serializers.ChoiceField(choices=FORMAT_CHOICES, default="svg")
    parameters = serializers.JSONField(required=False, default=dict)


class DiagramResponseSerializer(serializers.Serializer):
    diagram_type = serializers.CharField()
    data = serializers.CharField()
    format = serializers.CharField()
    cached = serializers.BooleanField(default=False)
