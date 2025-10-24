# Claude Skill Context: GitHub Issue Hierarchy Input Generator

This document provides complete context for building a Claude Skill that generates JSON input files for the `gh-issue-hierarchy` tool.

---

## Skill Purpose

Create a Claude Skill that helps users generate well-structured JSON input files for creating hierarchical GitHub issues. The skill should:

1. **Understand user intent** from natural language descriptions
2. **Generate valid JSON** matching the input schema
3. **Apply best practices** for issue hierarchies
4. **Validate the output** before returning to user
5. **Provide helpful suggestions** for improvement

---

## Input Schema Reference

### Complete JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["repository", "issues"],
  "properties": {
    "repository": {
      "type": "string",
      "description": "GitHub repository in format 'owner/repo'",
      "pattern": "^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$"
    },
    "defaults": {
      "type": "object",
      "properties": {
        "milestone": { "type": "string" },
        "labels": { "type": "array", "items": { "type": "string" } },
        "assignees": { "type": "array", "items": { "type": "string" } },
        "due_date": { "type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$" }
      }
    },
    "issues": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["id", "title"],
        "properties": {
          "id": {
            "type": "string",
            "pattern": "^[a-zA-Z0-9._-]+$",
            "description": "Unique identifier (use dot notation for hierarchy)"
          },
          "title": {
            "type": "string",
            "minLength": 1,
            "maxLength": 256
          },
          "body": { "type": "string" },
          "parent_id": { "type": ["string", "null"] },
          "milestone": { "type": "string" },
          "labels": { "type": "array", "items": { "type": "string" } },
          "assignees": { "type": "array", "items": { "type": "string" } },
          "due_date": { "type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$" }
        }
      }
    }
  }
}
```

### Field Descriptions

| Field | Required | Type | Description | Example |
|-------|----------|------|-------------|---------|
| `repository` | ✅ Yes | string | Format: `owner/repo` | `"microsoft/vscode"` |
| `defaults.milestone` | ❌ No | string | Applied to all issues unless overridden | `"Sprint 1"` |
| `defaults.labels` | ❌ No | array | Merged with issue-specific labels (additive) | `["enhancement"]` |
| `defaults.assignees` | ❌ No | array | Overridden by issue-specific assignees | `["username"]` |
| `defaults.due_date` | ❌ No | string | ISO date format | `"2025-12-31"` |
| `issues[].id` | ✅ Yes | string | Unique identifier, use dot notation | `"backend.api"` |
| `issues[].title` | ✅ Yes | string | Max 256 chars | `"Build REST API"` |
| `issues[].body` | ❌ No | string | Markdown supported | `"## Goals\n- API endpoints"` |
| `issues[].parent_id` | ❌ No | string/null | Reference to parent's `id`, null for root | `"backend"` or `null` |
| `issues[].labels` | ❌ No | array | Merged with defaults | `["api", "backend"]` |

---

## Best Practices for Input Generation

### 1. Issue ID Naming Convention

**✅ GOOD - Dot Notation:**
```json
{
  "id": "backend",
  "id": "backend.api",
  "id": "backend.api.auth",
  "id": "backend.database",
  "id": "backend.database.migrations"
}
```

**Why It Works:**
- Hierarchy is immediately visible
- Easy to read in database queries
- Searchable and sortable
- Natural grouping

**❌ BAD:**
```json
{
  "id": "1",  // Not descriptive
  "id": "task-1",  // No context
  "id": "backend-api-authentication-with-jwt-tokens-implementation"  // Too long
}
```

### 2. Hierarchy Levels and Structure

**Recommended Pattern:**

```
Epic (root)
└── Feature (child of epic)
    ├── Task (child of feature)
    │   └── Subtask (child of task)
    └── Task (child of feature)
```

**Example:**
```json
{
  "issues": [
    {
      "id": "user-management",
      "title": "User Management System",
      "parent_id": null,
      "labels": ["epic"]
    },
    {
      "id": "user-management.authentication",
      "title": "User Authentication",
      "parent_id": "user-management",
      "labels": ["feature"]
    },
    {
      "id": "user-management.authentication.login",
      "title": "Login Endpoint",
      "parent_id": "user-management.authentication",
      "labels": ["task"]
    }
  ]
}
```

**Depth Guidelines:**
- **2 levels**: Small projects (Epic → Task)
- **3 levels**: Medium projects (Epic → Feature → Task)
- **4 levels**: Large projects (Epic → Feature → Task → Subtask)
- **5+ levels**: Rarely needed, can become unwieldy

### 3. Issue Title Guidelines

**Format:**
- Start with action verb for tasks: "Build", "Implement", "Create", "Fix", "Refactor"
- Use nouns for epics/features: "User Management", "Payment System"
- Be specific but concise (aim for 3-8 words)
- Avoid redundancy with parent titles

**Examples:**

```json
// Epic level - noun phrase
{"title": "Backend Development"}

// Feature level - noun phrase with context
{"title": "User Authentication System"}

// Task level - action verb
{"title": "Implement JWT Token Generation"}

// Subtask level - specific action
{"title": "Add Token Expiration Logic"}
```

### 4. Issue Body Best Practices

**Structure for Epic/Feature:**
```markdown
Brief description of the initiative.

## Goals
- Goal 1
- Goal 2
- Goal 3

## Success Criteria
- Criterion 1
- Criterion 2

## Dependencies
- [List any blockers or prerequisites]
```

**Structure for Task:**
```markdown
Description of what needs to be done.

### Implementation Steps
1. Step 1
2. Step 2
3. Step 3

### Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

### Technical Notes
[Any relevant technical details]
```

### 5. Label Strategy

**Common Label Schemes:**

**By Type:**
```json
["epic", "feature", "task", "bug", "enhancement"]
```

**By Area:**
```json
["backend", "frontend", "database", "api", "ui"]
```

**By Status/Priority:**
```json
["priority:high", "priority:low", "blocked", "ready"]
```

**Best Practice:**
- Use 2-4 labels per issue
- Mix type + area labels
- Use `defaults.labels` for project-wide labels
- Use issue-specific labels for specialized tags

**Example:**
```json
{
  "defaults": {
    "labels": ["project:mvp", "sprint-1"]
  },
  "issues": [
    {
      "id": "backend",
      "labels": ["epic", "backend"],  // Merged with defaults
      // Final labels: ["project:mvp", "sprint-1", "epic", "backend"]
    }
  ]
}
```

### 6. Milestone and Due Date Usage

**Milestones:**
- Use for sprints or releases
- One milestone per sprint/release
- Apply at defaults level if all issues belong to same milestone

**Due Dates:**
- ISO format: `YYYY-MM-DD`
- Set on leaf nodes (tasks/subtasks), not epics
- Be realistic with timelines

```json
{
  "defaults": {
    "milestone": "MVP Release"
  },
  "issues": [
    {
      "id": "backend.api.auth",
      "due_date": "2025-11-15"  // Task deadline
    }
  ]
}
```

---

## Common Patterns and Templates

### Pattern 1: Simple Project (2 levels)

```json
{
  "repository": "owner/repo",
  "defaults": {
    "labels": ["mvp"]
  },
  "issues": [
    {
      "id": "setup",
      "title": "Project Setup",
      "body": "Initial project configuration and setup.",
      "parent_id": null,
      "labels": ["epic"]
    },
    {
      "id": "setup.docker",
      "title": "Docker Configuration",
      "body": "Create docker-compose.yml for development.",
      "parent_id": "setup"
    },
    {
      "id": "setup.ci",
      "title": "CI/CD Pipeline",
      "body": "Set up GitHub Actions workflow.",
      "parent_id": "setup"
    }
  ]
}
```

### Pattern 2: Feature Development (3 levels)

```json
{
  "repository": "owner/repo",
  "defaults": {
    "milestone": "Q4 2025",
    "labels": ["feature"]
  },
  "issues": [
    {
      "id": "payments",
      "title": "Payment Processing System",
      "body": "Complete payment integration.",
      "parent_id": null,
      "labels": ["epic", "backend"]
    },
    {
      "id": "payments.stripe",
      "title": "Stripe Integration",
      "body": "Integrate Stripe payment gateway.",
      "parent_id": "payments",
      "labels": ["integration"]
    },
    {
      "id": "payments.stripe.webhook",
      "title": "Webhook Handler",
      "body": "Handle Stripe webhook events.",
      "parent_id": "payments.stripe",
      "labels": ["backend", "api"]
    },
    {
      "id": "payments.stripe.ui",
      "title": "Payment Form UI",
      "body": "Build payment form with Stripe Elements.",
      "parent_id": "payments.stripe",
      "labels": ["frontend", "ui"]
    }
  ]
}
```

### Pattern 3: Full-Stack Feature (Complex)

```json
{
  "repository": "owner/repo",
  "defaults": {
    "milestone": "Beta Launch",
    "assignees": []
  },
  "issues": [
    {
      "id": "user-auth",
      "title": "User Authentication System",
      "body": "Complete authentication and authorization system.\n\n## Goals\n- Secure login/logout\n- JWT tokens\n- Password reset\n- Email verification",
      "parent_id": null,
      "labels": ["epic", "security"]
    },
    {
      "id": "user-auth.backend",
      "title": "Backend Authentication",
      "body": "Server-side authentication implementation.",
      "parent_id": "user-auth",
      "labels": ["feature", "backend"]
    },
    {
      "id": "user-auth.backend.jwt",
      "title": "JWT Token Service",
      "body": "Implement JWT generation and validation.\n\n### Tasks\n- Generate tokens\n- Validate tokens\n- Refresh tokens\n- Revoke tokens",
      "parent_id": "user-auth.backend",
      "labels": ["backend", "api"]
    },
    {
      "id": "user-auth.backend.endpoints",
      "title": "Auth API Endpoints",
      "body": "Create authentication endpoints.\n\n### Endpoints\n- POST /api/auth/register\n- POST /api/auth/login\n- POST /api/auth/refresh\n- POST /api/auth/logout",
      "parent_id": "user-auth.backend",
      "labels": ["backend", "api"]
    },
    {
      "id": "user-auth.frontend",
      "title": "Frontend Authentication",
      "body": "Client-side authentication implementation.",
      "parent_id": "user-auth",
      "labels": ["feature", "frontend"]
    },
    {
      "id": "user-auth.frontend.login",
      "title": "Login Page",
      "body": "Build login form with validation.",
      "parent_id": "user-auth.frontend",
      "labels": ["frontend", "ui"]
    },
    {
      "id": "user-auth.frontend.register",
      "title": "Registration Page",
      "body": "Build registration form with validation.",
      "parent_id": "user-auth.frontend",
      "labels": ["frontend", "ui"]
    }
  ]
}
```

---

## Validation Rules to Enforce

### Critical Validations

1. **Unique IDs:**
   - Every `id` must be unique across all issues
   - Check for duplicates before returning

2. **Parent References:**
   - Every `parent_id` must reference an existing issue's `id`
   - Or be `null` for root issues

3. **No Circular Dependencies:**
   - Issue A cannot be parent of B if B is ancestor of A
   - Validate the graph is acyclic

4. **Repository Format:**
   - Must match pattern: `owner/repo`
   - No URLs, no trailing slashes

5. **Title Length:**
   - Max 256 characters
   - Minimum 1 character

6. **ID Pattern:**
   - Only alphanumeric, dots, dashes, underscores
   - Pattern: `^[a-zA-Z0-9._-]+$`

### Recommended Validations

1. **Depth Check:**
   - Warn if hierarchy exceeds 4 levels
   - Suggest flattening

2. **Label Consistency:**
   - Check for typos in similar labels
   - Suggest consolidation

3. **Empty Bodies:**
   - Warn if epic/feature lacks description
   - Tasks can have minimal body

---

## User Interaction Patterns

### Skill Input Examples

**Example 1: Natural Language**

**User:** "Create issues for a user authentication system with login, registration, and password reset features"

**Expected Output:**
```json
{
  "repository": "user/repo",
  "defaults": {
    "labels": ["feature", "authentication"]
  },
  "issues": [
    {
      "id": "auth",
      "title": "User Authentication System",
      "body": "Complete authentication system with login, registration, and password reset.\n\n## Features\n- User login\n- User registration\n- Password reset\n- Session management",
      "parent_id": null,
      "labels": ["epic", "security"]
    },
    {
      "id": "auth.login",
      "title": "User Login",
      "body": "Implement user login functionality.\n\n### Requirements\n- Email/password authentication\n- Remember me option\n- Input validation\n- Error handling",
      "parent_id": "auth"
    },
    {
      "id": "auth.registration",
      "title": "User Registration",
      "body": "Implement user registration functionality.\n\n### Requirements\n- Email validation\n- Password strength requirements\n- Email verification\n- Terms acceptance",
      "parent_id": "auth"
    },
    {
      "id": "auth.password-reset",
      "title": "Password Reset",
      "body": "Implement password reset functionality.\n\n### Requirements\n- Email verification\n- Secure token generation\n- Token expiration\n- Password update",
      "parent_id": "auth"
    }
  ]
}
```

**Example 2: Structured Request**

**User:** "Generate issues for my-org/api-project with these epics: Backend (with Database and API tasks), Frontend (with UI and Components tasks), and DevOps (with CI/CD and Docker tasks)"

**Expected Output:** Generate 3 epic-level issues, each with 2 child tasks, properly structured with IDs like `backend`, `backend.database`, `backend.api`, etc.

### Skill Behavior Guidelines

1. **Always ask for repository** if not provided
2. **Suggest default labels** based on issue type
3. **Auto-generate IDs** using dot notation from titles
4. **Add descriptions** to epics/features (don't leave body empty)
5. **Validate before returning** and report any issues
6. **Offer to save** the output to a file

---

## Error Prevention

### Common Mistakes to Avoid

❌ **Mistake 1: Forgetting parent_id: null**
```json
// WRONG - root issue without parent_id: null
{"id": "epic", "title": "Epic"}

// CORRECT
{"id": "epic", "title": "Epic", "parent_id": null}
```

❌ **Mistake 2: Forward references**
```json
// WRONG - child defined before parent
[
  {"id": "child", "parent_id": "parent"},
  {"id": "parent", "parent_id": null}
]

// CORRECT - parent before child
[
  {"id": "parent", "parent_id": null},
  {"id": "child", "parent_id": "parent"}
]
```

❌ **Mistake 3: Inconsistent ID schemes**
```json
// WRONG - mixing schemes
{"id": "backend"},
{"id": "frontend-ui"},  // Should be "frontend.ui"
{"id": "testing_unit"}  // Should be "testing.unit"
```

❌ **Mistake 4: Overriding labels incorrectly**
```json
// WRONG - issue labels replace defaults
"defaults": {"labels": ["project"]},
"issues": [{"labels": ["backend"]}]  // Only gets "backend", loses "project"

// CORRECT - labels are additive (merged)
// Issue will have both: ["project", "backend"]
```

❌ **Mistake 5: Invalid repository format**
```json
// WRONG
"repository": "https://github.com/owner/repo"
"repository": "owner/repo/"
"repository": "owner"

// CORRECT
"repository": "owner/repo"
```

---

## Testing and Validation

### Validation Checklist

Before returning generated JSON, verify:

- [ ] All `id` values are unique
- [ ] All `parent_id` values reference existing IDs (or are null)
- [ ] No circular dependencies exist
- [ ] Repository format is `owner/repo`
- [ ] All required fields present (`repository`, `issues`, `id`, `title`)
- [ ] Issue IDs match pattern `^[a-zA-Z0-9._-]+$`
- [ ] Titles are ≤256 characters
- [ ] At least one root issue exists (`parent_id: null`)
- [ ] Hierarchy is logical (parents before children)

### Example Validation Code (for skill)

```python
def validate_issue_hierarchy(data):
    issues = data["issues"]
    ids = {issue["id"] for issue in issues}

    # Check unique IDs
    if len(ids) != len(issues):
        return "Error: Duplicate IDs found"

    # Check parent references
    for issue in issues:
        parent_id = issue.get("parent_id")
        if parent_id is not None and parent_id not in ids:
            return f"Error: Issue '{issue['id']}' references non-existent parent '{parent_id}'"

    # Check for root issues
    if not any(issue.get("parent_id") is None for issue in issues):
        return "Error: No root issues found (all issues have parents)"

    return "Valid"
```

---

## Skill Prompt Template

```markdown
You are a GitHub Issue Hierarchy Generator. Your job is to create well-structured JSON input files for the gh-issue-hierarchy tool.

When the user describes their project needs:

1. **Extract Requirements:**
   - Repository name
   - List of features/epics
   - Any specific requirements (labels, milestones, etc.)

2. **Generate Structure:**
   - Create logical hierarchy (Epic → Feature → Task)
   - Use dot notation for IDs (e.g., "backend.api.auth")
   - Write descriptive titles and bodies
   - Apply appropriate labels

3. **Validate:**
   - Ensure all IDs are unique
   - Verify parent references are valid
   - Check no circular dependencies
   - Confirm at least one root issue

4. **Return:**
   - Complete JSON matching the schema
   - Brief explanation of the structure
   - Suggestion to validate with: `gh-issue-hierarchy validate --input file.json`

**Key Principles:**
- Root issues (epics) should have `parent_id: null`
- Use descriptive IDs with dot notation
- Keep titles concise (3-8 words)
- Add detailed bodies to epics/features
- Labels are additive (merged with defaults)
- Order matters: parents before children

**Example Output Format:**
```json
{
  "repository": "owner/repo",
  "defaults": {
    "milestone": "Sprint 1",
    "labels": ["enhancement"]
  },
  "issues": [...]
}
```
```

---

## Real-World Example (From Testing)

This is the actual input that was successfully tested:

```json
{
  "repository": "michaeltomlinsontuks/issueTool",
  "defaults": {
    "labels": ["enhancement"],
    "assignees": []
  },
  "issues": [
    {
      "id": "testing",
      "title": "Testing & Quality Assurance",
      "body": "Comprehensive testing suite for the GitHub Issue Hierarchy tool.\n\n## Goals\n- Unit tests for all modules\n- Integration tests with mocked GitHub\n- End-to-end testing\n- Test coverage reporting",
      "parent_id": null,
      "labels": ["testing", "epic"]
    },
    {
      "id": "testing.unit",
      "title": "Unit Tests for Core Modules",
      "body": "Create unit tests for all core modules.\n\n### Modules to test:\n- `validator.py` - JSON schema validation, circular dependency detection\n- `fingerprint.py` - Hash generation consistency\n- `graph.py` - Topological sort, depth calculation\n- `state_manager.py` - Database operations\n- `utils.py` - Helper functions",
      "parent_id": "testing",
      "labels": ["testing", "unit-tests"]
    },
    {
      "id": "testing.integration",
      "title": "Integration Tests with Mocked GitHub",
      "body": "Test full workflow with mocked GitHub API calls.\n\n### Test scenarios:\n- Complete run with multiple levels of hierarchy\n- Resume logic with partial completion\n- Duplicate detection\n- Error handling and retries",
      "parent_id": "testing",
      "labels": ["testing", "integration-tests"]
    }
  ]
}
```

**Results:**
- Created 12 issues successfully
- Linked 8 sub-issue relationships
- All labels auto-created
- Completed in 55 seconds

---

## Additional Resources

- **JSON Schema File**: `schemas/input-schema.json`
- **Example Input**: `examples/sample-input.json`
- **Full Specification**: `CLAUDE.md`
- **README**: Comprehensive usage guide
- **Test Input**: `test-input.json` (12-issue real-world example)

---

## Skill Success Criteria

A successful Claude Skill should:

1. ✅ Generate valid JSON that passes `gh-issue-hierarchy validate`
2. ✅ Use dot notation for IDs consistently
3. ✅ Create logical hierarchies (Epic → Feature → Task)
4. ✅ Write descriptive titles and bodies
5. ✅ Handle various input styles (natural language, structured, bullet points)
6. ✅ Validate output before returning
7. ✅ Provide helpful explanations
8. ✅ Suggest improvements when relevant
9. ✅ Save output to file when requested
10. ✅ Be conversational and iterative (allow refinements)

---

**Last Updated:** October 24, 2025
**Version:** 1.0
**Status:** Ready for Skill Development
