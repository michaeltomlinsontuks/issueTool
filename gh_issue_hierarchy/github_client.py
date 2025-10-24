"""
GitHub operations wrapper.

Handles issue creation via gh CLI and sub-issue linking via PyGithub GraphQL.
Includes retry logic and error handling.
"""

import subprocess
import time
import re
from typing import Optional, List, Dict, Any
import logging

from github import Github, GithubException


logger = logging.getLogger(__name__)


class GitHubClientError(Exception):
    """Custom exception for GitHub operations."""

    pass


class GitHubClient:
    """
    Wrapper for GitHub operations.

    Uses hybrid approach:
    - gh CLI for issue creation (faster)
    - PyGithub for GraphQL operations (sub-issue linking)
    """

    def __init__(
        self,
        repository: str,
        retry_attempts: int = 3,
        retry_backoff_seconds: int = 5,
        timeout_seconds: int = 30,
    ):
        """
        Initialize GitHub client.

        Args:
            repository: GitHub repository in format 'owner/repo'
            retry_attempts: Number of retry attempts for failed operations
            retry_backoff_seconds: Initial backoff delay (exponential)
            timeout_seconds: Timeout for subprocess calls
        """
        self.repository = repository
        self.retry_attempts = retry_attempts
        self.retry_backoff_seconds = retry_backoff_seconds
        self.timeout_seconds = timeout_seconds

        # Initialize PyGithub with gh CLI token
        self.github = self._init_github()
        self.repo = self.github.get_repo(repository)

    def _init_github(self) -> Github:
        """
        Initialize PyGithub using gh CLI authentication.

        Returns:
            Authenticated Github instance

        Raises:
            GitHubClientError: If authentication fails
        """
        try:
            # Get token from gh CLI
            result = subprocess.run(
                ["gh", "auth", "token"],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            token = result.stdout.strip()
            return Github(token)
        except subprocess.CalledProcessError as e:
            raise GitHubClientError(
                f"Failed to get GitHub token. Is 'gh' CLI authenticated?\n{e.stderr}"
            )
        except FileNotFoundError:
            raise GitHubClientError("'gh' CLI not found. Please install GitHub CLI.")

    def _run_gh_command(self, args: List[str]) -> str:
        """
        Run gh CLI command with retry logic.

        Args:
            args: Command arguments

        Returns:
            Command output

        Raises:
            GitHubClientError: If command fails after all retries
        """
        for attempt in range(self.retry_attempts):
            try:
                result = subprocess.run(
                    ["gh"] + args,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    check=True,
                )
                return result.stdout.strip()
            except subprocess.CalledProcessError as e:
                logger.warning(
                    f"gh command failed (attempt {attempt + 1}/{self.retry_attempts}): {e.stderr}"
                )
                if attempt < self.retry_attempts - 1:
                    sleep_time = self.retry_backoff_seconds * (2**attempt)
                    logger.debug(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    raise GitHubClientError(f"gh command failed: {e.stderr}")
            except subprocess.TimeoutExpired:
                logger.warning(
                    f"gh command timed out (attempt {attempt + 1}/{self.retry_attempts})"
                )
                if attempt < self.retry_attempts - 1:
                    sleep_time = self.retry_backoff_seconds * (2**attempt)
                    time.sleep(sleep_time)
                else:
                    raise GitHubClientError("gh command timed out")

        raise GitHubClientError("gh command failed after all retries")

    def create_issue(
        self,
        title: str,
        body: Optional[str] = None,
        milestone: Optional[str] = None,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a GitHub issue using gh CLI.

        Args:
            title: Issue title
            body: Issue body/description
            milestone: Milestone name
            labels: List of label names
            assignees: List of assignee usernames

        Returns:
            Dictionary with:
                - issue_number: GitHub issue number
                - issue_url: Full URL to the issue
                - node_id: GraphQL node ID

        Raises:
            GitHubClientError: If issue creation fails
        """
        args = [
            "issue",
            "create",
            "--repo",
            self.repository,
            "--title",
            title,
        ]

        if body:
            args.extend(["--body", body])

        if milestone:
            args.extend(["--milestone", milestone])

        if labels:
            for label in labels:
                args.extend(["--label", label])

        if assignees:
            for assignee in assignees:
                args.extend(["--assignee", assignee])

        # Create issue
        output = self._run_gh_command(args)

        # Parse issue URL from output (gh outputs the URL)
        # Example: https://github.com/owner/repo/issues/123
        match = re.search(r'https://github\.com/[^/]+/[^/]+/issues/(\d+)', output)
        if not match:
            raise GitHubClientError(f"Could not parse issue number from gh output: {output}")

        issue_number = int(match.group(1))
        issue_url = match.group(0)

        # Get node_id via PyGithub (needed for GraphQL)
        try:
            issue = self.repo.get_issue(issue_number)
            node_id = issue.raw_data['node_id']
        except GithubException as e:
            raise GitHubClientError(f"Failed to get issue node_id: {e}")

        logger.info(f"Created issue #{issue_number}: {title}")

        return {
            "issue_number": issue_number,
            "issue_url": issue_url,
            "node_id": node_id,
        }

    def link_sub_issue(self, parent_node_id: str, child_node_id: str) -> bool:
        """
        Link a child issue to a parent using GraphQL mutation.

        Args:
            parent_node_id: GraphQL node ID of parent issue
            child_node_id: GraphQL node ID of child issue

        Returns:
            True if successful

        Raises:
            GitHubClientError: If linking fails after all retries
        """
        mutation = """
        mutation($parentId: ID!, $childId: ID!) {
          addSubIssue(input: {issueId: $parentId, subIssueId: $childId}) {
            issue {
              id
            }
          }
        }
        """

        for attempt in range(5):  # More retries for linking
            try:
                # Execute GraphQL mutation
                headers = {
                    "Authorization": f"Bearer {self.github._Github__requester.auth.token}",
                }

                # Use PyGithub's requester to execute GraphQL
                result = self.github._Github__requester.requestJsonAndCheck(
                    "POST",
                    "/graphql",
                    input={
                        "query": mutation,
                        "variables": {"parentId": parent_node_id, "childId": child_node_id},
                    },
                )

                if "errors" in result:
                    raise GitHubClientError(f"GraphQL errors: {result['errors']}")

                logger.debug(f"Linked sub-issue: {child_node_id} → {parent_node_id}")
                return True

            except Exception as e:
                logger.warning(
                    f"Sub-issue linking failed (attempt {attempt + 1}/5): {e}"
                )
                if attempt < 4:
                    sleep_time = self.retry_backoff_seconds * (2**attempt)
                    time.sleep(sleep_time)
                else:
                    raise GitHubClientError(f"Failed to link sub-issue: {e}")

        return False

    def get_milestones(self) -> List[Dict[str, Any]]:
        """
        Get all milestones for the repository.

        Returns:
            List of milestone dictionaries with 'title', 'number', 'description'
        """
        try:
            milestones = self.repo.get_milestones(state="all")
            return [
                {
                    "title": m.title,
                    "number": m.number,
                    "description": m.description or "",
                }
                for m in milestones
            ]
        except GithubException as e:
            raise GitHubClientError(f"Failed to get milestones: {e}")

    def create_milestone(self, title: str, description: Optional[str] = None) -> None:
        """
        Create a new milestone.

        Args:
            title: Milestone title
            description: Milestone description

        Raises:
            GitHubClientError: If milestone creation fails
        """
        try:
            self.repo.create_milestone(title, description=description)
            logger.info(f"Created milestone: {title}")
        except GithubException as e:
            raise GitHubClientError(f"Failed to create milestone '{title}': {e}")

    def get_labels(self) -> List[str]:
        """
        Get all labels for the repository.

        Returns:
            List of label names
        """
        try:
            labels = self.repo.get_labels()
            return [label.name for label in labels]
        except GithubException as e:
            raise GitHubClientError(f"Failed to get labels: {e}")

    def create_label(
        self, name: str, color: str = "cccccc", description: Optional[str] = None
    ) -> None:
        """
        Create a new label.

        Args:
            name: Label name
            color: Hex color code (without #)
            description: Label description

        Raises:
            GitHubClientError: If label creation fails
        """
        try:
            self.repo.create_label(name, color, description or "")
            logger.info(f"Created label: {name}")
        except GithubException as e:
            raise GitHubClientError(f"Failed to create label '{name}': {e}")

    def verify_issue_exists(self, issue_number: int) -> bool:
        """
        Check if an issue exists.

        Args:
            issue_number: GitHub issue number

        Returns:
            True if issue exists, False otherwise
        """
        try:
            self.repo.get_issue(issue_number)
            return True
        except GithubException:
            return False
