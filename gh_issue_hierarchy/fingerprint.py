"""
Fingerprint generation for issue deduplication.

Creates SHA256 hashes from repository + title + body preview
to detect duplicate issues across runs.
"""

import hashlib
from typing import Optional


def generate_fingerprint(repository: str, title: str, body: Optional[str] = None) -> str:
    """
    Generate a fingerprint for an issue to detect duplicates.

    The fingerprint is a SHA256 hash of:
    - Repository name
    - Issue title
    - First 100 characters of the body (if present)

    Args:
        repository: GitHub repository in format 'owner/repo'
        title: Issue title
        body: Issue body/description (optional)

    Returns:
        Hexadecimal SHA256 hash string (64 characters)

    Example:
        >>> fingerprint = generate_fingerprint("owner/repo", "Bug fix", "Description here")
        >>> len(fingerprint)
        64
    """
    # Normalize inputs
    repo_normalized = repository.strip().lower()
    title_normalized = title.strip()

    # Use first 100 chars of body for fingerprint (or empty string if None)
    body_preview = ""
    if body:
        body_preview = body.strip()[:100]

    # Create composite string
    composite = f"{repo_normalized}|{title_normalized}|{body_preview}"

    # Generate SHA256 hash
    hash_object = hashlib.sha256(composite.encode('utf-8'))

    return hash_object.hexdigest()
