from django.urls import path, include
from rest_framework.routers import DefaultRouter
from app.iam.views import LoginView, UserMeView, UserViewSet, TeamViewSet, RoleViewSet, AuditLogViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='iam-users')
router.register(r'teams', TeamViewSet, basename='iam-teams')
router.register(r'roles', RoleViewSet, basename='iam-roles')
router.register(r'audit-logs', AuditLogViewSet, basename='iam-audit-logs')

urlpatterns = [
    path('login/', LoginView.as_view(), name='iam-login'),
    path('me/', UserMeView.as_view(), name='iam-me'),
    path('', include(router.urls)),
]
