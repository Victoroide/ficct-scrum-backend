import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from django.utils import timezone
from github import Github, GithubException


class GitHubService:
    SMART_COMMIT_KEYWORDS = [
        "close",
        "closes",
        "closed",
        "fix",
        "fixes",
        "fixed",
        "resolve",
        "resolves",
        "resolved",
    ]

    def __init__(self):
        pass  # noqa: F821

    def parse_repository_url(self, repo_url: str) -> Tuple[str, str]:
        parsed = urlparse(repo_url)
        path_parts = parsed.path.strip("/").split("/")

        if len(path_parts) < 2:
            raise ValueError("Invalid repository URL format")

        owner = path_parts[0]
        repo_name = path_parts[1].replace(".git", "")

        return owner, repo_name

    def connect_repository(
        self, project, repo_url: str, access_token: str
    ) -> "GitHubIntegration":
        from apps.integrations.models import GitHubIntegration

        owner, repo_name = self.parse_repository_url(repo_url)

        if not self.verify_token(access_token, owner, repo_name):
            raise ValueError("Invalid access token or repository not accessible")

        integration, created = GitHubIntegration.objects.get_or_create(
            project=project,
            defaults={
                "repository_url": repo_url,
                "repository_owner": owner,
                "repository_name": repo_name,
            },
        )

        integration.set_access_token(access_token)
        integration.repository_url = repo_url
        integration.repository_owner = owner
        integration.repository_name = repo_name
        integration.is_active = True
        integration.save()

        return integration

    def verify_token(self, access_token: str, owner: str, repo_name: str) -> bool:
        try:
            g = Github(access_token)
            repo = g.get_repo(f"{owner}/{repo_name}")
            return repo is not None
        except GithubException:
            return False

    def sync_commits(
        self, repository: "GitHubIntegration", since: Optional[datetime] = None
    ) -> int:
        from apps.integrations.models import GitHubCommit

        # Validate repository configuration before attempting sync
        if not repository.repository_url:
            raise ValueError("Repository URL not configured. Please reconnect the integration.")
        
        if not repository.repository_owner or not repository.repository_name:
            raise ValueError(
                f"Repository owner/name not properly configured. "
                f"Owner: {repository.repository_owner}, Name: {repository.repository_name}. "
                f"Please reconnect the integration."
            )
        
        access_token = repository.get_access_token()
        if not access_token:
            raise ValueError("GitHub access token not found. Please reconnect the integration.")

        try:
            repository.sync_status = "syncing"
            repository.save()

            g = Github(access_token)
            repo_full_name = repository.repository_full_name
            
            # Log what we're trying to sync
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[Sync Commits] Attempting to sync: {repo_full_name}")
            
            repo = g.get_repo(repo_full_name)

            since_date = since or (timezone.now() - timedelta(days=30))
            commits = repo.get_commits(since=since_date)

            synced_count = 0
            for commit in commits[:100]:
                commit_obj, created = GitHubCommit.objects.get_or_create(
                    repository=repository,
                    sha=commit.sha,
                    defaults={
                        "message": commit.commit.message,
                        "author_name": commit.commit.author.name or "Unknown",
                        "author_email": commit.commit.author.email or "",
                        "commit_date": commit.commit.author.date,
                        "url": commit.html_url,
                    },
                )

                if created:
                    synced_count += 1

                    if repository.auto_link_commits:
                        self.link_commit_to_issues(commit_obj)

                    if repository.smart_commits_enabled:
                        self.process_smart_commit(commit_obj)

            repository.sync_status = "idle"
            repository.last_sync_at = timezone.now()
            repository.save()

            return synced_count

        except GithubException as e:
            repository.sync_status = "error"
            repository.save()
            
            # Provide specific error messages based on GitHub API status
            if e.status == 404:
                raise ValueError(
                    f"Repository '{repo_full_name}' not found on GitHub. "
                    f"Please verify the repository exists and is accessible."
                )
            elif e.status == 401:
                raise ValueError(
                    "GitHub access token is invalid or expired. "
                    "Please reconnect the integration to refresh the token."
                )
            elif e.status == 403:
                raise ValueError(
                    "GitHub access forbidden. Your token may lack required permissions (repo scope). "
                    "Please reconnect with proper permissions."
                )
            else:
                raise Exception(f"GitHub API error ({e.status}): {str(e)}")

    def sync_pull_requests(self, repository: "GitHubIntegration") -> int:
        from apps.integrations.models import GitHubPullRequest

        try:
            g = Github(repository.get_access_token())
            repo = g.get_repo(repository.repository_full_name)

            pulls = repo.get_pulls(state="all", sort="updated", direction="desc")

            synced_count = 0
            for pr in pulls[:50]:
                state = "merged" if pr.merged else pr.state
                pr_obj, created = GitHubPullRequest.objects.update_or_create(
                    repository=repository,
                    pr_number=pr.number,
                    defaults={
                        "title": pr.title,
                        "state": state,
                        "body": pr.body or "",
                        "base_branch": pr.base.ref,
                        "head_branch": pr.head.ref,
                        "author": pr.user.login if pr.user else "Unknown",
                        "url": pr.html_url,
                        "additions": pr.additions,
                        "deletions": pr.deletions,
                        "changed_files": pr.changed_files,
                        "commits_count": pr.commits,
                        "merged_at": pr.merged_at,
                        "closed_at": pr.closed_at,
                        "created_at": pr.created_at,
                        "updated_at": pr.updated_at,
                    },
                )

                if created:
                    synced_count += 1

                issue_keys = self.parse_commit_message(pr.title + " " + (pr.body or ""))
                if issue_keys:
                    self.link_pr_to_issues(pr_obj, issue_keys)

            return synced_count

        except GithubException as e:
            raise Exception(f"GitHub API error: {str(e)}")

    def parse_commit_message(self, message: str) -> List[str]:
        pattern = r"\b([A-Z]+-\d+)\b"
        matches = re.findall(pattern, message)
        return list(set(matches))

    def link_commit_to_issues(self, commit: "GitHubCommit") -> int:
        from apps.projects.models import Issue

        issue_keys = self.parse_commit_message(commit.message)
        if not issue_keys:
            return 0

        project = commit.repository.project
        linked_count = 0

        for issue_key in issue_keys:
            try:
                issue = Issue.objects.get(project=project, key=issue_key.split("-")[-1])
                commit.linked_issues.add(issue)
                linked_count += 1
            except Issue.DoesNotExist:
                continue

        return linked_count

    def link_pr_to_issues(self, pr: "GitHubPullRequest", issue_keys: List[str]) -> int:
        from apps.projects.models import Issue

        project = pr.repository.project
        linked_count = 0

        for issue_key in issue_keys:
            try:
                issue = Issue.objects.get(project=project, key=issue_key.split("-")[-1])
                pr.linked_issues.add(issue)
                linked_count += 1
            except Issue.DoesNotExist:
                continue

        return linked_count

    def process_smart_commit(self, commit: "GitHubCommit") -> bool:
        from apps.projects.models import Issue, WorkflowStatus
        from apps.reporting.models import ActivityLog

        message_lower = commit.message.lower()

        for keyword in self.SMART_COMMIT_KEYWORDS:
            if keyword in message_lower:
                issue_keys = self.parse_commit_message(commit.message)

                for issue_key in issue_keys:
                    try:
                        project = commit.repository.project
                        issue = Issue.objects.get(
                            project=project, key=issue_key.split("-")[-1]
                        )

                        done_status = WorkflowStatus.objects.filter(
                            project=project, category="done"
                        ).first()

                        if done_status and issue.status != done_status:
                            old_status = issue.status
                            issue.status = done_status
                            issue.resolved_at = timezone.now()
                            issue.save()

                            ActivityLog.objects.create(
                                user=issue.reporter,
                                action_type="transitioned",
                                content_type=ContentType.objects.get_for_model(Issue),
                                object_id=str(issue.id),
                                object_repr=str(issue),
                                project=project,
                                changes={
                                    "status": {
                                        "old": str(old_status),
                                        "new": str(done_status),
                                    },
                                    "reason": f"Smart commit {commit.short_sha}",
                                },
                            )

                            return True

                    except Issue.DoesNotExist:
                        continue

        return False

    def calculate_code_metrics(self, repository: "GitHubIntegration") -> Dict:
        from apps.integrations.models import GitHubCommit, GitHubPullRequest

        commits = GitHubCommit.objects.filter(repository=repository)
        prs = GitHubPullRequest.objects.filter(repository=repository)

        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_commits = commits.filter(commit_date__gte=thirty_days_ago)

        metrics = {
            "total_commits": commits.count(),
            "total_pull_requests": prs.count(),
            "commits_last_30_days": recent_commits.count(),
            "open_prs": prs.filter(state="open").count(),
            "merged_prs": prs.filter(state="merged").count(),
            "closed_prs": prs.filter(state="closed").count(),
            "avg_commits_per_day": round(recent_commits.count() / 30, 2),
            "top_contributors": self._get_top_contributors(recent_commits),
            "commit_frequency": self._get_commit_frequency(recent_commits),
        }

        return metrics

    def _get_top_contributors(self, commits) -> List[Dict]:
        from django.db.models import Count

        contributors = (
            commits.values("author_email", "author_name")
            .annotate(commit_count=Count("id"))
            .order_by("-commit_count")[:5]
        )

        return list(contributors)

    def _get_commit_frequency(self, commits) -> Dict:
        from django.db.models.functions import TruncDate

        frequency = (
            commits.annotate(date=TruncDate("commit_date"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        return {str(item["date"]): item["count"] for item in frequency}
