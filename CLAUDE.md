# GitHub Issue Hierarchy Creation Tool - Specification

**Project:** `gh-issue-hierarchy`  
**Version:** 1.0.0  
**Purpose:** Autonomous CLI tool for creating hierarchical GitHub issues from JSON input

---

## Overview

Creates hierarchical GitHub issues with parent-child relationships from a structured JSON input file. Designed for autonomous operation, idempotency, and reliability when creating 100+ issues.

### Core Requirements
- Create issues in parent-child hierarchy using GitHub's sub-issue feature
- Safe to re-run (idempotent) - no duplicate issues on failure recovery
- Resume incomplete runs from exact failure point
- Interactive prompts when milestones/labels don't exist
- Detailed progress tracking and logging
- JSON validation before any GitHub operations
- Future MCP tool integration support

---

## Technical Stack

**Language:** Python 3.10+  
**Package Manager:** Poetry

**Dependencies:**
- `click` - CLI framework with argument parsing
- `pygithub` - GitHub API wrapper for GraphQL operations
- `jsonschema` - Input validation
- `rich` - Terminal UI (progress bars, tables, colors)
- `sqlite3` (built-in) - State persistence

**External Tools Required:**
- GitHub CLI (`gh`) - Issue creation and authentication
- Git - Repository operations

**Why These Choices:**
- **Hybrid GitHub approach**: `gh` CLI for fast issue creation + PyGithub for GraphQL sub-issue linking
- **SQLite**: Lightweight state tracking without external dependencies
- **Rich**: Professional progress indicators for autonomous monitoring
- **Click**: Self-documenting CLI with robust argument handling

---

## Project Structure

```
gh-issue-hierarchy/
├── gh_issue_hierarchy/          # Main package
│   ├── cli.py                   # Click command definitions
│   ├── core.py                  # Main orchestration
│   ├── github_client.py         # GitHub operations wrapper
│   ├── state_manager.py         # SQLite operations
│   ├── validator.py             # JSON schema validation
│   ├── fingerprint.py           # Issue deduplication logic
│   ├── graph.py                 # Dependency graph + topological sort
│   ├── interactive.py           # User prompts
│   └── utils.py                 # Helpers
├── tests/                       # Unit + integration tests
├── schemas/
│   └── input-schema.json        # JSON Schema definition
├── examples/
│   └── sample-input.json        # Example input file
├── .state/                      # SQLite database (gitignored)
├── logs/                        # Log files (gitignored)
├── config.example.json
├── pyproject.toml
└── CLAUDE.md                    # This file
```

---

## Architecture Decisions

### Decision 1: Two-Phase Issue Creation

### Decision 1: Two-Phase Creation with Immediate Linking

**Phase 1 - Create & Link:**
- Create parent issue first
- Immediately create and link children recursively (depth-first)
- Record each successful operation in SQLite before proceeding

**Phase 2 - Validation:**
- Verify all issues exist on GitHub
- Confirm all sub-issue relationships established
- Report inconsistencies

**Why:** Partial state is always valid (parent exists before children). Failed runs resume from exact failure point. No orphaned issues.

### Decision 2: SQLite State Management

**Database Location:** `.state/state.db` in project directory

**Schema - Two Tables:**

**`runs` table:**
- Tracks each execution run
- Fields: `run_id`, `input_file`, `input_file_hash`, `repository`, `started_at`, `completed_at`, `status`
- Status values: `in_progress`, `completed`, `failed`

**`created_issues` table:**
- Records every created issue
- Fields: `run_id`, `local_id`, `github_issue_number`, `github_issue_url`, `github_node_id`, `title`, `fingerprint`, `parent_id`, `parent_issue_number`, `linked_at`, `created_at`
- Indexes on: `fingerprint`, `local_id`, `run_status`

**Fingerprint Algorithm:**
- `SHA256(repository + title + body_first_100_chars)`
- Used for duplicate detection across runs
- Enables idempotent operations

**Why:** Lightweight, no external dependencies, fast lookups, survives process crashes, enables precise resume logic.

### Decision 3: Hybrid GitHub Integration

**Issue Creation:** GitHub CLI (`gh issue create`)
- Faster than direct API calls
- Handles authentication automatically
- Parses issue number from output URL

**Sub-Issue Linking:** PyGithub GraphQL API
- GitHub CLI doesn't expose sub-issue API
- Requires GraphQL mutation: `addSubIssue`
- Needs `node_id` (not issue number) for both parent and child

**Authentication:** Both use same GitHub token from `gh auth token`

**Why:** Combines speed of CLI with power of GraphQL. No duplicate auth setup.

### Decision 4: Flat JSON with Parent References

### Decision 4: Flat JSON with Parent References

**Structure:** Array of issues, each with optional `parent_id` reference

**Example:**
```json
{
  "repository": "owner/repo",
  "defaults": {
    "milestone": "MVP Sprint 1",
    "labels": ["subsystem"],
    "assignees": []
  },
  "issues": [
    {
      "id": "parent-1",
      "title": "Database Setup",
      "body": "Setup PostgreSQL...",
      "parent_id": null,
      "labels": ["database"]
    },
    {
      "id": "parent-1.task-1",
      "title": "Docker Config",
      "body": "Configure...",
      "parent_id": "parent-1"
    }
  ]
}
```

**Field Inheritance Rules:**
- Issue-level fields override defaults
- Labels are **additive**: merge issue + default labels
- `parent_id: null` = root issue
- Missing fields use defaults, then GitHub defaults

**Why:** Easy to edit manually, simple to generate programmatically (LLM-friendly), clear parent references, supports arbitrary depth, topological sort trivial.

### Decision 5: Interactive Prompts for Missing Resources

**When Milestone Doesn't Exist:**
- Option 1: Create new milestone (with description prompt)
- Option 2: Choose from existing milestones (show table)
- Option 3: Skip milestone (no milestone assigned)

**When Labels Don't Exist:**
- Option 1: Create all missing labels
- Option 2: Choose which labels to create (individual prompts)
- Option 3: Skip missing labels

**Implementation:** Use Rich library for menus/tables/prompts

**Why:** Prevents script failures on missing resources. User maintains control over GitHub repo organization.

---

## Module Responsibilities

### `cli.py` - Command-Line Interface
**Commands:**
- `create` - Main issue creation with options: `--input`, `--repo`, `--dry-run`, `--resume`, `--force`, `--config`, `--log-level`
- `validate` - Validate JSON input against schema
- `status` - Show run status (specific or all runs)
- `list-runs` - List all runs in database
- `cleanup` - Remove run from database (optionally delete GitHub issues)

**Responsibilities:**
- Parse CLI arguments with Click
- Load configuration file
- Initialize logging
- Call appropriate module functions
- Handle user-facing errors gracefully

### `core.py` - Main Orchestration
**Key Functions:**
- Initialize components (state manager, GitHub client, graph)
- Compute input file hash
- Handle resume vs new run logic
- Execute milestone/label validation (call interactive module)
- Build dependency graph and topological sort
- Main issue creation loop with progress bar
- Validation phase
- Generate summary report

**Responsibilities:**
- Coordinate all modules
- Track statistics (created/skipped/failed/linked)
- Progress visualization with Rich
- Error aggregation and reporting

### `github_client.py` - GitHub Operations
**Key Functions:**
- `create_issue()` - Use `gh` CLI subprocess
- `link_sub_issue()` - PyGithub GraphQL mutation
- `get_milestones()` - Fetch existing milestones
- `create_milestone()` - Create new milestone
- `get_labels()` - Fetch existing labels  
- `create_label()` - Create new label
- `verify_issue_exists()` - Check if issue exists

**Responsibilities:**
- Wrap all GitHub API operations
- Handle GitHub CLI authentication
- Parse `gh` command outputs
- Retry logic with exponential backoff (3 attempts)
- Error translation (subprocess errors → readable messages)

### `state_manager.py` - SQLite Operations
**Key Functions:**
- `init_database()` - Create schema if not exists
- `create_run()` - Start new run record
- `get_run_by_hash()` - Find existing run by input hash
- `get_created_issue()` - Lookup issue by local_id
- `find_by_fingerprint()` - Find duplicate by fingerprint
- `record_created_issue()` - Save newly created issue
- `record_link()` - Update when sub-issue linked
- `mark_run_complete()` - Update run status
- `get_run_stats()` - Calculate statistics

**Responsibilities:**
- All SQLite database operations
- Connection management
- Index maintenance
- Query optimization
- Transaction safety

### `validator.py` - JSON Validation
**Key Functions:**
- `load_schema()` - Load JSON schema from file
- `validate_input_file()` - Validate against schema
- `validate_no_circular_dependencies()` - Graph cycle detection
- `validate_parent_references()` - Ensure parent_ids exist

**Responsibilities:**
- JSON schema validation with detailed errors
- Structural validation (cycles, orphans)
- Early failure before any GitHub operations
- Clear error messages with path information

### `graph.py` - Dependency Graph
**Key Functions:**
- `build_adjacency_list()` - Build parent→children map
- `topological_sort()` - DFS-based sort (parents before children)
- `get_children()` - Get direct children of issue
- `get_depth()` - Calculate tree depth for issue

**Responsibilities:**
- Parse parent-child relationships
- Topological sorting (ensures parents created first)
- Tree traversal operations
- Depth calculations for display

### `fingerprint.py` - Deduplication
**Key Functions:**
- `generate_fingerprint()` - Create SHA256 hash from repo + title + body preview

**Responsibilities:**
- Consistent fingerprint generation
- Collision resistance
- Enable idempotent operations

### `interactive.py` - User Prompts
**Key Functions:**
- `prompt_for_milestone()` - Handle missing milestone
- `prompt_for_labels()` - Handle missing labels

**Responsibilities:**
- Rich-based interactive menus
- Call GitHub client to create resources
- Return selected/created resource names
- Handle user cancellations gracefully

---

## Data Structures

### Input JSON Schema
**Required Fields:**
- `repository` (string, pattern: `owner/repo`)
- `issues` (array, min 1 item)
  - Each issue requires: `id`, `title`

**Optional Fields:**
- `defaults` object with `milestone`, `labels`, `assignees`, `due_date`
- Per-issue: `body`, `parent_id`, `milestone`, `labels`, `assignees`, `due_date`

**Validation Rules:**
- Issue IDs must be unique
- Issue IDs pattern: `[a-zA-Z0-9._-]+`
- Parent IDs must reference existing issue IDs
- No circular dependencies
- Title max 256 characters

### State Database Records
**Run Record:**
```python
{
  "run_id": "20251024_143022",
  "input_file": "issues.json",
  "input_file_hash": "abc123...",
  "repository": "owner/repo",
  "started_at": "2025-10-24 14:30:22",
  "completed_at": None,  # or timestamp
  "status": "in_progress"  # or "completed", "failed"
}
```

**Created Issue Record:**
```python
{
  "run_id": "20251024_143022",
  "local_id": "parent-1.task-1",
  "github_issue_number": 45,
  "github_issue_url": "https://github.com/owner/repo/issues/45",
  "github_node_id": "I_kwDOAbc123",  # For GraphQL
  "title": "Docker Configuration",
  "fingerprint": "def456...",
  "parent_id": "parent-1",
  "parent_issue_number": 44,
  "linked_at": "2025-10-24 14:30:45",
  "created_at": "2025-10-24 14:30:40"
}
```

### Configuration File
**Location:** `config.json` in project directory

**Fields:**
```json
{
  "state_db_path": ".state/state.db",
  "log_directory": "logs/",
  "log_level": "INFO",
  "retry_attempts": 3,
  "retry_backoff_seconds": 5,
  "github_api_timeout_seconds": 30,
  "enable_color": true
}
```

---

## Execution Flow

### Main Creation Flow
1. Parse CLI arguments
2. Load and validate JSON input (fail fast if invalid)
3. Initialize SQLite state database
4. Compute input file hash
5. Check for existing run:
   - If incomplete run exists → Resume mode
   - If completed run exists → Warn, exit (unless `--force`)
   - If no run exists → Create new run record
6. Validate milestone exists (prompt if missing)
7. Validate labels exist (prompt if missing)
8. Build dependency graph from issues
9. Topological sort (parents before children)
10. For each issue in sorted order:
    - Check if already created (database lookup)
    - Check fingerprint for duplicates (unless `--force`)
    - If exists: Skip, log warning
    - If not exists: Create issue via `gh` CLI
    - Parse issue number and URL from output
    - Get `node_id` via PyGithub
    - Record in database
    - If has parent: Link via GraphQL, update database
    - Show progress in Rich progress bar
11. Validation phase (optional):
    - Query GitHub for all created issues
    - Verify sub-issue relationships
    - Report inconsistencies
12. Mark run as complete
13. Print summary statistics

### Resume Logic
- Load existing run from database
- Get list of already-created issues
- Skip fingerprint generation for existing issues
- Continue from next uncreated issue in topological order
- Link any unlinked sub-issues

### Error Handling Strategy
**Network Errors (gh CLI failures):**
- Retry 3 times with exponential backoff (5s, 10s, 20s)
- Log error details
- Continue to next issue (don't fail entire run)

**Linking Errors (GraphQL):**
- Retry 5 times with backoff
- Log warning if all retries fail
- Issue still created (just not linked)
- Add to "needs manual review" list

**Input Validation Errors:**
- Fail immediately before any GitHub operations
- Print detailed JSON schema error with path
- Exit with code 1

**Database Errors:**
- Critical failure (cannot proceed safely)
- Print error message
- Suggest checking database path/permissions
- Exit with code 2

---

## Logging & Output

### Log Files
**Location:** `logs/` directory  
**Structure:**
- `gh-issue-hierarchy.log` - Main log (rotating, 10MB, 5 backups)
- `runs/YYYYMMDD_HHMMSS_runid.log` - Per-run detailed log

**Log Levels:**
- ERROR: Creation failures, API errors, critical issues
- WARNING: Linking failures, skipped duplicates, missing resources
- INFO: Issue created, run started/completed, validation results (DEFAULT)
- DEBUG: API calls, fingerprints, database queries, retries

### Console Output
**Use Rich library for:**
- Progress bars during issue creation
- Tables for summary statistics
- Colored status messages (✓ green, ⚠ yellow, ✗ red)
- Panels for section headers
- Interactive prompts with tables

**Example Summary:**
```
╭─────────────────────────────╮
│  Summary                     │
├─────────────────────────────┤
│  ✓ Created: 98              │
│  ⚠ Skipped: 8               │
│  ✗ Failed: 0                │
│  🔗 Linked: 92              │
│  ⏱ Duration: 3m 42s         │
╰─────────────────────────────╯
```

---

## Testing Requirements

### Unit Tests
1. **Validator:**
   - Valid JSON passes
   - Invalid JSON fails with specific errors
   - Circular dependency detection
   - Orphaned parent_id detection

2. **Fingerprint:**
   - Same input = same fingerprint
   - Different input = different fingerprint
   - Collision resistance test

3. **Graph:**
   - Topological sort correctness
   - Multiple root handling
   - Depth calculation accuracy

4. **State Manager:**
   - Database initialization
   - CRUD operations
   - Fingerprint lookups
   - Run statistics

### Integration Tests
- Mock `gh` CLI subprocess calls
- Test full flow with mocked GitHub
- Test resume logic with partial database
- Test error handling and retries

---

## Usage Examples

```bash
# Create issues from input
python -m gh_issue_hierarchy create --input issues.json

# Dry run (preview only)
python -m gh_issue_hierarchy create --input issues.json --dry-run

# Resume failed run
python -m gh_issue_hierarchy create --input issues.json --resume 20251024_143022

# Force recreate (ignore duplicates)
python -m gh_issue_hierarchy create --input issues.json --force

# Validate input file
python -m gh_issue_hierarchy validate --input issues.json

# Check run status
python -m gh_issue_hierarchy status --run-id 20251024_143022

# List all runs
python -m gh_issue_hierarchy list-runs

# Clean up run (dangerous!)
python -m gh_issue_hierarchy cleanup --run-id 20251024_143022 --delete-issues
```

---

## Success Criteria

- ✅ Creates 100+ issues reliably without manual intervention
- ✅ Resumes failed runs without creating duplicates
- ✅ Completes 106-issue UMS creation in <5 minutes
- ✅ Zero duplicate issues in resume scenarios
- ✅ All sub-issue relationships correctly established
- ✅ Interactive prompts handle missing milestones/labels gracefully
- ✅ Detailed logs enable debugging any failures
- ✅ Validates input before any GitHub API calls

---

## Future MCP Integration Notes

The tool is designed for easy MCP wrapping:
- JSON input/output (native MCP format)
- Stateless per-invocation (state in database)
- Structured error responses
- Dry-run mode for safe LLM use
- Progress can be adapted to MCP notifications

---

**Document Version:** 1.0  
**Last Updated:** 2025-10-24  
**Status:** Ready for Implementation
