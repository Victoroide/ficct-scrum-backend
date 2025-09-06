from rest_framework import serializers


class SystemHealthSerializer(serializers.Serializer):
    total_logs_24h = serializers.IntegerField()
    error_logs_24h = serializers.IntegerField()
    error_logs_1h = serializers.IntegerField()
    active_alerts = serializers.IntegerField()
    critical_errors_24h = serializers.IntegerField()
    unique_users_24h = serializers.IntegerField()
