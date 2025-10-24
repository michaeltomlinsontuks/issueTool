"""
JSON input validation.

Validates input files against JSON schema and performs structural
validation (cycles, orphaned references, duplicates).
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Set

import jsonschema

from .graph import IssueGraph


class ValidationError(Exception):
    """Custom exception for validation errors."""

    pass


def load_schema(schema_path: Path) -> Dict[str, Any]:
    """
    Load JSON schema from file.

    Args:
        schema_path: Path to the JSON schema file

    Returns:
        Parsed JSON schema

    Raises:
        ValidationError: If schema file cannot be loaded
    """
    try:
        with open(schema_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise ValidationError(f"Schema file not found: {schema_path}")
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON in schema file: {e}")


def load_input_file(input_path: Path) -> Dict[str, Any]:
    """
    Load input JSON file.

    Args:
        input_path: Path to the input JSON file

    Returns:
        Parsed input data

    Raises:
        ValidationError: If input file cannot be loaded
    """
    try:
        with open(input_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise ValidationError(f"Input file not found: {input_path}")
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON in input file: {e}")


def validate_against_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> None:
    """
    Validate data against JSON schema.

    Args:
        data: Input data to validate
        schema: JSON schema

    Raises:
        ValidationError: If validation fails with detailed error message
    """
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        # Format error message with path information
        path = ' → '.join(str(p) for p in e.absolute_path) if e.absolute_path else 'root'
        raise ValidationError(
            f"Schema validation failed at '{path}': {e.message}"
        )
    except jsonschema.SchemaError as e:
        raise ValidationError(f"Invalid schema: {e.message}")


def validate_unique_ids(issues: List[Dict[str, Any]]) -> None:
    """
    Validate that all issue IDs are unique.

    Args:
        issues: List of issue dictionaries

    Raises:
        ValidationError: If duplicate IDs are found
    """
    seen_ids: Set[str] = set()
    duplicates: List[str] = []

    for issue in issues:
        issue_id = issue['id']
        if issue_id in seen_ids:
            duplicates.append(issue_id)
        seen_ids.add(issue_id)

    if duplicates:
        raise ValidationError(
            f"Duplicate issue IDs found: {', '.join(duplicates)}"
        )


def validate_parent_references(issues: List[Dict[str, Any]]) -> None:
    """
    Validate that all parent_id references point to existing issues.

    Args:
        issues: List of issue dictionaries

    Raises:
        ValidationError: If orphaned parent references are found
    """
    issue_ids = {issue['id'] for issue in issues}
    orphaned: List[str] = []

    for issue in issues:
        parent_id = issue.get('parent_id')
        if parent_id is not None and parent_id not in issue_ids:
            orphaned.append(f"{issue['id']} → {parent_id}")

    if orphaned:
        raise ValidationError(
            f"Orphaned parent references found:\n  " + "\n  ".join(orphaned)
        )


def validate_no_circular_dependencies(issues: List[Dict[str, Any]]) -> None:
    """
    Validate that there are no circular dependencies in the issue graph.

    Args:
        issues: List of issue dictionaries

    Raises:
        ValidationError: If circular dependencies are detected
    """
    try:
        graph = IssueGraph(issues)
        graph.topological_sort()
    except ValueError as e:
        raise ValidationError(str(e))


def validate_input_file(input_path: Path, schema_path: Path) -> Dict[str, Any]:
    """
    Validate an input file comprehensively.

    Performs:
    1. JSON schema validation
    2. Unique ID validation
    3. Parent reference validation
    4. Circular dependency detection

    Args:
        input_path: Path to the input JSON file
        schema_path: Path to the JSON schema file

    Returns:
        Validated input data

    Raises:
        ValidationError: If any validation fails
    """
    # Load files
    schema = load_schema(schema_path)
    data = load_input_file(input_path)

    # Schema validation
    validate_against_schema(data, schema)

    # Structural validation
    issues = data.get('issues', [])

    validate_unique_ids(issues)
    validate_parent_references(issues)
    validate_no_circular_dependencies(issues)

    return data
