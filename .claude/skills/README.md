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

### Current (MVP)
- ✅ doc-updater skill (completed)

### Planned
- 🔄 test-runner skill (run tests before commit)
- 🔄 security-checker skill (validate no secrets in commits)
- 🔄 pr-helper skill (standardized PR creation)

### Future
- Feature scaffolding (generate boilerplate)
- Safe refactoring (with test loop)
- Dependency updater (with security checks)

---

**Questions?** Check `/docs/research/07_claude_skills_enterprise_implementation.summary.md` for detailed patterns and architecture decisions.
