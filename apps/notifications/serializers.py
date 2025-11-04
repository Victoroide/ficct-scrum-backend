"""
Notification serializers for API responses.

Provides serialization for notifications and preferences.
"""

from rest_framework import serializers

from apps.notifications.models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for Notification model.
    
    Provides complete notification data with proper field types and validation.
    """
    
    # Read-only computed fields
    id = serializers.UUIDField(read_only=True)
    recipient_email = serializers.EmailField(source='recipient.email', read_only=True)
    recipient_name = serializers.SerializerMethodField()
    type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id',
            'recipient',
            'recipient_email',
            'recipient_name',
            'notification_type',
            'type_display',
            'title',
            'message',
            'link',
            'data',
            'is_read',
            'read_at',
            'email_sent',
            'slack_sent',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'recipient',
            'recipient_email',
            'recipient_name',
            'type_display',
            'notification_type',
            'title',
            'message',
            'link',
            'data',
            'email_sent',
            'slack_sent',
            'created_at',
            'read_at',
        ]
    
    def get_recipient_name(self, obj):
        """Get recipient full name."""
        if obj.recipient.first_name or obj.recipient.last_name:
            return f"{obj.recipient.first_name} {obj.recipient.last_name}".strip()
        return obj.recipient.email


class NotificationUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating notification (mark as read).
    
    Only allows updating is_read field.
    """
    
    class Meta:
        model = Notification
        fields = ['is_read']
    
    def update(self, instance, validated_data):
        """Update notification and set read_at timestamp."""
        if validated_data.get('is_read') and not instance.is_read:
            # Use the model's mark_as_read method which sets read_at
            instance.mark_as_read()
        elif not validated_data.get('is_read', True):
            # If marking as unread, clear read_at
            instance.is_read = False
            instance.read_at = None
            instance.save(update_fields=['is_read', 'read_at'])
        
        return instance


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """
    Serializer for NotificationPreference model.
    
    Provides user notification preferences management.
    """
    
    id = serializers.UUIDField(read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = NotificationPreference
        fields = [
            'id',
            'user',
            'user_email',
            'email_enabled',
            'in_app_enabled',
            'slack_enabled',
            'notification_types',
            'digest_enabled',
            'digest_time',
            'quiet_hours_enabled',
            'quiet_hours_start',
            'quiet_hours_end',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'user', 'user_email', 'created_at', 'updated_at']
