"""
Main orchestration logic for issue creation.

Coordinates all modules to create hierarchical issues.
"""

import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .state_manager import StateManager
from .github_client import GitHubClient, GitHubClientError
from .graph import IssueGraph
from .validator import validate_input_file, ValidationError
from .fingerprint import generate_fingerprint
from .interactive import prompt_for_milestone, prompt_for_labels, display_summary_panel
from .utils import (
    compute_file_hash,
    generate_run_id,
    format_duration,
    apply_defaults,
)


logger = logging.getLogger(__name__)
console = Console()


class IssueCreator:
    """Main orchestrator for creating hierarchical issues."""

    def __init__(
        self,
        input_file: Path,
        schema_file: Path,
        state_db_path: Path,
        config: Dict[str, Any],
        dry_run: bool = False,
        force: bool = False,
        resume_run_id: Optional[str] = None,
    ):
        """
        Initialize issue creator.

        Args:
            input_file: Path to input JSON file
            schema_file: Path to JSON schema file
            state_db_path: Path to SQLite database
            config: Configuration dictionary
            dry_run: If True, don't create issues (preview only)
            force: If True, ignore existing runs and duplicates
            resume_run_id: Run ID to resume (optional)
        """
        self.input_file = input_file
        self.schema_file = schema_file
        self.state_db_path = state_db_path
        self.config = config
        self.dry_run = dry_run
        self.force = force
        self.resume_run_id = resume_run_id

        # Statistics
        self.stats = {
            "created": 0,
            "skipped": 0,
            "failed": 0,
            "linked": 0,
        }

        # Components (initialized later)
        self.data: Optional[Dict[str, Any]] = None
        self.state_manager: Optional[StateManager] = None
        self.github_client: Optional[GitHubClient] = None
        self.graph: Optional[IssueGraph] = None
        self.run_id: Optional[str] = None

    def run(self) -> bool:
        """
        Main execution flow.

        Returns:
            True if successful, False otherwise
        """
        start_time = time.time()

        try:
            # Step 1: Validate input
            console.print("[bold blue]Step 1:[/bold blue] Validating input file...")
            self._validate_input()
            console.print("[green]✓[/green] Input validation passed\n")

            # Step 2: Initialize state
            console.print("[bold blue]Step 2:[/bold blue] Initializing state...")
            self._initialize_state()
            console.print(f"[green]✓[/green] Run ID: {self.run_id}\n")

            # Step 3: Initialize GitHub client
            console.print("[bold blue]Step 3:[/bold blue] Connecting to GitHub...")
            self._initialize_github_client()
            console.print("[green]✓[/green] Connected to GitHub\n")

            # Step 4: Validate resources (milestone, labels)
            if not self.dry_run:
                console.print("[bold blue]Step 4:[/bold blue] Validating resources...")
                self._validate_resources()
                console.print("[green]✓[/green] Resources validated\n")

            # Step 5: Build dependency graph
            console.print("[bold blue]Step 5:[/bold blue] Building dependency graph...")
            self._build_graph()
            console.print("[green]✓[/green] Graph built\n")

            # Step 6: Create issues
            console.print("[bold blue]Step 6:[/bold blue] Creating issues...")
            self._create_issues()
            console.print("\n[green]✓[/green] Issues created\n")

            # Step 7: Mark run complete
            if not self.dry_run:
                self.state_manager.mark_run_complete(self.run_id, "completed")

            # Calculate duration
            duration = time.time() - start_time
            self.stats["duration"] = format_duration(duration)

            # Display summary
            display_summary_panel(self.stats)

            return True

        except ValidationError as e:
            console.print(f"\n[red]✗ Validation Error:[/red] {e}")
            return False

        except GitHubClientError as e:
            console.print(f"\n[red]✗ GitHub Error:[/red] {e}")
            if self.state_manager and self.run_id:
                self.state_manager.mark_run_complete(self.run_id, "failed")
            return False

        except Exception as e:
            console.print(f"\n[red]✗ Unexpected Error:[/red] {e}")
            logger.exception("Unexpected error during execution")
            if self.state_manager and self.run_id:
                self.state_manager.mark_run_complete(self.run_id, "failed")
            return False

        finally:
            if self.state_manager:
                self.state_manager.close()

    def _validate_input(self) -> None:
        """Validate input file against schema."""
        self.data = validate_input_file(self.input_file, self.schema_file)

    def _initialize_state(self) -> None:
        """Initialize state manager and determine run ID."""
        self.state_manager = StateManager(self.state_db_path)

        # Compute input file hash
        input_hash = compute_file_hash(self.input_file)

        # Check for existing run
        if self.resume_run_id:
            # Resume specific run
            existing_run = self.state_manager.get_run(self.resume_run_id)
            if not existing_run:
                raise ValidationError(f"Run ID '{self.resume_run_id}' not found")
            if existing_run["status"] == "completed":
                raise ValidationError(f"Run '{self.resume_run_id}' is already completed")
            self.run_id = self.resume_run_id
            console.print(f"[yellow]Resuming run: {self.run_id}[/yellow]")

        else:
            # Check for existing run with same input hash
            existing_run = self.state_manager.get_run_by_hash(input_hash)

            if existing_run:
                if existing_run["status"] == "completed" and not self.force:
                    raise ValidationError(
                        f"Input file already processed in run '{existing_run['run_id']}'. "
                        "Use --force to recreate."
                    )
                elif existing_run["status"] == "in_progress":
                    # Resume incomplete run
                    self.run_id = existing_run["run_id"]
                    console.print(f"[yellow]Resuming incomplete run: {self.run_id}[/yellow]")
                else:
                    # Create new run
                    self.run_id = generate_run_id()
                    if not self.dry_run:
                        self.state_manager.create_run(
                            self.run_id,
                            str(self.input_file),
                            input_hash,
                            self.data["repository"],
                        )
            else:
                # Create new run
                self.run_id = generate_run_id()
                if not self.dry_run:
                    self.state_manager.create_run(
                        self.run_id,
                        str(self.input_file),
                        input_hash,
                        self.data["repository"],
                    )

    def _initialize_github_client(self) -> None:
        """Initialize GitHub client."""
        self.github_client = GitHubClient(
            self.data["repository"],
            retry_attempts=self.config.get("retry_attempts", 3),
            retry_backoff_seconds=self.config.get("retry_backoff_seconds", 5),
            timeout_seconds=self.config.get("github_api_timeout_seconds", 30),
        )

    def _validate_resources(self) -> None:
        """Validate that milestones and labels exist, prompt if missing."""
        defaults = self.data.get("defaults", {})

        # Check milestone
        milestone = defaults.get("milestone")
        if milestone:
            existing_milestones = [m["title"] for m in self.github_client.get_milestones()]
            if milestone not in existing_milestones:
                result = prompt_for_milestone(self.github_client, milestone)
                if result:
                    defaults["milestone"] = result
                else:
                    defaults.pop("milestone", None)

        # Check labels
        all_labels = set(defaults.get("labels", []))
        for issue in self.data["issues"]:
            all_labels.update(issue.get("labels", []))

        if all_labels:
            existing_labels = self.github_client.get_labels()
            missing_labels = [label for label in all_labels if label not in existing_labels]

            if missing_labels:
                created_labels = prompt_for_labels(self.github_client, missing_labels)
                # Labels are now created, no need to modify data

    def _build_graph(self) -> None:
        """Build dependency graph and validate."""
        # Apply defaults to all issues
        defaults = self.data.get("defaults", {})
        issues = [apply_defaults(issue, defaults) for issue in self.data["issues"]]

        # Build graph
        self.graph = IssueGraph(issues)

        # Validate references
        self.graph.validate_references()

    def _create_issues(self) -> None:
        """Create issues in topological order."""
        # Get sorted issue IDs
        sorted_ids = self.graph.topological_sort()

        # Create progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Creating issues...", total=len(sorted_ids))

            for issue_id in sorted_ids:
                issue = self.graph.issues[issue_id]
                self._create_single_issue(issue, progress, task)
                progress.advance(task)

    def _create_single_issue(
        self, issue: Dict[str, Any], progress: Progress, task: Any
    ) -> None:
        """
        Create a single issue and link to parent if needed.

        Args:
            issue: Issue dictionary
            progress: Rich progress instance
            task: Progress task
        """
        issue_id = issue["id"]
        title = issue["title"]

        # Update progress description
        depth = self.graph.get_depth(issue_id)
        indent = "  " * depth
        progress.update(task, description=f"{indent}Creating: {title[:50]}")

        # Check if already created
        if not self.dry_run:
            existing = self.state_manager.get_created_issue(self.run_id, issue_id)
            if existing:
                logger.info(f"Skipping already created issue: {issue_id}")
                self.stats["skipped"] += 1
                return

        # Check fingerprint for duplicates (unless force)
        if not self.force and not self.dry_run:
            fingerprint = generate_fingerprint(
                self.data["repository"], title, issue.get("body")
            )
            duplicate = self.state_manager.find_by_fingerprint(fingerprint)
            if duplicate:
                logger.warning(
                    f"Duplicate detected for '{title}': "
                    f"#{duplicate['github_issue_number']} (use --force to recreate)"
                )
                self.stats["skipped"] += 1
                return

        # Dry run - just log
        if self.dry_run:
            logger.info(f"[DRY RUN] Would create: {title}")
            self.stats["created"] += 1
            return

        # Create issue
        try:
            result = self.github_client.create_issue(
                title=title,
                body=issue.get("body"),
                milestone=issue.get("milestone"),
                labels=issue.get("labels"),
                assignees=issue.get("assignees"),
            )

            # Record in database
            fingerprint = generate_fingerprint(
                self.data["repository"], title, issue.get("body")
            )

            self.state_manager.record_created_issue(
                run_id=self.run_id,
                local_id=issue_id,
                github_issue_number=result["issue_number"],
                github_issue_url=result["issue_url"],
                github_node_id=result["node_id"],
                title=title,
                fingerprint=fingerprint,
                parent_id=issue.get("parent_id"),
            )

            self.stats["created"] += 1

            # Link to parent if needed
            parent_id = issue.get("parent_id")
            if parent_id:
                parent = self.state_manager.get_created_issue(self.run_id, parent_id)
                if parent:
                    try:
                        self.github_client.link_sub_issue(
                            parent["github_node_id"], result["node_id"]
                        )
                        self.state_manager.record_link(
                            self.run_id, issue_id, parent["github_issue_number"]
                        )
                        self.stats["linked"] += 1
                    except Exception as e:
                        logger.error(f"Failed to link issue '{issue_id}' to parent: {e}")
                else:
                    logger.error(f"Parent '{parent_id}' not found for linking")

        except Exception as e:
            logger.error(f"Failed to create issue '{issue_id}': {e}")
            self.stats["failed"] += 1
