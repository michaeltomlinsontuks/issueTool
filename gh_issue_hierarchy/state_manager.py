"""
SQLite state management for issue creation tracking.

Manages runs and created issues in a local database to enable
idempotent operations and resume functionality.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List


class StateManager:
    """
    Manages persistent state in SQLite database.

    Tracks runs and created issues to support resume functionality
    and duplicate detection.
    """

    def __init__(self, db_path: Path):
        """
        Initialize state manager with database path.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None
        self._init_database()

    def _init_database(self) -> None:
        """Create database schema if it doesn't exist."""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

        cursor = self.conn.cursor()

        # Create runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                input_file TEXT NOT NULL,
                input_file_hash TEXT NOT NULL,
                repository TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL CHECK(status IN ('in_progress', 'completed', 'failed'))
            )
        """)

        # Create created_issues table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS created_issues (
                run_id TEXT NOT NULL,
                local_id TEXT NOT NULL,
                github_issue_number INTEGER NOT NULL,
                github_issue_url TEXT NOT NULL,
                github_node_id TEXT NOT NULL,
                title TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                parent_id TEXT,
                parent_issue_number INTEGER,
                linked_at TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (run_id, local_id),
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fingerprint
            ON created_issues(fingerprint)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_local_id
            ON created_issues(local_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_run_status
            ON runs(status)
        """)

        self.conn.commit()

    def create_run(
        self, run_id: str, input_file: str, input_file_hash: str, repository: str
    ) -> None:
        """
        Create a new run record.

        Args:
            run_id: Unique run identifier
            input_file: Path to input file
            input_file_hash: SHA256 hash of input file
            repository: GitHub repository (owner/repo)
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO runs (run_id, input_file, input_file_hash, repository, started_at, status)
            VALUES (?, ?, ?, ?, ?, 'in_progress')
            """,
            (run_id, input_file, input_file_hash, repository, datetime.utcnow().isoformat()),
        )
        self.conn.commit()

    def get_run_by_hash(self, input_file_hash: str) -> Optional[Dict[str, Any]]:
        """
        Find existing run by input file hash.

        Args:
            input_file_hash: SHA256 hash of input file

        Returns:
            Run record as dictionary, or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM runs WHERE input_file_hash = ? ORDER BY started_at DESC LIMIT 1",
            (input_file_hash,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get run by ID.

        Args:
            run_id: Run identifier

        Returns:
            Run record as dictionary, or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_created_issue(self, run_id: str, local_id: str) -> Optional[Dict[str, Any]]:
        """
        Lookup issue by local_id in a specific run.

        Args:
            run_id: Run identifier
            local_id: Local issue identifier

        Returns:
            Issue record as dictionary, or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM created_issues WHERE run_id = ? AND local_id = ?",
            (run_id, local_id),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def find_by_fingerprint(self, fingerprint: str) -> Optional[Dict[str, Any]]:
        """
        Find issue by fingerprint across all runs.

        Args:
            fingerprint: Issue fingerprint hash

        Returns:
            Issue record as dictionary, or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM created_issues WHERE fingerprint = ? LIMIT 1",
            (fingerprint,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def record_created_issue(
        self,
        run_id: str,
        local_id: str,
        github_issue_number: int,
        github_issue_url: str,
        github_node_id: str,
        title: str,
        fingerprint: str,
        parent_id: Optional[str] = None,
    ) -> None:
        """
        Save newly created issue to database.

        Args:
            run_id: Run identifier
            local_id: Local issue identifier
            github_issue_number: GitHub issue number
            github_issue_url: Full URL to GitHub issue
            github_node_id: GraphQL node ID
            title: Issue title
            fingerprint: Issue fingerprint
            parent_id: Parent issue local_id (if any)
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO created_issues
            (run_id, local_id, github_issue_number, github_issue_url, github_node_id,
             title, fingerprint, parent_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                local_id,
                github_issue_number,
                github_issue_url,
                github_node_id,
                title,
                fingerprint,
                parent_id,
                datetime.utcnow().isoformat(),
            ),
        )
        self.conn.commit()

    def record_link(self, run_id: str, local_id: str, parent_issue_number: int) -> None:
        """
        Update issue record when sub-issue link is established.

        Args:
            run_id: Run identifier
            local_id: Local issue identifier
            parent_issue_number: GitHub issue number of parent
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE created_issues
            SET parent_issue_number = ?, linked_at = ?
            WHERE run_id = ? AND local_id = ?
            """,
            (parent_issue_number, datetime.utcnow().isoformat(), run_id, local_id),
        )
        self.conn.commit()

    def mark_run_complete(self, run_id: str, status: str = "completed") -> None:
        """
        Mark run as complete or failed.

        Args:
            run_id: Run identifier
            status: Final status ('completed' or 'failed')
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE runs
            SET status = ?, completed_at = ?
            WHERE run_id = ?
            """,
            (status, datetime.utcnow().isoformat(), run_id),
        )
        self.conn.commit()

    def get_run_stats(self, run_id: str) -> Dict[str, int]:
        """
        Calculate statistics for a run.

        Args:
            run_id: Run identifier

        Returns:
            Dictionary with counts: total, linked, unlinked
        """
        cursor = self.conn.cursor()

        # Total issues created
        cursor.execute(
            "SELECT COUNT(*) as count FROM created_issues WHERE run_id = ?", (run_id,)
        )
        total = cursor.fetchone()["count"]

        # Linked issues
        cursor.execute(
            "SELECT COUNT(*) as count FROM created_issues WHERE run_id = ? AND linked_at IS NOT NULL",
            (run_id,),
        )
        linked = cursor.fetchone()["count"]

        return {"total": total, "linked": linked, "unlinked": total - linked}

    def list_all_runs(self) -> List[Dict[str, Any]]:
        """
        List all runs in the database.

        Returns:
            List of run records
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM runs ORDER BY started_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    def get_created_issues_for_run(self, run_id: str) -> List[Dict[str, Any]]:
        """
        Get all created issues for a specific run.

        Args:
            run_id: Run identifier

        Returns:
            List of issue records
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM created_issues WHERE run_id = ? ORDER BY created_at",
            (run_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def delete_run(self, run_id: str) -> None:
        """
        Delete a run and all its created issues.

        Args:
            run_id: Run identifier
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM created_issues WHERE run_id = ?", (run_id,))
        cursor.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
        self.conn.commit()

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self) -> "StateManager":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()
