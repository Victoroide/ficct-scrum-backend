import factory
from factory.django import DjangoModelFactory

from apps.integrations.models import GitHubCommit, GitHubIntegration, GitHubPullRequest


class GitHubIntegrationFactory(DjangoModelFactory):
    class Meta:
        model = GitHubIntegration

    project = factory.SubFactory("apps.projects.tests.factories.ProjectFactory")
    repository_url = factory.Sequence(
        lambda n: f"https://github.com/testorg/testrepo{n}"
    )
    repository_owner = factory.Sequence(lambda n: f"testorg{n}")
    repository_name = factory.Sequence(lambda n: f"testrepo{n}")
    access_token = b"encrypted_token_placeholder"
    is_active = True
    sync_status = "idle"
    auto_link_commits = True
    smart_commits_enabled = True
    sync_pull_requests = True


class GitHubCommitFactory(DjangoModelFactory):
    class Meta:
        model = GitHubCommit

    repository = factory.SubFactory(GitHubIntegrationFactory)
    sha = factory.Sequence(lambda n: f"abc123def456{n:010d}")
    message = factory.Faker("sentence")
    author_name = factory.Faker("name")
    author_email = factory.Faker("email")
    commit_date = factory.Faker("date_time_this_year")
    branch = "main"
    url = factory.Sequence(
        lambda n: f"https://github.com/testorg/testrepo/commit/abc123{n}"
    )


class GitHubPullRequestFactory(DjangoModelFactory):
    class Meta:
        model = GitHubPullRequest

    repository = factory.SubFactory(GitHubIntegrationFactory)
    pr_number = factory.Sequence(lambda n: n + 1)
    title = factory.Faker("sentence")
    state = "open"
    body = factory.Faker("text")
    base_branch = "main"
    head_branch = factory.Sequence(lambda n: f"feature-branch-{n}")
    author = factory.Faker("user_name")
    url = factory.Sequence(lambda n: f"https://github.com/testorg/testrepo/pull/{n}")
    additions = factory.Faker("random_int", min=1, max=500)
    deletions = factory.Faker("random_int", min=1, max=200)
    changed_files = factory.Faker("random_int", min=1, max=50)
    commits_count = factory.Faker("random_int", min=1, max=20)
    created_at = factory.Faker("date_time_this_year")
    updated_at = factory.Faker("date_time_this_year")
