from rest_framework import serializers

from apps.reporting.models import SavedFilter


class SavedFilterSerializer(serializers.ModelSerializer):
    filter_count = serializers.IntegerField(read_only=True)
    formatted_criteria = serializers.CharField(read_only=True)

    class Meta:
        model = SavedFilter
        fields = [
            "id",
            "name",
            "description",
            "user",
            "project",
            "filter_criteria",
            "is_public",
            "shared_with_team",
            "use_count",
            "last_used_at",
            "filter_count",
            "formatted_criteria",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "use_count",
            "last_used_at",
            "created_at",
            "updated_at",
        ]

    def validate_filter_criteria(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Filter criteria must be a JSON object")
        return value

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)
