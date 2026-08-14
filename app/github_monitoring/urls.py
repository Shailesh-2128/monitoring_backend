from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProjectViewSet,
    repo_details_direct,
    repo_commits_direct,
    repo_pulls_direct,
    repo_issues_direct,
    repo_actions_direct,
    repo_releases_direct,
    github_webhook,
)

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')

urlpatterns = [
    path('', include(router.urls)),
    
    # GitHub Webhook Receiver Endpoint for Push & CI/CD events
    path('webhook/', github_webhook, name='github-webhook'),
    
    # Direct GitHub proxy endpoints matching specified GitHub route patterns
    path('repos/<str:owner>/<str:repo>/', repo_details_direct, name='repo-details-direct'),
    path('repos/<str:owner>/<str:repo>/commits/', repo_commits_direct, name='repo-commits-direct'),
    path('repos/<str:owner>/<str:repo>/pulls/', repo_pulls_direct, name='repo-pulls-direct'),
    path('repos/<str:owner>/<str:repo>/issues/', repo_issues_direct, name='repo-issues-direct'),
    path('repos/<str:owner>/<str:repo>/actions/runs/', repo_actions_direct, name='repo-actions-direct'),
    path('repos/<str:owner>/<str:repo>/releases/', repo_releases_direct, name='repo-releases-direct'),
]
