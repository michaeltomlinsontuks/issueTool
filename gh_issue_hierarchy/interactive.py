"""
Interactive user prompts.

Handles missing milestones and labels with Rich-based menus and prompts.
"""

from typing import Optional, List, Dict, Any

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.panel import Panel

from .github_client import GitHubClient


console = Console()


def prompt_for_milestone(
    github_client: GitHubClient, milestone_name: str
) -> Optional[str]:
    """
    Handle missing milestone with interactive prompt.

    Offers options to:
    1. Create new milestone
    2. Choose from existing milestones
    3. Skip milestone

    Args:
        github_client: GitHub client instance
        milestone_name: Requested milestone name that doesn't exist

    Returns:
        Selected milestone name, or None to skip
    """
    console.print(
        f"\n[yellow]Milestone '{milestone_name}' does not exist.[/yellow]"
    )

    # Show options
    console.print("\nOptions:")
    console.print("  1. Create new milestone")
    console.print("  2. Choose from existing milestones")
    console.print("  3. Skip milestone (no milestone will be assigned)")

    choice = Prompt.ask(
        "Select an option",
        choices=["1", "2", "3"],
        default="1",
    )

    if choice == "1":
        # Create new milestone
        console.print(f"\n[bold]Creating milestone: {milestone_name}[/bold]")
        description = Prompt.ask(
            "Enter milestone description (optional)",
            default="",
        )

        try:
            github_client.create_milestone(
                milestone_name,
                description if description else None,
            )
            console.print(f"[green]✓[/green] Milestone '{milestone_name}' created")
            return milestone_name
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to create milestone: {e}")
            return None

    elif choice == "2":
        # Choose from existing milestones
        try:
            milestones = github_client.get_milestones()

            if not milestones:
                console.print("[yellow]No existing milestones found.[/yellow]")
                return None

            # Display milestones in a table
            table = Table(title="Available Milestones")
            table.add_column("#", style="cyan")
            table.add_column("Title", style="green")
            table.add_column("Description")

            for idx, milestone in enumerate(milestones, 1):
                table.add_row(
                    str(idx),
                    milestone["title"],
                    milestone["description"][:50] if milestone["description"] else "",
                )

            console.print(table)

            # Get user selection
            selection = Prompt.ask(
                "Select milestone number (or 0 to skip)",
                default="0",
            )

            try:
                selection_idx = int(selection)
                if selection_idx == 0:
                    return None
                if 1 <= selection_idx <= len(milestones):
                    selected = milestones[selection_idx - 1]["title"]
                    console.print(f"[green]✓[/green] Selected: {selected}")
                    return selected
                else:
                    console.print("[red]Invalid selection[/red]")
                    return None
            except ValueError:
                console.print("[red]Invalid input[/red]")
                return None

        except Exception as e:
            console.print(f"[red]✗[/red] Failed to fetch milestones: {e}")
            return None

    else:  # choice == "3"
        console.print("[yellow]Skipping milestone[/yellow]")
        return None


def prompt_for_labels(
    github_client: GitHubClient, missing_labels: List[str]
) -> List[str]:
    """
    Handle missing labels with interactive prompt.

    Offers options to:
    1. Create all missing labels
    2. Choose which labels to create
    3. Skip missing labels

    Args:
        github_client: GitHub client instance
        missing_labels: List of label names that don't exist

    Returns:
        List of label names to use (may be empty)
    """
    console.print(
        f"\n[yellow]The following labels do not exist:[/yellow]"
    )
    for label in missing_labels:
        console.print(f"  - {label}")

    # Show options
    console.print("\nOptions:")
    console.print("  1. Create all missing labels")
    console.print("  2. Choose which labels to create")
    console.print("  3. Skip missing labels")

    choice = Prompt.ask(
        "Select an option",
        choices=["1", "2", "3"],
        default="1",
    )

    created_labels: List[str] = []

    if choice == "1":
        # Create all labels
        console.print("\n[bold]Creating labels...[/bold]")
        for label in missing_labels:
            try:
                # Use default gray color
                github_client.create_label(label)
                console.print(f"[green]✓[/green] Created label: {label}")
                created_labels.append(label)
            except Exception as e:
                console.print(f"[red]✗[/red] Failed to create label '{label}': {e}")

    elif choice == "2":
        # Choose which labels to create
        console.print("\n[bold]Select labels to create:[/bold]")
        for label in missing_labels:
            if Confirm.ask(f"Create label '{label}'?", default=True):
                try:
                    github_client.create_label(label)
                    console.print(f"[green]✓[/green] Created label: {label}")
                    created_labels.append(label)
                except Exception as e:
                    console.print(f"[red]✗[/red] Failed to create label '{label}': {e}")

    else:  # choice == "3"
        console.print("[yellow]Skipping missing labels[/yellow]")

    return created_labels


def display_summary_panel(stats: Dict[str, Any]) -> None:
    """
    Display a summary panel with run statistics.

    Args:
        stats: Dictionary with statistics
    """
    content = []

    if "created" in stats:
        content.append(f"[green]✓[/green] Created: {stats['created']}")
    if "skipped" in stats:
        content.append(f"[yellow]⚠[/yellow] Skipped: {stats['skipped']}")
    if "failed" in stats:
        content.append(f"[red]✗[/red] Failed: {stats['failed']}")
    if "linked" in stats:
        content.append(f"[blue]🔗[/blue] Linked: {stats['linked']}")
    if "duration" in stats:
        content.append(f"[cyan]⏱[/cyan] Duration: {stats['duration']}")

    panel = Panel(
        "\n".join(content),
        title="Summary",
        border_style="bright_blue",
    )

    console.print("\n")
    console.print(panel)
