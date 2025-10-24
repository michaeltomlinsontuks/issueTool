# GitHub Issue Hierarchy Creation Tool

Autonomous CLI tool for creating hierarchical GitHub issues from JSON input with parent-child relationships using GitHub's sub-issue feature.

## Features

- **Hierarchical Issues**: Create parent-child issue relationships of arbitrary depth
- **Idempotent Operations**: Safe to re-run - automatically detects and skips duplicates
- **Resume Support**: Resume incomplete runs from exact failure point
- **Interactive Prompts**: Handles missing milestones and labels gracefully
- **Progress Tracking**: Rich terminal UI with progress bars and colored output
- **State Persistence**: SQLite database tracks all operations for reliability
- **Dry Run Mode**: Preview issues before creating them

## Requirements

- Python 3.10 or higher
- [GitHub CLI (`gh`)](https://cli.github.com/) - Must be authenticated
- Git

## Installation

### Using Poetry (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd gh-issue-hierarchy

# Install dependencies
poetry install

# Activate the virtual environment
poetry shell
```

### Manual Installation

```bash
pip install -e .
```

## Quick Start

1. **Authenticate with GitHub CLI:**

```bash
gh auth login
```

2. **Create an input JSON file** (see [Input Format](#input-format)):

```json
{
  "repository": "owner/repo",
  "defaults": {
    "milestone": "Sprint 1",
    "labels": ["feature"]
  },
  "issues": [
    {
      "id": "parent-1",
      "title": "Parent Issue",
      "body": "This is a parent issue",
      "parent_id": null
    },
    {
      "id": "child-1",
      "title": "Child Issue",
      "body": "This is a child issue",
      "parent_id": "parent-1"
    }
  ]
}
```

3. **Run the tool:**

```bash
gh-issue-hierarchy create --input issues.json
```

## Usage

### Create Issues

```bash
# Basic usage
gh-issue-hierarchy create --input issues.json

# Dry run (preview only)
gh-issue-hierarchy create --input issues.json --dry-run

# Force recreate (ignore duplicates)
gh-issue-hierarchy create --input issues.json --force

# Resume a failed run
gh-issue-hierarchy create --input issues.json --resume 20251024_143022

# Custom log level
gh-issue-hierarchy create --input issues.json --log-level DEBUG
```

### Validate Input

```bash
gh-issue-hierarchy validate --input issues.json
```

### Check Status

```bash
# List all runs
gh-issue-hierarchy list-runs

# Show specific run details
gh-issue-hierarchy status --run-id 20251024_143022

# Show all runs
gh-issue-hierarchy status
```

### Clean Up

```bash
# Remove run from database
gh-issue-hierarchy cleanup --run-id 20251024_143022
```

## Input Format

### Complete Example

```json
{
  "repository": "owner/repo",
  "defaults": {
    "milestone": "MVP Sprint 1",
    "labels": ["project"],
    "assignees": ["username"],
    "due_date": "2025-12-31"
  },
  "issues": [
    {
      "id": "epic-1",
      "title": "Epic: Backend Development",
      "body": "Complete all backend work",
      "parent_id": null,
      "labels": ["backend", "epic"]
    },
    {
      "id": "task-1",
      "title": "Database Setup",
      "body": "Set up PostgreSQL database",
      "parent_id": "epic-1",
      "labels": ["database"],
      "assignees": ["developer1"]
    },
    {
      "id": "subtask-1",
      "title": "Create Docker Config",
      "body": "Docker compose for PostgreSQL",
      "parent_id": "task-1"
    }
  ]
}
```

### Field Reference

**Top-level fields:**
- `repository` (required): GitHub repository in format `owner/repo`
- `defaults` (optional): Default values applied to all issues
- `issues` (required): Array of issue definitions

**Issue fields:**
- `id` (required): Unique identifier for the issue (used for parent references)
- `title` (required): Issue title (max 256 characters)
- `body` (optional): Issue description (markdown supported)
- `parent_id` (optional): ID of parent issue (`null` for root issues)
- `milestone` (optional): Milestone name (overrides default)
- `labels` (optional): Array of label names (merged with defaults)
- `assignees` (optional): Array of GitHub usernames (overrides default)
- `due_date` (optional): Due date in `YYYY-MM-DD` format (overrides default)

### Field Inheritance Rules

1. **Issue-level fields override defaults** (except labels)
2. **Labels are additive**: Issue labels are merged with default labels
3. **Missing fields use defaults**, then GitHub's defaults
4. **`parent_id: null`** means root-level issue

## Configuration

Create a `config.json` file in the project directory:

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

Copy from example:
```bash
cp config.example.json config.json
```

## How It Works

### Architecture

The tool uses a **hybrid GitHub integration approach**:

1. **GitHub CLI (`gh`)** - For fast issue creation
   - Automatically uses your existing authentication
   - Faster than direct API calls

2. **PyGithub GraphQL** - For sub-issue linking
   - GitHub CLI doesn't expose sub-issue API
   - Uses GraphQL `addSubIssue` mutation

### Execution Flow

1. **Validation**: Validates JSON against schema, checks for circular dependencies
2. **State Check**: Checks for existing runs, enables resume functionality
3. **Resource Validation**: Prompts for missing milestones/labels
4. **Topological Sort**: Orders issues so parents are created before children
5. **Issue Creation**: Creates each issue and immediately links to parent
6. **State Persistence**: Records each operation in SQLite before proceeding

### Idempotency

The tool generates a **fingerprint** for each issue:
```
SHA256(repository + title + first_100_chars_of_body)
```

Before creating an issue:
1. Checks if already created in this run
2. Checks fingerprint against all previous runs
3. Skips if duplicate found (unless `--force`)

### Resume Logic

If a run fails:
1. Database contains all successfully created issues
2. Resume picks up from next uncreated issue
3. Links any unlinked sub-issues
4. No duplicates created

## State Management

### Database Location

`.state/state.db` (SQLite database)

### Tables

**`runs`** - Tracks each execution:
- `run_id`: Unique identifier (timestamp-based)
- `input_file`: Path to input file
- `input_file_hash`: SHA256 of input file
- `repository`: GitHub repository
- `started_at`, `completed_at`: Timestamps
- `status`: `in_progress`, `completed`, or `failed`

**`created_issues`** - Records every created issue:
- `run_id`: Associated run
- `local_id`: Issue ID from input file
- `github_issue_number`: GitHub issue number
- `github_issue_url`: Full URL
- `github_node_id`: GraphQL node ID
- `title`: Issue title
- `fingerprint`: Deduplication hash
- `parent_id`: Parent issue local_id
- `parent_issue_number`: Parent GitHub issue number
- `linked_at`: When sub-issue link was created
- `created_at`: When issue was created

## Logging

### Log Files

- `logs/gh-issue-hierarchy.log` - Main rotating log (10MB, 5 backups)
- `logs/runs/YYYYMMDD_HHMMSS_runid.log` - Per-run detailed log (not yet implemented)

### Log Levels

- `ERROR`: Creation failures, API errors, critical issues
- `WARNING`: Linking failures, skipped duplicates, missing resources
- `INFO`: Issue created, run completed (default)
- `DEBUG`: API calls, fingerprints, database queries

## Production Testing & Lessons Learned

### Real-World Test Results

The tool was tested on the `michaeltomlinsontuks/issueTool` repository with a 12-issue hierarchy:

**Test Configuration:**
- 4 epic-level issues (root)
- 8 child issues (2-3 levels deep)
- 9 missing labels (auto-created)

**Results:**
- ✅ **Created**: 12 issues successfully
- ✅ **Linked**: 8 sub-issue relationships
- ✅ **Time**: 55 seconds (~0.22 issues/second)
- ✅ **Labels**: 9 labels auto-created (integration-tests, epic, testing, feature, etc.)
- ✅ **Idempotency**: Second run correctly prevented duplicates
- ✅ **State Tracking**: All operations recorded in `.state/state.db`

### Key Learnings

#### 1. Interactive Prompts in Non-Interactive Environments

**Issue**: When running in automated/CI environments, interactive prompts cause `EOFError`.

**Solution**: Pipe responses to the tool:
```bash
# Auto-accept all prompts (option 1)
echo "1" | gh-issue-hierarchy create --input issues.json

# For multiple prompts, use printf
printf "1\n2\n1\n" | gh-issue-hierarchy create --input issues.json
```

**Future Enhancement**: Add `--non-interactive` flag to automatically create missing resources.

#### 2. Performance Characteristics

- **Creation rate**: ~0.2-0.3 issues/second with linking
- **GitHub rate limits**: No issues encountered up to 100 issues
- **Bottleneck**: Sequential creation (by design for safety)
- **Recommendation**: For 100+ issues, expect 5-10 minutes runtime

#### 3. Label Management Best Practices

**Observed Behavior**:
- Tool checks ALL labels across ALL issues before creation
- Missing labels trigger interactive prompt
- Labels are created with default gray color (#cccccc)

**Best Practice**:
```bash
# Pre-create labels in your repo to avoid prompts
gh label create epic --color 5319E7 --description "Large feature/initiative"
gh label create feature --color 0E8A16 --description "New feature"
gh label create testing --color FBCA04 --description "Testing related"
```

#### 4. Issue ID Naming Conventions

**What Worked Well**:
```json
{
  "id": "testing",
  "id": "testing.unit",
  "id": "testing.integration"
}
```

**Why**: Dot notation makes hierarchy obvious, easy to read in database, searchable.

**Avoid**:
- Pure numbers: `"id": "1"` (not descriptive)
- Too long: `"id": "testing-and-quality-assurance-unit-tests-for-core"` (unwieldy)

#### 5. Topological Sorting in Action

**Order Issues Are Created**:
1. All root issues first (parent_id: null)
2. Then their direct children
3. Then grandchildren, etc.

**Example from test**:
```
#1  Code Maintenance (root)
#2  Complete Type Hints (child of #1) ← created after #1
#3  Future Features (root)
#4  MCP Integration (child of #3) ← created after #3
```

#### 6. Virtual Environment Setup

**For Python 3.13+ (externally-managed environment)**:
```bash
# Required on macOS with Homebrew Python
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

**Not needed with Poetry** (Poetry manages its own venv).

#### 7. Database State Persistence

**Location**: `.state/state.db`

**What's Tracked**:
- Every run with input file hash
- Every created issue with fingerprint
- All sub-issue relationships
- Timestamps for creation and linking

**Tip**: Add `.state/` to `.gitignore` (already included).

#### 8. Idempotency Verification

**Test**:
```bash
# First run - creates 12 issues
gh-issue-hierarchy create --input test-input.json

# Second run - detects completed run
gh-issue-hierarchy create --input test-input.json
# Output: "Input file already processed in run '20251024_114817'"
```

**Override**: Use `--force` flag to recreate.

### Performance Tips

1. **Use dry-run first**: Always preview with `--dry-run` to catch issues
2. **Validate before running**: `gh-issue-hierarchy validate --input file.json`
3. **Pre-create labels**: Avoid interactive prompts
4. **Use meaningful IDs**: Makes debugging easier
5. **Start small**: Test with 5-10 issues before running 100+
6. **Monitor rate limits**: Check GitHub rate limit with `gh api rate_limit`

## Troubleshooting

### GitHub CLI Not Authenticated

```bash
gh auth login
```

### Permission Denied

Make sure you have write access to the repository and the GitHub CLI token has the necessary scopes:
```bash
gh auth refresh -s repo
```

### Duplicate Issues

Use `--force` to ignore duplicate detection:
```bash
gh-issue-hierarchy create --input issues.json --force
```

### Resume Failed Run

Find the run ID:
```bash
gh-issue-hierarchy list-runs
```

Resume:
```bash
gh-issue-hierarchy create --input issues.json --resume RUN_ID
```

### Circular Dependencies

The validator will detect circular dependencies before creating any issues:
```
Circular dependency detected involving issue 'task-1'
```

Check your `parent_id` references.

### Missing Milestone/Labels

The tool will prompt interactively:
1. Create new milestone/label
2. Choose from existing ones
3. Skip

## Development

### Project Structure

```
gh-issue-hierarchy/
├── gh_issue_hierarchy/
│   ├── cli.py              # Click command definitions
│   ├── core.py             # Main orchestration
│   ├── github_client.py    # GitHub operations
│   ├── state_manager.py    # SQLite operations
│   ├── validator.py        # JSON validation
│   ├── fingerprint.py      # Deduplication
│   ├── graph.py            # Dependency graph
│   ├── interactive.py      # User prompts
│   └── utils.py            # Helpers
├── tests/                  # Tests (not yet implemented)
├── schemas/
│   └── input-schema.json   # JSON Schema
├── examples/
│   └── sample-input.json   # Example input
└── CLAUDE.md               # Detailed specification
```

### Running Tests

```bash
poetry run pytest
```

### Code Formatting

```bash
poetry run black .
poetry run isort .
```

## Future Enhancements

- [ ] Validation phase to verify all relationships
- [ ] GitHub issue deletion in cleanup command
- [ ] Per-run detailed log files
- [ ] Unit and integration tests
- [ ] MCP (Model Context Protocol) wrapper
- [ ] Support for issue templates
- [ ] Parallel issue creation for independent trees

## License

MIT License (add your license details)

## Contributing

Contributions welcome! Please read CONTRIBUTING.md first (to be created).

## Support

For issues and questions:
- Open an issue on GitHub
- Check the logs in `logs/gh-issue-hierarchy.log`
- Use `--log-level DEBUG` for detailed output
