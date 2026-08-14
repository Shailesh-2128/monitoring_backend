from datetime import datetime
import requests
from typing import Dict, Any, List, Optional


class GitHubService:
    BASE_URL = "https://api.github.com"

    @classmethod
    def get_headers(cls, token: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "DeployOps-Monitoring-Backend"
        }
        if token and token.strip():
            clean_token = token.strip()
            if clean_token.startswith("Bearer ") or clean_token.startswith("token "):
                headers["Authorization"] = clean_token
            else:
                headers["Authorization"] = f"Bearer {clean_token}"
        return headers

    @classmethod
    def get_repo_details(cls, owner: str, repo: str, token: Optional[str] = None) -> Dict[str, Any]:
        headers = cls.get_headers(token)
        url = f"{cls.BASE_URL}/repos/{owner}/{repo}"
        
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return {
                "error": f"Failed to fetch repo details from GitHub: {resp.status_code}",
                "detail": resp.json() if resp.headers.get('content-type', '').startswith('application/json') else resp.text
            }
        
        data = resp.json()
        
        # Fetch latest commit
        latest_commit = cls.get_latest_commit(owner, repo, token, default_branch=data.get("default_branch", "main"))
        
        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "full_name": data.get("full_name"),
            "owner": data.get("owner", {}).get("login"),
            "description": data.get("description"),
            "default_branch": data.get("default_branch", "main"),
            "stars": data.get("stargazers_count", 0),
            "forks": data.get("forks_count", 0),
            "open_issues_count": data.get("open_issues_count", 0),
            "visibility": data.get("visibility", "private" if data.get("private") else "public"),
            "is_private": data.get("private", False),
            "html_url": data.get("html_url"),
            "updated_at": data.get("updated_at"),
            "latest_commit": latest_commit
        }

    @classmethod
    def get_latest_commit(cls, owner: str, repo: str, token: Optional[str] = None, default_branch: str = "main") -> Optional[Dict[str, Any]]:
        commits = cls.get_commits(owner, repo, token, branch=default_branch, limit=1)
        if commits and isinstance(commits, list) and len(commits) > 0 and "error" not in commits[0]:
            return commits[0]
        return None

    @classmethod
    def get_commits(cls, owner: str, repo: str, token: Optional[str] = None, branch: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        headers = cls.get_headers(token)
        url = f"{cls.BASE_URL}/repos/{owner}/{repo}/commits"
        params = {"per_page": limit}
        if branch:
            params["sha"] = branch
            
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code == 404 and branch:
            # Fall back to default repository branch if specified branch fails
            resp = requests.get(url, headers=headers, params={"per_page": limit}, timeout=10)

        if resp.status_code != 200:
            return [{
                "error": f"Failed to fetch commits: {resp.status_code}",
                "detail": resp.text
            }]
            
        raw_commits = resp.json()
        commits = []
        for item in raw_commits:
            commit_obj = item.get("commit", {})
            author_obj = item.get("author") or {}
            committer_obj = commit_obj.get("author") or {}
            
            sha = item.get("sha", "")
            commits.append({
                "sha": sha,
                "short_sha": sha[:7] if sha else "",
                "message": commit_obj.get("message", "").split("\n")[0],
                "full_message": commit_obj.get("message", ""),
                "author": {
                    "name": committer_obj.get("name", "Unknown"),
                    "email": committer_obj.get("email", ""),
                    "username": author_obj.get("login", committer_obj.get("name", "Unknown")),
                    "avatar_url": author_obj.get("avatar_url", "")
                },
                "date": committer_obj.get("date"),
                "html_url": item.get("html_url")
            })
        return commits

    @classmethod
    def get_pull_requests(cls, owner: str, repo: str, token: Optional[str] = None, limit: int = 30) -> Dict[str, Any]:
        headers = cls.get_headers(token)
        url = f"{cls.BASE_URL}/repos/{owner}/{repo}/pulls"
        params = {"state": "all", "per_page": limit}
        
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code != 200:
            return {
                "open_count": 0, "merged_count": 0, "closed_count": 0, "total_count": 0,
                "pull_requests": [], "error": f"Failed to fetch PRs: {resp.status_code}"
            }
            
        raw_prs = resp.json()
        prs = []
        open_cnt = 0
        merged_cnt = 0
        closed_cnt = 0
        
        for item in raw_prs:
            state = item.get("state")
            merged_at = item.get("merged_at")
            
            if state == "open":
                open_cnt += 1
                pr_status = "open"
            elif merged_at:
                merged_cnt += 1
                pr_status = "merged"
            else:
                closed_cnt += 1
                pr_status = "closed"
                
            user = item.get("user") or {}
            prs.append({
                "id": item.get("id"),
                "number": item.get("number"),
                "title": item.get("title"),
                "state": pr_status,
                "raw_state": state,
                "is_merged": bool(merged_at),
                "author": {
                    "username": user.get("login", "Unknown"),
                    "avatar_url": user.get("avatar_url", "")
                },
                "head_branch": item.get("head", {}).get("ref"),
                "base_branch": item.get("base", {}).get("ref"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "closed_at": item.get("closed_at"),
                "merged_at": merged_at,
                "html_url": item.get("html_url")
            })
            
        return {
            "open_count": open_cnt,
            "merged_count": merged_cnt,
            "closed_count": closed_cnt,
            "total_count": len(prs),
            "pull_requests": prs
        }

    @classmethod
    def get_issues(cls, owner: str, repo: str, token: Optional[str] = None, limit: int = 30) -> Dict[str, Any]:
        headers = cls.get_headers(token)
        url = f"{cls.BASE_URL}/repos/{owner}/{repo}/issues"
        params = {"state": "all", "per_page": limit}
        
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code != 200:
            return {
                "open_count": 0, "closed_count": 0, "total_count": 0,
                "issues": [], "error": f"Failed to fetch issues: {resp.status_code}"
            }
            
        raw_issues = resp.json()
        issues = []
        open_cnt = 0
        closed_cnt = 0
        
        for item in raw_issues:
            # Exclude pull requests which GitHub includes in issues endpoint
            if "pull_request" in item:
                continue
                
            state = item.get("state")
            if state == "open":
                open_cnt += 1
            else:
                closed_cnt += 1
                
            user = item.get("user") or {}
            labels = [{"name": l.get("name"), "color": l.get("color")} for l in item.get("labels", [])]
            
            issues.append({
                "id": item.get("id"),
                "number": item.get("number"),
                "title": item.get("title"),
                "state": state,
                "author": {
                    "username": user.get("login", "Unknown"),
                    "avatar_url": user.get("avatar_url", "")
                },
                "labels": labels,
                "comments_count": item.get("comments", 0),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "closed_at": item.get("closed_at"),
                "html_url": item.get("html_url")
            })
            
        return {
            "open_count": open_cnt,
            "closed_count": closed_cnt,
            "total_count": len(issues),
            "issues": issues
        }

    @classmethod
    def get_actions_runs(cls, owner: str, repo: str, token: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
        headers = cls.get_headers(token)
        url = f"{cls.BASE_URL}/repos/{owner}/{repo}/actions/runs"
        params = {"per_page": limit}
        
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code != 200:
            return {
                "total_count": 0, "workflow_runs": [], "error": f"Failed to fetch actions: {resp.status_code}"
            }
            
        data = resp.json()
        raw_runs = data.get("workflow_runs", [])
        runs = []
        
        for item in raw_runs:
            created_at_str = item.get("created_at") or item.get("run_started_at")
            updated_at_str = item.get("updated_at")
            
            duration_sec = 0
            if created_at_str and updated_at_str:
                try:
                    t1 = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    t2 = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
                    duration_sec = int((t2 - t1).total_seconds())
                except Exception:
                    duration_sec = 0

            # Formatted duration string (e.g. "3 min 12 sec")
            if duration_sec >= 60:
                mins = duration_sec // 60
                secs = duration_sec % 60
                duration_formatted = f"{mins} min {secs}s" if secs else f"{mins} min"
            elif duration_sec > 0:
                duration_formatted = f"{duration_sec}s"
            else:
                duration_formatted = "Running..." if item.get("status") == "in_progress" else "0s"

            actor = item.get("actor") or {}
            
            runs.append({
                "id": item.get("id"),
                "name": item.get("name") or "Workflow Run",
                "status": item.get("status"), # e.g. queued, in_progress, completed
                "conclusion": item.get("conclusion"), # e.g. success, failure, cancelled, skipped
                "event": item.get("event"),
                "head_branch": item.get("head_branch"),
                "head_sha": item.get("head_sha", "")[:7],
                "actor": {
                    "username": actor.get("login", "Unknown"),
                    "avatar_url": actor.get("avatar_url", "")
                },
                "started_at": created_at_str,
                "updated_at": updated_at_str,
                "duration_seconds": duration_sec,
                "duration_formatted": duration_formatted,
                "html_url": item.get("html_url")
            })
            
        return {
            "total_count": data.get("total_count", len(runs)),
            "workflow_runs": runs
        }

    @classmethod
    def get_releases(cls, owner: str, repo: str, token: Optional[str] = None, limit: int = 15) -> Dict[str, Any]:
        headers = cls.get_headers(token)
        url = f"{cls.BASE_URL}/repos/{owner}/{repo}/releases"
        params = {"per_page": limit}
        
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code != 200:
            return {
                "total_count": 0, "releases": [], "error": f"Failed to fetch releases: {resp.status_code}"
            }
            
        raw_releases = resp.json()
        releases = []
        
        for item in raw_releases:
            author = item.get("author") or {}
            releases.append({
                "id": item.get("id"),
                "tag_name": item.get("tag_name"),
                "name": item.get("name") or item.get("tag_name"),
                "body": item.get("body", ""),
                "draft": item.get("draft", False),
                "prerelease": item.get("prerelease", False),
                "published_at": item.get("published_at") or item.get("created_at"),
                "author": {
                    "username": author.get("login", "Unknown"),
                    "avatar_url": author.get("avatar_url", "")
                },
                "html_url": item.get("html_url")
            })
            
        return {
            "total_count": len(releases),
            "latest_release": releases[0] if len(releases) > 0 else None,
            "releases": releases
        }
