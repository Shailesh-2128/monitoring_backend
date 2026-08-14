from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from app.iam.models import Team, Role, UserProfile, AuditLog
from app.iam.serializers import (
    TeamSerializer, RoleSerializer, UserSerializer,
    CreateUserSerializer, UpdateUserSerializer, LoginSerializer, AuditLogSerializer
)
from app.iam.auth import generate_jwt_token, JWTAuthentication
from app.iam.permissions import module_permission

def get_user_permissions(user):
    """Helper function to compile permissions map for a user (combining Role & Team scope)."""
    profile = getattr(user, 'profile', None)
    if user.is_superuser or (profile and profile.is_superadmin):
        return {
            'servers': 'write',
            'websites': 'write',
            'databases': 'write',
            'github': 'write',
            'aws': 'write',
            'aws_costing': 'write',
            'iam': 'write',
        }

    all_modules = ['servers', 'websites', 'databases', 'github', 'aws', 'aws_costing', 'iam']
    res = {m: 'none' for m in all_modules}

    if profile and profile.role and profile.role.permissions:
        for m, lev in profile.role.permissions.items():
            if m in res:
                res[m] = lev

    if profile and profile.team and profile.team.permissions:
        level_order = {'none': 0, 'read': 1, 'write': 2}
        for m, t_lev in profile.team.permissions.items():
            if m in res:
                if level_order.get(t_lev, 0) > level_order.get(res[m], 0):
                    res[m] = t_lev

    return res

def log_audit_event(request, action, module, description):
    """Utility to record security audit logs."""
    try:
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            user_obj = None
            username_str = getattr(request, 'data', {}).get('username', 'Anonymous') if hasattr(request, 'data') else 'Anonymous'
        else:
            user_obj = user
            username_str = user.username

        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')

        AuditLog.objects.create(
            user=user_obj,
            username=username_str,
            action=action,
            module=module,
            description=description,
            ip_address=ip
        )
    except Exception as e:
        print(f"Failed to record audit log: {e}")


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        username_or_email = serializer.validated_data['username']
        password = serializer.validated_data['password']

        user = None
        if '@' in username_or_email:
            try:
                user_obj = User.objects.get(email__iexact=username_or_email)
                user = authenticate(username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None
        else:
            user = authenticate(username=username_or_email, password=password)

        if not user:
            log_audit_event(request, 'LOGIN_FAILED', 'iam', f"Failed login attempt for user/email '{username_or_email}'")
            return Response({'detail': 'Invalid username/email or password.'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            log_audit_event(request, 'LOGIN_DISABLED', 'iam', f"Disabled account login attempt for user '{user.username}'")
            return Response({'detail': 'Account is disabled.'}, status=status.HTTP_403_FORBIDDEN)

        profile, created = UserProfile.objects.get_or_create(user=user)

        token = generate_jwt_token(user)
        permissions = get_user_permissions(user)

        user_serializer = UserSerializer(user)
        user_data = user_serializer.data
        user_data['permissions'] = permissions

        log_audit_event(request, 'LOGIN_SUCCESS', 'iam', f"User '{user.username}' logged into system.")

        return Response({
            'token': token,
            'user': user_data
        }, status=status.HTTP_200_OK)


class UserMeView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        permissions = get_user_permissions(user)
        user_serializer = UserSerializer(user)
        user_data = user_serializer.data
        user_data['permissions'] = permissions
        return Response(user_data)


class UserViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [module_permission('iam')]
    queryset = User.objects.select_related('profile', 'profile__role', 'profile__team').order_by('-date_joined')
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        serializer = CreateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        role = None
        if data.get('role_id'):
            role = Role.objects.filter(id=data['role_id']).first()

        team = None
        if data.get('team_id'):
            team = Team.objects.filter(id=data['team_id']).first()

        user = User.objects.create_user(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', '')
        )

        UserProfile.objects.create(
            user=user,
            role=role,
            team=team,
            job_title=data.get('job_title', ''),
            is_superadmin=data.get('is_superadmin', False)
        )

        log_audit_event(request, 'USER_CREATE', 'iam', f"Created IAM user '{user.username}' ({user.email}) with role '{role.name if role else 'None'}'")

        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = UpdateUserSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if 'email' in data:
            user.email = data['email']
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'is_active' in data:
            user.is_active = data['is_active']
        if 'password' in data and data['password']:
            user.set_password(data['password'])
        user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        if 'job_title' in data:
            profile.job_title = data['job_title']
        if 'is_superadmin' in data:
            profile.is_superadmin = data['is_superadmin']
        if 'role_id' in data:
            profile.role = Role.objects.filter(id=data['role_id']).first() if data['role_id'] else None
        if 'team_id' in data:
            profile.team = Team.objects.filter(id=data['team_id']).first() if data['team_id'] else None
        profile.save()

        log_audit_event(request, 'USER_UPDATE', 'iam', f"Updated profile for user '{user.username}'")

        return Response(UserSerializer(user).data)

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        username = user.username
        res = super().destroy(request, *args, **kwargs)
        log_audit_event(request, 'USER_DELETE', 'iam', f"Deleted IAM user account '{username}'")
        return res


class TeamViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [module_permission('iam')]
    queryset = Team.objects.all().order_by('name')
    serializer_class = TeamSerializer

    def create(self, request, *args, **kwargs):
        res = super().create(request, *args, **kwargs)
        team_name = request.data.get('name', '')
        log_audit_event(request, 'TEAM_CREATE', 'iam', f"Created engineering team '{team_name}'")
        return res

    def destroy(self, request, *args, **kwargs):
        team = self.get_object()
        team_name = team.name
        res = super().destroy(request, *args, **kwargs)
        log_audit_event(request, 'TEAM_DELETE', 'iam', f"Deleted engineering team '{team_name}'")
        return res


class RoleViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [module_permission('iam')]
    queryset = Role.objects.all().order_by('id')
    serializer_class = RoleSerializer

    def create(self, request, *args, **kwargs):
        res = super().create(request, *args, **kwargs)
        role_name = request.data.get('name', '')
        log_audit_event(request, 'ROLE_CREATE', 'iam', f"Created custom role '{role_name}'")
        return res

    def destroy(self, request, *args, **kwargs):
        role = self.get_object()
        if role.is_system_role:
            return Response(
                {'detail': 'System built-in roles cannot be deleted.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        role_name = role.name
        res = super().destroy(request, *args, **kwargs)
        log_audit_event(request, 'ROLE_DELETE', 'iam', f"Deleted custom role '{role_name}'")
        return res


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [module_permission('iam')]
    serializer_class = AuditLogSerializer

    def get_queryset(self):
        queryset = AuditLog.objects.all().order_by('-timestamp')
        module_param = self.request.query_params.get('module')
        action_param = self.request.query_params.get('action')
        search_param = self.request.query_params.get('search')

        if module_param:
            queryset = queryset.filter(module=module_param)
        if action_param:
            queryset = queryset.filter(action=action_param)
        if search_param:
            queryset = queryset.filter(
                username__icontains=search_param
            ) | queryset.filter(
                description__icontains=search_param
            ) | queryset.filter(
                ip_address__icontains=search_param
            )
        return queryset[:200]
