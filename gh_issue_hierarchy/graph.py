"""
Dependency graph operations for issue hierarchies.

Handles parent-child relationships, topological sorting,
and tree traversal operations.
"""

from typing import Dict, List, Set, Optional, Any


class IssueGraph:
    """
    Manages the dependency graph of issues.

    Builds parent→children relationships and provides operations
    like topological sorting and depth calculations.
    """

    def __init__(self, issues: List[Dict[str, Any]]):
        """
        Initialize the graph from a list of issues.

        Args:
            issues: List of issue dictionaries with 'id' and optional 'parent_id'
        """
        self.issues = {issue['id']: issue for issue in issues}
        self.children_map: Dict[Optional[str], List[str]] = {}
        self._build_adjacency_list()

    def _build_adjacency_list(self) -> None:
        """Build parent→children mapping."""
        self.children_map = {}

        for issue_id, issue in self.issues.items():
            parent_id = issue.get('parent_id')

            # Initialize parent's children list if not exists
            if parent_id not in self.children_map:
                self.children_map[parent_id] = []

            # Add this issue as a child of its parent
            self.children_map[parent_id].append(issue_id)

    def get_children(self, issue_id: Optional[str]) -> List[str]:
        """
        Get direct children of an issue.

        Args:
            issue_id: ID of the issue (None for root issues)

        Returns:
            List of child issue IDs
        """
        return self.children_map.get(issue_id, [])

    def get_root_issues(self) -> List[str]:
        """
        Get all root issues (issues with no parent).

        Returns:
            List of root issue IDs
        """
        return self.children_map.get(None, [])

    def topological_sort(self) -> List[str]:
        """
        Sort issues topologically (parents before children).

        Uses depth-first search to ensure parent issues are always
        created before their children.

        Returns:
            List of issue IDs in topological order

        Raises:
            ValueError: If circular dependencies are detected
        """
        sorted_issues: List[str] = []
        visited: Set[str] = set()
        in_progress: Set[str] = set()

        def dfs(issue_id: Optional[str]) -> None:
            """Depth-first traversal."""
            if issue_id is None:
                # Process root issues
                for root_id in self.get_root_issues():
                    if root_id not in visited:
                        dfs(root_id)
                return

            if issue_id in in_progress:
                raise ValueError(f"Circular dependency detected involving issue '{issue_id}'")

            if issue_id in visited:
                return

            in_progress.add(issue_id)

            # Visit children first (depth-first)
            for child_id in self.get_children(issue_id):
                dfs(child_id)

            in_progress.remove(issue_id)
            visited.add(issue_id)
            sorted_issues.append(issue_id)

        # Start DFS from root (None represents root level)
        dfs(None)

        # Reverse to get parent-before-children order
        return list(reversed(sorted_issues))

    def get_depth(self, issue_id: str) -> int:
        """
        Calculate the depth of an issue in the tree.

        Root issues have depth 0, their children have depth 1, etc.

        Args:
            issue_id: ID of the issue

        Returns:
            Depth of the issue (0 for root issues)
        """
        depth = 0
        current_id = issue_id

        while True:
            issue = self.issues.get(current_id)
            if not issue:
                break

            parent_id = issue.get('parent_id')
            if parent_id is None:
                break

            depth += 1
            current_id = parent_id

        return depth

    def get_all_descendants(self, issue_id: str) -> List[str]:
        """
        Get all descendants of an issue (children, grandchildren, etc.).

        Args:
            issue_id: ID of the issue

        Returns:
            List of all descendant issue IDs
        """
        descendants: List[str] = []

        def collect_descendants(current_id: str) -> None:
            for child_id in self.get_children(current_id):
                descendants.append(child_id)
                collect_descendants(child_id)

        collect_descendants(issue_id)
        return descendants

    def validate_references(self) -> None:
        """
        Validate that all parent_id references point to existing issues.

        Raises:
            ValueError: If any parent_id references a non-existent issue
        """
        for issue_id, issue in self.issues.items():
            parent_id = issue.get('parent_id')
            if parent_id is not None and parent_id not in self.issues:
                raise ValueError(
                    f"Issue '{issue_id}' references non-existent parent '{parent_id}'"
                )
