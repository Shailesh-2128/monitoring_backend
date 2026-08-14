from rest_framework import serializers
from django.contrib.auth.models import User
from app.iam.models import Team, Role, UserProfile, AuditLog, MODULE_CHOICES, PERMISSION_LEVEL_CHOICES

class TeamSerializer(serializers.ModelSerializer):
    members_count = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = ['id', 'name', 'description', 'permissions', 'members_count', 'created_at', 'updated_at']

    def get_members_count(self, obj):
        return obj.members.count()

class RoleSerializer(serializers.ModelSerializer):
    profiles_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ['id', 'name', 'description', 'is_system_role', 'permissions', 'profiles_count', 'created_at', 'updated_at']

    def get_profiles_count(self, obj):
        return obj.profiles.count()

    def validate_permissions(self, value):
        valid_modules = {choice[0] for choice in MODULE_CHOICES}
        valid_levels = {choice[0] for choice in PERMISSION_LEVEL_CHOICES}
        
        if not isinstance(value, dict):
            raise serializers.ValidationError("Permissions must be a dictionary.")
        
        for mod, level in value.items():
            if mod not in valid_modules:
                raise serializers.ValidationError(f"Invalid module: '{mod}'. Must be one of {list(valid_modules)}")
            if level not in valid_levels:
                raise serializers.ValidationError(f"Invalid access level '{level}' for module '{mod}'. Must be one of {list(valid_levels)}")
        return value

class UserProfileSerializer(serializers.ModelSerializer):
    role_details = RoleSerializer(source='role', read_only=True)
    team_details = TeamSerializer(source='team', read_only=True)

    class Meta:
        model = UserProfile
        fields = ['id', 'is_superadmin', 'job_title', 'role', 'team', 'role_details', 'team_details']

class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 'date_joined', 'last_login', 'profile']

class CreateUserSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    job_title = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    role_id = serializers.IntegerField(required=False, allow_null=True)
    team_id = serializers.IntegerField(required=False, allow_null=True)
    is_superadmin = serializers.BooleanField(default=False)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email address already exists.")
        return value

class UpdateUserSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    job_title = serializers.CharField(max_length=100, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, min_length=6, allow_blank=True)
    role_id = serializers.IntegerField(required=False, allow_null=True)
    team_id = serializers.IntegerField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)
    is_superadmin = serializers.BooleanField(required=False)

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ['id', 'user', 'username', 'action', 'module', 'description', 'ip_address', 'timestamp']
