"""
GitHub Code Fetcher Service

Fetches repository tree and file contents from GitHub API.
Handles authentication, rate limiting, and caching.
"""
import base64
import logging
from datetime import timedelta
from typing import Dict, List, Optional

from django.core.cache import cache
from django.utils import timezone

import requests

logger = logging.getLogger(__name__)


class GitHubCodeFetcher:
    """
    Fetches code from GitHub repositories using GitHub API.

    Handles authentication, rate limiting, and intelligent caching.
    """

    def __init__(self, integration):
        """
        Initialize fetcher with GitHub integration.

        Args:
            integration: GitHubIntegration model instance
        """
        self.integration = integration
        self.base_url = "https://api.github.com"
        self.access_token = integration.get_access_token()

        if not self.access_token:
            raise ValueError(
                "GitHub access token not found. Please reconnect the integration."
            )

    def _get_headers(self) -> Dict:
        """Get headers for GitHub API requests."""
        return {
            "Authorization": f"token {self.access_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "FICCT-Scrum-Backend",
        }

    def _make_request(self, url: str, method: str = "GET") -> Dict:
        """
        Make authenticated request to GitHub API.

        Args:
            url: API endpoint URL
            method: HTTP method

        Returns:
            Response JSON

        Raises:
            ValueError: On API errors
        """
        try:
            response = requests.request(
                method, url, headers=self._get_headers(), timeout=30
            )

            # Check rate limit
            remaining = response.headers.get("X-RateLimit-Remaining")
            if remaining and int(remaining) < 10:
                logger.warning(
                    f"GitHub API rate limit low: {remaining} requests remaining"
                )

            if response.status_code == 403 and "rate limit" in response.text.lower():
                raise ValueError(
                    "GitHub API rate limit exceeded. Please try again later."
                )

            if response.status_code == 401:
                raise ValueError(
                    "GitHub access token is invalid or expired. Please reconnect the integration."
                )

            if response.status_code == 404:
                raise ValueError(
                    f"Repository '{self.integration.repository_owner}/{self.integration.repository_name}' "
                    f"not found or not accessible."
                )

            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            logger.error(f"GitHub API request failed: {str(e)}")
            raise ValueError(f"GitHub API request failed: {str(e)}")

    def fetch_repo_tree(self, use_cache: bool = True) -> List[Dict]:
        """
        Fetch complete repository tree (all files and directories).

        Args:
            use_cache: Whether to use cached result

        Returns:
            List of file/directory entries with paths and types
        """
        cache_key = f"github_tree_{self.integration.id}"

        if use_cache:
            cached = cache.get(cache_key)
            if cached:
                logger.info(
                    f"Using cached repository tree for {self.integration.repository_name}"
                )
                return cached

        # Get default branch
        repo_url = (
            f"{self.base_url}/repos/{self.integration.repository_owner}/"
            f"{self.integration.repository_name}"
        )
        repo_data = self._make_request(repo_url)
        default_branch = repo_data.get("default_branch", "main")

        # Get tree recursively
        tree_url = (
            f"{self.base_url}/repos/{self.integration.repository_owner}/"
            f"{self.integration.repository_name}/git/trees/{default_branch}?recursive=1"
        )

        logger.info(
            f"Fetching repository tree from GitHub: {self.integration.repository_name}"
        )
        tree_data = self._make_request(tree_url)

        tree = tree_data.get("tree", [])

        # Cache for 5 minutes
        cache.set(cache_key, tree, 300)

        logger.info(f"Fetched {len(tree)} items from repository tree")
        return tree

    def list_python_files(self) -> List[str]:
        """
        List all Python files in the repository.

        Returns:
            List of Python file paths
        """
        tree = self.fetch_repo_tree()

        python_files = [
            item["path"]
            for item in tree
            if item["type"] == "blob" and item["path"].endswith(".py")
        ]

        logger.info(f"Found {len(python_files)} Python files in repository")

        if not python_files:
            raise ValueError(
                "Repository contains no Python files. "
                "Currently only Python repositories are supported."
            )

        return python_files

    def fetch_file_content(self, file_path: str, use_cache: bool = True) -> str:
        """
        Fetch content of a specific file.

        Args:
            file_path: Path to file in repository
            use_cache: Whether to use cached result

        Returns:
            File content as string
        """
        cache_key = f"github_file_{self.integration.id}_{file_path}"

        if use_cache:
            cached = cache.get(cache_key)
            if cached:
                return cached

        url = (
            f"{self.base_url}/repos/{self.integration.repository_owner}/"
            f"{self.integration.repository_name}/contents/{file_path}"
        )

        logger.debug(f"Fetching file content: {file_path}")
        data = self._make_request(url)

        # Decode base64 content
        content_b64 = data.get("content", "")
        if not content_b64:
            return ""

        try:
            content = base64.b64decode(content_b64).decode("utf-8")
        except Exception as e:
            logger.warning(f"Failed to decode file {file_path}: {str(e)}")
            content = ""

        # Cache for 5 minutes
        cache.set(cache_key, content, 300)

        return content

    def fetch_multiple_files(
        self, file_paths: List[str], max_files: int = 100
    ) -> Dict[str, str]:
        """
        Fetch content of multiple files.

        Args:
            file_paths: List of file paths
            max_files: Maximum number of files to fetch

        Returns:
            Dict mapping file path to content
        """
        if len(file_paths) > max_files:
            logger.warning(
                f"Repository has {len(file_paths)} Python files. "
                f"Analyzing first {max_files} files."
            )
            file_paths = file_paths[:max_files]

        results = {}

        for i, path in enumerate(file_paths, 1):
            try:
                content = self.fetch_file_content(path)
                results[path] = content

                if i % 10 == 0:
                    logger.info(f"Fetched {i}/{len(file_paths)} files")

            except Exception as e:
                logger.warning(f"Failed to fetch {path}: {str(e)}")
                continue

        logger.info(f"Successfully fetched {len(results)} files")
        return results

    def clear_cache(self):
        """Clear cached data for this repository."""
        cache_key_tree = f"github_tree_{self.integration.id}"
        cache.delete(cache_key_tree)
        logger.info(f"Cleared cache for repository {self.integration.repository_name}")
