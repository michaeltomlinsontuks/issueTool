"""
Command-line interface using Click.

Provides commands for creating, validating, and managing issue hierarchy runs.
"""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .core import IssueCreator
from .state_manager import StateManager
from .validator import validate_input_file, ValidationError
from .utils import load_config, setup_logging


console = Console()


@click.group()
@click.version_option(version="1.0.0")
def main() -> None:
    """
    GitHub Issue Hierarchy Creation Tool.

    Create hierarchical GitHub issues from JSON input with parent-child relationships.
    """
    pass


@main.command()
@click.option(
    "--input",
    "-i",
    "input_file",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to input JSON file",
)
@click.option(
    "--config",
    "-c",
    "config_file",
    type=click.Path(path_type=Path),
    default="config.json",
    help="Path to configuration file (default: config.json)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview issues without creating them",
)
@click.option(
    "--force",
    is_flag=True,
    help="Ignore existing runs and duplicate checks",
)
@click.option(
    "--resume",
    "resume_run_id",
    type=str,
    help="Resume a specific run by ID",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    help="Logging level",
)
def create(
    input_file: Path,
    config_file: Path,
    dry_run: bool,
    force: bool,
    resume_run_id: str,
    log_level: str,
) -> None:
    """
    Create hierarchical GitHub issues from JSON input.

    Examples:
        gh-issue-hierarchy create --input issues.json
        gh-issue-hierarchy create --input issues.json --dry-run
        gh-issue-hierarchy create --input issues.json --force
    """
    # Load configuration
    config = load_config(config_file)

    # Override log level if specified
    if log_level:
        config["log_level"] = log_level

    # Setup logging
    log_dir = Path(config["log_directory"])
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "gh-issue-hierarchy.log"

    setup_logging(
        log_level=config["log_level"],
        log_file=log_file,
        enable_color=config["enable_color"],
    )

    # Get schema path
    schema_file = Path(__file__).parent.parent / "schemas" / "input-schema.json"

    # Get state DB path
    state_db_path = Path(config["state_db_path"])

    # Create and run
    creator = IssueCreator(
        input_file=input_file,
        schema_file=schema_file,
        state_db_path=state_db_path,
        config=config,
        dry_run=dry_run,
        force=force,
        resume_run_id=resume_run_id,
    )

    success = creator.run()
    sys.exit(0 if success else 1)


@main.command()
@click.option(
    "--input",
    "-i",
    "input_file",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to input JSON file",
)
def validate(input_file: Path) -> None:
    """
    Validate input JSON file against schema.

    Examples:
        gh-issue-hierarchy validate --input issues.json
    """
    schema_file = Path(__file__).parent.parent / "schemas" / "input-schema.json"

    try:
        data = validate_input_file(input_file, schema_file)
        console.print("[green]✓[/green] Validation passed")
        console.print(f"\nRepository: {data['repository']}")
        console.print(f"Issues: {len(data['issues'])}")

        # Count root issues
        root_count = sum(1 for issue in data['issues'] if issue.get('parent_id') is None)
        console.print(f"Root issues: {root_count}")

        sys.exit(0)

    except ValidationError as e:
        console.print(f"[red]✗[/red] Validation failed: {e}")
        sys.exit(1)


@main.command()
@click.option(
    "--run-id",
    "-r",
    type=str,
    help="Specific run ID to show status for",
)
@click.option(
    "--config",
    "-c",
    "config_file",
    type=click.Path(path_type=Path),
    default="config.json",
    help="Path to configuration file",
)
def status(run_id: str, config_file: Path) -> None:
    """
    Show status of a specific run or all runs.

    Examples:
        gh-issue-hierarchy status
        gh-issue-hierarchy status --run-id 20251024_143022
    """
    config = load_config(config_file)
    state_db_path = Path(config["state_db_path"])

    if not state_db_path.exists():
        console.print("[yellow]No runs found (database doesn't exist)[/yellow]")
        sys.exit(0)

    state_manager = StateManager(state_db_path)

    try:
        if run_id:
            # Show specific run
            run = state_manager.get_run(run_id)
            if not run:
                console.print(f"[red]✗[/red] Run '{run_id}' not found")
                sys.exit(1)

            _display_run_details(state_manager, run)

        else:
            # Show all runs
            runs = state_manager.list_all_runs()
            if not runs:
                console.print("[yellow]No runs found[/yellow]")
                sys.exit(0)

            _display_runs_table(runs)

    finally:
        state_manager.close()


@main.command(name="list-runs")
@click.option(
    "--config",
    "-c",
    "config_file",
    type=click.Path(path_type=Path),
    default="config.json",
    help="Path to configuration file",
)
def list_runs(config_file: Path) -> None:
    """
    List all runs in the database.

    Examples:
        gh-issue-hierarchy list-runs
    """
    config = load_config(config_file)
    state_db_path = Path(config["state_db_path"])

    if not state_db_path.exists():
        console.print("[yellow]No runs found (database doesn't exist)[/yellow]")
        sys.exit(0)

    state_manager = StateManager(state_db_path)

    try:
        runs = state_manager.list_all_runs()
        if not runs:
            console.print("[yellow]No runs found[/yellow]")
            sys.exit(0)

        _display_runs_table(runs)

    finally:
        state_manager.close()


@main.command()
@click.option(
    "--run-id",
    "-r",
    type=str,
    required=True,
    help="Run ID to clean up",
)
@click.option(
    "--delete-issues",
    is_flag=True,
    help="Also delete issues from GitHub (DANGEROUS!)",
)
@click.option(
    "--config",
    "-c",
    "config_file",
    type=click.Path(path_type=Path),
    default="config.json",
    help="Path to configuration file",
)
@click.confirmation_option(
    prompt="Are you sure you want to delete this run from the database?"
)
def cleanup(run_id: str, delete_issues: bool, config_file: Path) -> None:
    """
    Remove a run from the database (optionally delete GitHub issues).

    WARNING: This is destructive and cannot be undone!

    Examples:
        gh-issue-hierarchy cleanup --run-id 20251024_143022
        gh-issue-hierarchy cleanup --run-id 20251024_143022 --delete-issues
    """
    config = load_config(config_file)
    state_db_path = Path(config["state_db_path"])

    if not state_db_path.exists():
        console.print("[red]✗[/red] Database doesn't exist")
        sys.exit(1)

    state_manager = StateManager(state_db_path)

    try:
        run = state_manager.get_run(run_id)
        if not run:
            console.print(f"[red]✗[/red] Run '{run_id}' not found")
            sys.exit(1)

        if delete_issues:
            console.print("[yellow]⚠[/yellow] Deleting issues from GitHub is not yet implemented")
            console.print("Only removing from local database")

        state_manager.delete_run(run_id)
        console.print(f"[green]✓[/green] Run '{run_id}' deleted from database")

    finally:
        state_manager.close()


def _display_runs_table(runs: list) -> None:
    """Display runs in a table."""
    table = Table(title="Runs")
    table.add_column("Run ID", style="cyan")
    table.add_column("Repository", style="green")
    table.add_column("Status")
    table.add_column("Started")
    table.add_column("Issues")

    for run in runs:
        # Status with color
        status = run["status"]
        if status == "completed":
            status_str = f"[green]{status}[/green]"
        elif status == "failed":
            status_str = f"[red]{status}[/red]"
        else:
            status_str = f"[yellow]{status}[/yellow]"

        # Format date
        started = run["started_at"][:19] if run["started_at"] else "N/A"

        table.add_row(
            run["run_id"],
            run["repository"],
            status_str,
            started,
            "N/A",  # Would need to query created_issues table
        )

    console.print(table)


def _display_run_details(state_manager: StateManager, run: dict) -> None:
    """Display detailed information about a run."""
    console.print(f"\n[bold]Run ID:[/bold] {run['run_id']}")
    console.print(f"[bold]Repository:[/bold] {run['repository']}")
    console.print(f"[bold]Status:[/bold] {run['status']}")
    console.print(f"[bold]Input File:[/bold] {run['input_file']}")
    console.print(f"[bold]Started:[/bold] {run['started_at']}")

    if run["completed_at"]:
        console.print(f"[bold]Completed:[/bold] {run['completed_at']}")

    # Get statistics
    stats = state_manager.get_run_stats(run["run_id"])
    console.print(f"\n[bold]Statistics:[/bold]")
    console.print(f"  Total issues: {stats['total']}")
    console.print(f"  Linked: {stats['linked']}")
    console.print(f"  Unlinked: {stats['unlinked']}")

    # List created issues
    issues = state_manager.get_created_issues_for_run(run["run_id"])
    if issues:
        console.print(f"\n[bold]Created Issues:[/bold]")
        table = Table()
        table.add_column("Local ID", style="cyan")
        table.add_column("GitHub #", style="green")
        table.add_column("Title")
        table.add_column("Linked", style="yellow")

        for issue in issues[:10]:  # Show first 10
            table.add_row(
                issue["local_id"],
                str(issue["github_issue_number"]),
                issue["title"][:40],
                "✓" if issue["linked_at"] else "-",
            )

        console.print(table)

        if len(issues) > 10:
            console.print(f"\n... and {len(issues) - 10} more issues")


if __name__ == "__main__":
    main()
