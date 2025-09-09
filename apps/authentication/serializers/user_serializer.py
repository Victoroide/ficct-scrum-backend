from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes
from apps.authentication.models import User


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'username', 'first_name', 'last_name', 'password', 'password_confirm']

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists")
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("User with this username already exists")
        return value

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data, password=password)
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(email=email, password=password)
            if not user:
                raise serializers.ValidationError('Invalid credentials')
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled')
            attrs['user'] = user
        else:
            raise serializers.ValidationError('Must include email and password')
        return attrs


class UserProfileNestedSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    
    class Meta:
        from apps.authentication.models import UserProfile
        model = UserProfile
        fields = [
            'avatar_url', 'bio', 'phone_number', 'timezone',
            'language', 'github_username', 'linkedin_url', 'website_url',
            'is_online', 'last_activity'
        ]
        read_only_fields = ['is_online', 'last_activity']
    
    @extend_schema_field(OpenApiTypes.STR)
    def get_avatar_url(self, obj):
        return obj.avatar.url if getattr(obj, 'avatar', None) else None


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    profile = UserProfileNestedSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'full_name', 'is_active', 'is_verified', 'is_staff', 'is_superuser',
            'date_joined', 'last_login', 'created_at', 'updated_at', 'profile'
        ]
        read_only_fields = [
            'id', 'date_joined', 'last_login', 'is_verified',
            'is_staff', 'is_superuser', 'created_at', 'updated_at'
        ]
