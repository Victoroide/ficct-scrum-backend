from django.contrib.auth.password_validation import validate_password

from rest_framework import serializers

from apps.authentication.models import PasswordResetToken, User


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            user = User.objects.get(email=value, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError("No active user found with this email")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(
        write_only=True, validators=[validate_password]
    )
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError("Passwords don't match")
        return attrs

    def validate_token(self, value):
        try:
            reset_token = PasswordResetToken.objects.get(token=value)
            if not reset_token.is_valid:
                raise serializers.ValidationError("Token is invalid or expired")
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError("Invalid token")
        return value
