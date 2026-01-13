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

### 6. changelog-updater (v1.0.0)

**Purpose:** Automatically generates changelog entries from git commit history using conventional commits

**Triggers:**
- Preparing to create a Pull Request
- Multiple commits exist that aren't reflected in changelog
- Keywords: `changelog`, `update changelog`, `generate changelog`, `commits to changelog`, `before pr`

**What it does:**
1. Analyzes git commit history from branch divergence point
2. Parses conventional commit messages (feat, fix, docs, security, etc.)
3. Categorizes changes into appropriate changelog sections (Added/Changed/Fixed/Security)
4. Generates well-formatted, human-readable changelog entries
5. Groups related commits to reduce clutter
6. Updates `docs/changelog.md` under [Unreleased] section
7. Validates markdown syntax and completeness

**When to use:**
- Before creating a PR (to ensure all commits are documented)
- After completing a feature with multiple commits
- When conventional commits were used
- To automate changelog maintenance

**Example:**
```bash
# Before creating PR
"Update changelog before PR"

# Generate from commits
"Generate changelog from commits"

# After feature completion
"Update changelog for the OAuth2 feature"
```

**Integration:**
Works with doc-updater and CI/CD:
- changelog-updater generates entries from commits (automated)
- doc-updater validates changelog format (quality check)
- docs-check.yml ensures changelog completeness (CI gate)
- Together they enforce complete changelog coverage

**Benefits:**
- ✅ Saves time - no manual changelog writing
- ✅ Consistent format - follows Keep a Changelog standard
- ✅ Complete coverage - analyzes all commits
- ✅ Proper categorization - uses conventional commit types
- ✅ File references - includes paths and line numbers

**Typical workflow:**
```
Multiple commits with conventional format
    ↓
changelog-updater analyzes history
    ↓
Generates changelog entries automatically
    ↓
Developer reviews and commits
    ↓
CI validates with docs-check.yml
```

### 7. session-start-hook (v1.0.0)

**Purpose:** Creates and manages SessionStart hooks for Claude Code to ensure development environment is ready

**Triggers:**
- Keywords: `session start`, `session hook`, `startup hook`, `session configuration`, `claude code setup`, `environment setup`
- First-time repository setup for Claude Code
- Configuring Claude Code on the web

**What it does:**
1. Creates `.claude/.claude-settings.json` with SessionStart hook configuration
2. Generates `.claude/hooks/session-start.sh` script for environment checks
3. Verifies Python and development tools (pytest, ruff, pydocstyle)
4. Displays git status and current branch
5. Shows available skills and project configuration
6. Auto-installs dependencies if needed
7. Provides quick reminders about project guidelines

**When to use:**
- Setting up Claude Code for the first time
- Configuring automated environment setup
- Preparing repository for Claude Code web sessions
- Ensuring consistent development environment

**Example:**
```bash
# First-time setup
"Set up SessionStart hook for this repository"

# Web environment
"Configure SessionStart hook for Claude Code on the web"

# Update existing hook
"Add git diff stats to the SessionStart hook"

# Troubleshoot
"SessionStart hook is failing"
```

**Integration:**
Provides foundation for all other skills:
```
Session Starts
    ↓
session-start-hook: Environment ready ✅
    ↓
User makes code changes
    ↓
test-runner / doc-updater / security-checker run
    ↓
pr-helper creates PR
```

**Benefits:**
- ✅ Zero manual setup - session ready immediately
- ✅ Fast startup - completes in < 10 seconds
- ✅ Idempotent - safe to run multiple times
- ✅ Informative - provides useful context
- ✅ Auto-installs dependencies when needed
- ✅ Works in both local and web environments

**Typical workflow:**
```
Claude Code session starts
    ↓
SessionStart hook runs automatically
    ↓
Verifies tools and dependencies
    ↓
Displays project status
    ↓
Injects context into session
    ↓
Developer ready to work
```

**What the hook checks:**
- 📦 Python environment (version, pip)
- 🔧 Development tools (pytest, ruff, pydocstyle)
- 📊 Repository status (git status, current branch)
- ☁️ GCP configuration (project ID, available secrets)
- 🎯 Available skills (list of all skills)
- 💡 Quick reminders (security rules, testing, docs)

### 8. preflight-check (v1.0.0)

**Purpose:** Run all validation checks before creating PR to ensure auto-merge will succeed

**Triggers:**
- Keywords: `preflight`, `create pr`, `ready to merge`, `open pull request`
- Before PR creation (automatic integration with pr-helper)

**What it does:**
1. 🔒 **Security Check** - Scans git diff for secrets (API keys, tokens, passwords)
2. 🧪 **Tests** - Runs full test suite with `pytest tests/ -v`
3. 🎨 **Lint** - Runs `ruff check src/ tests/`
4. 📚 **Documentation** - Verifies changelog updated if src/ changed, runs pydocstyle

**When to use:**
- Before creating a PR (automatically integrated with pr-helper)
- Manual validation: "Run preflight checks"
- After fixing issues: "Check if everything passes now"

**Example:**
```bash
# Before creating PR (automatic)
"I'm ready to create a PR"  # Preflight runs automatically

# Manual preflight
"Run preflight checks"
```

**Integration:**
```
preflight-check (local) → All pass? → Create PR
    ↓
auto-merge.yml (GitHub) → Verify again → Auto-merge
    ↓
Merged + branch deleted (< 1 minute)
```

**Benefits:**
- ✅ Zero PR rejections due to validation failures
- ✅ < 1 minute from "create PR" to merge
- ✅ 100% of preflight passes result in auto-merge success
- ✅ Fast execution (< 30 seconds)

**Why run checks twice?**
- **Local (preflight):** Fast feedback, no CI wait
- **GitHub (auto-merge):** Security verification, final gate

### 9. performance-monitor (v1.0.0)

**Purpose:** Monitor CI/CD pipeline performance, identify bottlenecks, and provide actionable optimization recommendations

**Triggers:**
- Keywords: `performance`, `bottlenecks`, `workflow stats`, `slow ci`, `CI performance`
- After major changes: new dependencies, workflow modifications
- Periodic reviews: weekly/monthly performance check

**What it does:**
1. Collects workflow run data from GitHub API (last 7-30 days)
2. Calculates statistics per workflow (avg/min/max duration, success rate)
3. Analyzes step-level performance to identify slow steps
4. Identifies bottlenecks (workflows >30s avg, failing workflows)
5. Generates actionable optimization recommendations
6. Tracks trends over time to detect performance regressions

**When to use:**
- Weekly performance review: "How is CI performing this week?"
- Investigating slowness: "Why is CI so slow?"
- After dependency updates: detect regressions
- Before optimization work: get baseline metrics

**Example:**
```bash
# Weekly review
"How is CI performing this week?"

# Bottleneck investigation
"Why is CI so slow?"

# Trend detection
"Has CI gotten slower recently?"
```

**Integration:**
```
Developer requests performance review
    ↓
performance-monitor: Collect workflow data (GitHub API)
    ↓
Analyze: Workflows, jobs, steps
    ↓
Identify: Slow workflows (>30s), failing workflows
    ↓
Generate: Report with specific recommendations
    ↓
Developer implements optimizations
    ↓
performance-monitor: Measure impact
```

**Sample Output:**
```markdown
# 📊 CI/CD Performance Report

## Summary
- Total Runs: 42
- Total CI Time: 28.5 minutes
- Avg Success Rate: 95.2%

## 🐌 Slow Workflows
- **Tests**: 50.3s avg (regression from 30s)
- **Deploy Documentation**: 78.2s avg

## 💡 Recommendations
- Tests: Enable pytest-xdist for parallel execution
- Deploy: Consider faster deployment service
```

**Benefits:**
- ✅ Data-driven optimization (no guessing)
- ✅ Detect regressions within 1 day
- ✅ Specific, actionable recommendations
- ✅ Track optimization impact
- ✅ Understand CI costs (time = money)

**Success Metrics:**
- Accurate performance metrics collected
- Bottlenecks clearly identified
- Actionable recommendations provided
- Regressions detected quickly

### 10. cost-optimizer (v1.0.0)

**Purpose:** Monitor Claude API usage, calculate costs, identify expensive operations, and provide optimization recommendations to reduce spending

**Triggers:**
- Keywords: `costs`, `spending`, `API costs`, `reduce costs`, `budget`
- Monthly/weekly cost review
- After high-usage events: skills deployment, large PRs
- Budget alerts: approaching spending limits

**What it does:**
1. Collects Claude API usage data (tokens, model, operations)
2. Calculates costs based on 2026 pricing (Sonnet/Opus/Haiku rates)
3. Identifies expensive operations (high-cost API calls)
4. Detects cost anomalies (unusual spending spikes)
5. Generates optimization recommendations (model selection, context size)
6. Tracks spending trends and projects monthly costs

**When to use:**
- Monthly cost review: "What did I spend on Claude API this month?"
- After major work: "How much did that documentation generation cost?"
- Budget planning: "What will this cost monthly?"
- Cost optimization: "How can I reduce my API costs?"

**Example:**
```bash
# Monthly review
"What did I spend on Claude API this month?"

# Optimization
"How can I reduce my Claude API costs?"

# Budget check
"Am I staying within budget?"
```

**Claude API Pricing (2026):**
| Model | Input | Output | Best For |
|-------|-------|--------|----------|
| Haiku 3.5 | $0.25/MTok | $1.25/MTok | Simple tasks, search |
| Sonnet 4.5 | $3.00/MTok | $15.00/MTok | Balanced, default |
| Opus 4.5 | $15.00/MTok | $75.00/MTok | Complex reasoning |

**Cost Ratio:** Opus is 60x more expensive than Haiku for output tokens.

**Integration:**
```
High-usage event occurs (docs generation)
    ↓
cost-optimizer: Track API calls and tokens
    ↓
Calculate: Costs per operation/category
    ↓
Analyze: Expensive operations, trends
    ↓
Generate: Report with optimization recommendations
    ↓
Developer implements: Use Haiku for research, reduce context
    ↓
cost-optimizer: Measure savings
```

**Sample Output:**
```markdown
# 💰 Claude API Cost Report

## Summary
- Total Cost: $68.25
- Period: Last 30 days
- Daily Average: $2.28

## Cost Breakdown
| Category | Cost | % |
|----------|------|---|
| Code Generation | $40.95 | 60% |
| Research | $20.48 | 30% |
| Documentation | $6.82 | 10% |

## 💡 High Priority Recommendations
**Model Selection** - Using Sonnet for all operations
- Use Haiku for Explore agent tasks
- Potential Savings: $15-20/month (70% on research costs)

**Context Optimization** - Average context: 120K tokens
- Enable automatic summarization
- Potential Savings: 40-60% input costs
```

**Benefits:**
- ✅ Accurate cost tracking and reporting
- ✅ Identify expensive operations
- ✅ Measurable cost reductions (20-50%)
- ✅ Budget alerts prevent overspending
- ✅ Smart model selection guidance

**Success Metrics:**
- 20-50% cost reduction after optimizations
- No quality degradation
- Budget compliance (no surprises)
- Clear, actionable recommendations

**Critical Optimizations:**
1. **Model Selection:** Use Haiku for simple tasks (60x cheaper than Opus)
2. **Context Size:** Minimize tokens without sacrificing quality
3. **Caching:** Avoid re-reading same files
4. **Batching:** Group related operations

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
- ✅ changelog-updater skill - Generates changelog entries from git commits
- ✅ session-start-hook skill - SessionStart hooks for environment setup

### Future (v2.0.0+)
- Feature scaffolding (generate boilerplate from templates)
- Safe refactoring (with automated test loop)
- Code review assistant (automated PR review)
- Performance profiler (identify bottlenecks)

---

**Questions?** Check `/docs/research/07_claude_skills_enterprise_implementation.summary.md` for detailed patterns and architecture decisions.
