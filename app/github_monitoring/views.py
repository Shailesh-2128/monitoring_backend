from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from .models import Project
from .serializers import ProjectSerializer
from .services import GitHubService


from app.iam.auth import JWTAuthentication
from app.iam.permissions import module_permission


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [module_permission('github')]

    def _get_project_token(self, project: Project):
        return project.get_decrypted_token()

    @action(detail=True, methods=['get'], url_path='repo')
    def repo(self, request, pk=None):
        project = self.get_object()
        token = self._get_project_token(project)
        details = GitHubService.get_repo_details(project.github_owner, project.github_repo, token)
        return Response(details)

    @action(detail=True, methods=['get'], url_path='commits')
    def commits(self, request, pk=None):
        project = self.get_object()
        token = self._get_project_token(project)
        branch = request.query_params.get('branch', project.default_branch)
        commits = GitHubService.get_commits(project.github_owner, project.github_repo, token, branch=branch)
        return Response(commits)

    @action(detail=True, methods=['get'], url_path='pulls')
    def pulls(self, request, pk=None):
        project = self.get_object()
        token = self._get_project_token(project)
        pulls = GitHubService.get_pull_requests(project.github_owner, project.github_repo, token)
        return Response(pulls)

    @action(detail=True, methods=['get'], url_path='issues')
    def issues(self, request, pk=None):
        project = self.get_object()
        token = self._get_project_token(project)
        issues = GitHubService.get_issues(project.github_owner, project.github_repo, token)
        return Response(issues)

    @action(detail=True, methods=['get'], url_path='actions')
    def actions(self, request, pk=None):
        project = self.get_object()
        token = self._get_project_token(project)
        runs = GitHubService.get_actions_runs(project.github_owner, project.github_repo, token)
        return Response(runs)

    @action(detail=True, methods=['get'], url_path='releases')
    def releases(self, request, pk=None):
        project = self.get_object()
        token = self._get_project_token(project)
        releases = GitHubService.get_releases(project.github_owner, project.github_repo, token)
        return Response(releases)

    @action(detail=True, methods=['get'], url_path='overview')
    def overview(self, request, pk=None):
        project = self.get_object()
        token = self._get_project_token(project)
        
        repo_data = GitHubService.get_repo_details(project.github_owner, project.github_repo, token)
        if repo_data and not repo_data.get("error") and repo_data.get("default_branch"):
            real_branch = repo_data["default_branch"]
            if project.default_branch != real_branch:
                project.default_branch = real_branch
                project.save(update_fields=['default_branch', 'updated_at'])

        pulls_data = GitHubService.get_pull_requests(project.github_owner, project.github_repo, token, limit=10)
        issues_data = GitHubService.get_issues(project.github_owner, project.github_repo, token, limit=10)
        actions_data = GitHubService.get_actions_runs(project.github_owner, project.github_repo, token, limit=10)
        releases_data = GitHubService.get_releases(project.github_owner, project.github_repo, token, limit=5)
        
        return Response({
            "project": ProjectSerializer(project).data,
            "repository": repo_data,
            "pull_requests": pulls_data,
            "issues": issues_data,
            "actions": actions_data,
            "releases": releases_data
        })


# Helper to get token for direct owner/repo routes
def get_token_for_owner_repo(owner: str, repo: str, request) -> str:
    # First look up Project in DB
    proj = Project.objects.filter(github_owner__iexact=owner, github_repo__iexact=repo).first()
    if proj and proj.github_token:
        return proj.get_decrypted_token()
    
    # Fallback to authorization header or query param
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    return request.query_params.get('token', '')


@api_view(['GET'])
def repo_details_direct(request, owner, repo):
    token = get_token_for_owner_repo(owner, repo, request)
    res = GitHubService.get_repo_details(owner, repo, token)
    return Response(res)


@api_view(['GET'])
def repo_commits_direct(request, owner, repo):
    token = get_token_for_owner_repo(owner, repo, request)
    branch = request.query_params.get('branch')
    res = GitHubService.get_commits(owner, repo, token, branch=branch)
    return Response(res)


@api_view(['GET'])
def repo_pulls_direct(request, owner, repo):
    token = get_token_for_owner_repo(owner, repo, request)
    res = GitHubService.get_pull_requests(owner, repo, token)
    return Response(res)


@api_view(['GET'])
def repo_issues_direct(request, owner, repo):
    token = get_token_for_owner_repo(owner, repo, request)
    res = GitHubService.get_issues(owner, repo, token)
    return Response(res)


@api_view(['GET'])
def repo_actions_direct(request, owner, repo):
    token = get_token_for_owner_repo(owner, repo, request)
    res = GitHubService.get_actions_runs(owner, repo, token)
    return Response(res)


@api_view(['GET'])
def repo_releases_direct(request, owner, repo):
    token = get_token_for_owner_repo(owner, repo, request)
    res = GitHubService.get_releases(owner, repo, token)
    return Response(res)


from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny
from rest_framework.decorators import permission_classes, authentication_classes
import json

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def github_webhook(request):
    """
    GitHub Webhook receiver endpoint for repository push events.
    Dispatches Telegram notifications to all active connected users.
    """
    event_type = request.headers.get('X-GitHub-Event', 'push')
    
    try:
        data = request.data if hasattr(request, 'data') else json.loads(request.body)
    except Exception:
        return Response({"error": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)

    if event_type == 'push':
        repo_data = data.get('repository', {})
        repo_name = repo_data.get('full_name') or repo_data.get('name', 'Unknown Repository')
        ref = data.get('ref', '')
        branch = ref.replace('refs/heads/', '') if ref.startswith('refs/heads/') else ref or 'main'
        
        pusher_data = data.get('pusher', {}) or data.get('sender', {})
        pusher = pusher_data.get('name') or pusher_data.get('login', 'GitHub User')
        
        commits = data.get('commits', [])
        head_commit = data.get('head_commit', {})
        commit_url = head_commit.get('url', '') or repo_data.get('html_url', '')

        try:
            from app.telegram_monitoring.services import TelegramService
            sent_count = TelegramService.send_github_push_alert(
                repo_name=repo_name,
                branch=branch,
                pusher=pusher,
                commits=commits,
                commit_url=commit_url
            )
            return Response({"status": "received", "event": "push", "notifications_sent": sent_count}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"status": "error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({"status": "ignored", "event": event_type}, status=status.HTTP_200_OK)

