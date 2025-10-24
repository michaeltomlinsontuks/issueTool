"""
Utility functions and helpers.
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional


def compute_file_hash(file_path: Path) -> str:
    """
    Compute SHA256 hash of a file.

    Args:
        file_path: Path to file

    Returns:
        Hexadecimal hash string
    """
    hash_obj = hashlib.sha256()

    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            hash_obj.update(chunk)

    return hash_obj.hexdigest()


def generate_run_id() -> str:
    """
    Generate a unique run ID based on timestamp.

    Returns:
        Run ID in format YYYYMMDD_HHMMSS
    """
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "3m 42s")
    """
    if seconds < 60:
        return f"{seconds:.0f}s"

    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)

    if minutes < 60:
        return f"{minutes}m {remaining_seconds}s"

    hours = int(minutes // 60)
    remaining_minutes = int(minutes % 60)

    return f"{hours}h {remaining_minutes}m {remaining_seconds}s"


def merge_labels(defaults: List[str], issue_labels: List[str]) -> List[str]:
    """
    Merge default and issue-specific labels (additive).

    Args:
        defaults: Default labels
        issue_labels: Issue-specific labels

    Returns:
        Combined list of unique labels
    """
    # Use set to remove duplicates, then convert back to list
    combined = set(defaults) | set(issue_labels)
    return sorted(list(combined))


def apply_defaults(
    issue: Dict[str, Any], defaults: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Apply default values to an issue.

    Issue-level fields override defaults, except labels which are additive.

    Args:
        issue: Issue dictionary
        defaults: Default values dictionary

    Returns:
        Issue with defaults applied
    """
    if not defaults:
        return issue

    result = issue.copy()

    # Apply simple defaults (if not present in issue)
    if 'milestone' not in result and 'milestone' in defaults:
        result['milestone'] = defaults['milestone']

    if 'assignees' not in result and 'assignees' in defaults:
        result['assignees'] = defaults['assignees']

    if 'due_date' not in result and 'due_date' in defaults:
        result['due_date'] = defaults['due_date']

    # Labels are additive (merge)
    default_labels = defaults.get('labels', [])
    issue_labels = result.get('labels', [])
    result['labels'] = merge_labels(default_labels, issue_labels)

    return result


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[Path] = None,
    enable_color: bool = True,
) -> None:
    """
    Set up logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Path to log file (optional)
        enable_color: Enable colored console output
    """
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper()))

    # Format
    if enable_color:
        # Rich handles colored output
        console_format = "%(message)s"
    else:
        console_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    console_formatter = logging.Formatter(console_format)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)  # Always DEBUG for file
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)


def load_config(config_path: Path) -> Dict[str, Any]:
    """
    Load configuration from JSON file.

    Args:
        config_path: Path to config file

    Returns:
        Configuration dictionary with defaults
    """
    defaults = {
        "state_db_path": ".state/state.db",
        "log_directory": "logs/",
        "log_level": "INFO",
        "retry_attempts": 3,
        "retry_backoff_seconds": 5,
        "github_api_timeout_seconds": 30,
        "enable_color": True,
    }

    if not config_path.exists():
        return defaults

    try:
        with open(config_path, 'r') as f:
            user_config = json.load(f)
            # Merge with defaults
            defaults.update(user_config)
            return defaults
    except Exception:
        # Return defaults if config loading fails
        return defaults


def validate_repository_format(repository: str) -> bool:
    """
    Validate repository format (owner/repo).

    Args:
        repository: Repository string

    Returns:
        True if valid format
    """
    parts = repository.split('/')
    return len(parts) == 2 and all(part.strip() for part in parts)
