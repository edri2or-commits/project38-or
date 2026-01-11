# Claude Skills for project38-or

This directory contains reusable, version-controlled behaviors (Skills) for Claude Code CLI.

## What are Skills?

**Skills** are specialized agent behaviors that transform Claude from ad-hoc prompting to standardized workflow automation. Each skill is:

- 📁 **Version-controlled** - Lives in Git, changes tracked in PRs
- 🔒 **Scoped** - Defines allowed tools and safety constraints
- 🔄 **Reusable** - Can be triggered by keywords or explicit invocation
- 📚 **Self-documenting** - Includes role, instructions, and examples

## Available Skills

### 1. doc-updater (v1.0.0)

**Purpose:** Autonomous documentation maintainer

**Triggers:**
- Changes to `src/` directory
- Keywords: `documentation`, `docs`, `docstring`, `changelog`, `api reference`

**What it does:**
1. Detects code changes
2. Validates/adds docstrings (Google style)
3. Updates API documentation
4. Adds changelog entries
5. Validates with pydocstyle and mkdocs

**When to use:**
- After modifying functions/classes in `src/`
- Before creating a PR
- When CI workflow `docs-check.yml` fails

**Example:**
```bash
# Explicit invocation (if skill system supports it)
/doc-updater

# Or simply mention documentation needs
# "Update documentation for the changes I just made"
```

**Integration:**
Works alongside `docs-check.yml` CI workflow:
- Skill runs proactively during development
- CI validates before merge
- Together they enforce Zero Tolerance Documentation

### 2. test-runner (v1.0.0)

**Purpose:** Automated test execution before commits

**Triggers:**
- User about to commit code
- Changes to `src/` or `tests/` directories
- Keywords: `test`, `tests`, `pytest`, `run tests`, `before commit`

**What it does:**
1. Verifies test environment (pytest configuration)
2. Runs full test suite with verbose output
3. Optionally runs with coverage report
4. Analyzes test results (passed/failed/skipped)
5. Provides detailed failure reports with file/line context
6. Blocks commit recommendation if tests fail

**When to use:**
- Before committing code changes
- Before creating a PR
- After fixing bugs or adding features

**Example:**
```bash
# Before commit
"Run tests before I commit"

# With coverage
"Run tests with coverage"

# Before PR
"I'm ready to create a PR"
```

**Integration:**
Works alongside `test.yml` CI workflow:
- Skill runs proactively before commit (local)
- CI validates after push (server-side)
- Together they enforce Zero Broken Commits

### 3. security-checker (v1.0.0)

**Purpose:** Validates no secrets or sensitive data are being committed

**Triggers:**
- User about to commit code
- Changes to configuration files
- Keywords: `security`, `secrets`, `commit`, `check secrets`

**What it does:**
1. Checks staged changes with `git diff --cached`
2. Scans for sensitive file patterns (.env, *-key.json, *.pem)
3. Scans file contents for secret patterns:
   - AWS access keys, GitHub PATs, API keys
   - JWT tokens, private keys
   - Database URLs with credentials
   - Hardcoded passwords
4. Handles false positives (test data, documentation)
5. Verifies .gitignore protection
6. Blocks commit if secrets detected

**When to use:**
- Before committing any code
- Before creating a PR
- After adding API integrations or configuration

**Example:**
```bash
# Before commit
"Check for secrets before commit"

# Before PR
"I'm ready to create a PR"

# After config changes
"I added API configuration, check for secrets"
```

**Integration:**
First line of defense (local):
- Skill scans before commit
- Future: GitLeaks in CI (second line)
- Together they create defense in depth

**Critical:** This is a PUBLIC repository - any secret committed is permanently exposed.

### 4. pr-helper (v1.0.0)

**Purpose:** Standardized Pull Request creation

**Triggers:**
- Keywords: `pull request`, `pr`, `create pr`, `open pr`, `ready to merge`
- After passing all checks (tests, security, docs)

**What it does:**
1. Verifies prerequisites (branch pushed, not on main)
2. Analyzes branch changes with git log and diff
3. Determines change type (feat, fix, docs, refactor)
4. Drafts PR title (conventional commits format)
5. Generates comprehensive PR description
6. Creates PR using `gh pr create`
7. Reports PR URL and checks status

**When to use:**
- After completing a feature or fix
- When ready for code review
- After passing all skill checks

**Example:**
```bash
# After feature complete
"Create PR for my changes"

# Ready to merge
"Ready to merge"

# Specific request
"Open pull request for the skills I added"
```

**Integration:**
Works with other skills in sequence:
```
Code complete → test-runner ✅ → doc-updater ✅
→ security-checker ✅ → pr-helper ✅
```

### 5. dependency-checker (v1.0.0)

**Purpose:** Audits Python dependencies for security vulnerabilities, outdated versions, and best practices

**Triggers:**
- Changes to `requirements*.txt` files
- Keywords: `dependencies`, `vulnerabilities`, `outdated packages`, `audit dependencies`, `security audit`

**What it does:**
1. Scans for known security vulnerabilities using pip-audit
2. Identifies outdated packages with available updates
3. Validates requirements.txt format (pinning, version constraints)
4. Checks for dependency conflicts
5. Verifies lock files are synchronized
6. Generates prioritized remediation plan
7. Blocks deployment on CRITICAL/HIGH vulnerabilities

**When to use:**
- Before committing changes to requirements.txt
- Before creating a PR
- Monthly security audits
- After adding new dependencies

**Example:**
```bash
# After updating dependencies
"Check dependencies for vulnerabilities"

# Periodic audit
"Run dependency audit"

# Before PR
"Audit dependencies before creating PR"
```

**Integration:**
Works alongside CI/CD security scanning:
- Skill runs proactively during development (local)
- CI validates before merge (GitHub Actions)
- Together they enforce Zero Known Vulnerabilities

**Critical:** Blocks deployment on CRITICAL/HIGH vulnerabilities. All production dependencies must be pinned to exact versions.

## Skill Structure

Each skill follows this structure:

```
.claude/skills/
└── skill-name/
    └── SKILL.md          # Skill definition
```

### SKILL.md Format

```markdown
---
name: skill-name
description: What the skill does
version: 1.0.0
allowed-tools:
  - Read
  - Edit
  - Bash(specific-commands)
plan_mode_required: false/true
trigger_keywords:
  - keyword1
  - keyword2
---

# Role
Who the agent becomes when executing this skill

# Instructions
Step-by-step workflow

# Constraints and Safety
DO NOT / ALWAYS rules

# Examples
Concrete use cases
```

## Creating New Skills

### 1. Plan Your Skill

Ask yourself:
- What specific problem does this solve?
- What tools does it need?
- What can go wrong? (Safety constraints)
- Is human verification needed? (plan_mode_required)

### 2. Start with Template

```bash
mkdir -p .claude/skills/your-skill-name
cp .claude/skills/doc-updater/SKILL.md .claude/skills/your-skill-name/SKILL.md
# Edit to fit your use case
```

### 3. Define Safety Boundaries

**Allowed Tools:**
- Be specific (e.g., `Bash(npm run test)` not just `Bash`)
- Use `plan_mode_required: true` for risky operations

**Constraints:**
- What should the skill NEVER do?
- What should it ALWAYS do?

### 4. Test Thoroughly

1. Create a test scenario
2. Trigger the skill
3. Verify behavior matches expectations
4. Check error handling
5. Document edge cases

### 5. Document in CLAUDE.md

Add entry to the "Available Skills" section:
```markdown
## Available Skills

### skill-name
- **Purpose**: Brief description
- **Trigger**: Keywords or commands
- **Safety**: plan_mode_required setting
```

## Skill Best Practices

### ✅ DO

- Start with low-risk skills (documentation, formatting)
- Include concrete examples in SKILL.md
- Test error handling
- Document success metrics
- Use progressive disclosure (< 500 lines)
- Add troubleshooting section

### ❌ DON'T

- Create skills that modify production data without verification
- Grant unlimited tool access
- Skip error handling
- Assume skill will always succeed
- Mix multiple concerns in one skill

## Skill Patterns

### Pattern 1: Scaffolding
Generate boilerplate from templates
```yaml
allowed-tools:
  - Read (templates)
  - Write (new files)
  - Edit (configuration)
```

### Pattern 2: Validation & Remediation
Check for issues and auto-fix when safe
```yaml
allowed-tools:
  - Read
  - Grep
  - Edit (for fixes)
  - Bash (for validation)
```

### Pattern 3: Human-in-the-Loop
Generate plans, wait for approval, then execute
```yaml
plan_mode_required: true
allowed-tools:
  - Read
  - Edit (after approval)
  - Bash (after approval)
```

## Integration with Workflows

Skills complement GitHub Actions workflows:

| Stage | Responsibility |
|-------|----------------|
| **Development** | Skills run proactively in Claude CLI |
| **Pre-commit** | Skills validate before commit |
| **CI/CD** | Workflows validate before merge |
| **Post-merge** | Workflows deploy/publish |

**Example: doc-updater skill**
```
Developer changes code
    ↓
Skills detect and update docs automatically
    ↓
Developer reviews changes
    ↓
Developer commits
    ↓
docs-check.yml validates in CI
    ↓
PR approved and merged
```

## Troubleshooting

### Skill not triggering

**Check:**
1. Skill name matches directory name
2. SKILL.md has valid frontmatter
3. Trigger keywords match user input
4. Claude Code CLI supports skills (check version)

### Skill failing during execution

**Debug steps:**
1. Read the SKILL.md constraints
2. Check if required tools are available
3. Verify input matches expected format
4. Look for error messages in skill output
5. Test manually with each tool

### Tools being blocked

**Solution:**
1. Check allowed-tools whitelist in frontmatter
2. Be more specific (e.g., `Bash(pytest)` instead of `Bash`)
3. If truly needed, update allowed-tools list
4. Document why tool is needed

## Resources

- **Research:** `/docs/research/07_claude_skills_enterprise_implementation.summary.md`
- **Architecture:** `/docs/research/04_autonomous_agent_layer_architecture.summary.md`
- **Security:** `/docs/SECURITY.md`
- **Main docs:** `/CLAUDE.md`

## Roadmap

### Completed (v1.0.0)
- ✅ doc-updater skill - Autonomous documentation maintenance
- ✅ test-runner skill - Automated test execution before commits
- ✅ security-checker skill - Validates no secrets in commits
- ✅ pr-helper skill - Standardized PR creation
- ✅ dependency-checker skill - Audits dependencies for security vulnerabilities

### Future (v2.0.0+)
- changelog-updater (auto-update changelog on commits)
- Feature scaffolding (generate boilerplate from templates)
- Safe refactoring (with automated test loop)
- Code review assistant (automated PR review)
- Performance profiler (identify bottlenecks)

---

**Questions?** Check `/docs/research/07_claude_skills_enterprise_implementation.summary.md` for detailed patterns and architecture decisions.
