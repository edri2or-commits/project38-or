# Bootstrap Plan: Project38-OR

## Current State (2026-01-11)

**Completed:**
- GCP Secret Manager integration with Service Account
- 7 secrets accessible: ANTHROPIC-API, GEMINI-API, N8N-API, OPENAI-API, RAILWAY-API, TELEGRAM-BOT-TOKEN, github-app-private-key
- 4 GitHub Actions workflows (hardened with minimal permissions)
- Python secrets_manager module for runtime fetch
- PR #1 merged into main

---

## Phase 1: Foundation Hardening

**Goal**: Establish secure, maintainable infrastructure for autonomous agent operation.

### 1.1 Secret Strategy: CI vs Runtime

| Context | Secret Source | Mechanism |
|---------|---------------|-----------|
| **CI (GitHub Actions)** | GCP Secret Manager | Fetched via `google-github-actions/auth` with static SA key |
| **Runtime (Railway)** | GCP Secret Manager | Bootstrap key in Railway env → fetch others into memory |

**The "Secret Zero" Reality:**
- We currently store `GCP_SERVICE_ACCOUNT_KEY` in GitHub Secrets (long-lived)
- This is acceptable for Phase 1, but should migrate to WIF in Phase 2
- Railway has no native WIF support, so bootstrap key pattern is required

**Current Flow:**
```
GitHub Secrets (SA Key) → Auth to GCP → Fetch runtime secrets → Inject to Railway
```

**Target Flow (Phase 2):**
```
GitHub OIDC → WIF → GCP Auth → Fetch secrets → Inject to Railway
```

### 1.2 Prioritized Tasks

| Priority | Task | Size | Value |
|----------|------|------|-------|
| P0 | Add branch protection rules for main | XS | Prevent accidental pushes |
| P1 | Create CLAUDE.md with project context | S | Agent understands codebase |
| P2 | Add basic Python linting (ruff) to CI | S | Code quality baseline |
| P3 | Create requirements.txt lockfile | XS | Reproducible builds |

---

## Phase 2: Autonomous Agent Infrastructure

**Goal**: Enable Claude Code to operate safely as an autonomous contributor.

### 2.1 Agent Workflow Setup

1. **Create `agent-dev.yml` workflow:**
   - Triggered by issue comments (`/claude <task>`)
   - Runs in sandboxed feature branch
   - Creates PR for human review

2. **Human Approval Gate:**
   - GitHub Environment "Production" with required reviewers
   - Agent PRs require human merge

3. **CLAUDE.md Constitution:**
   - Never commit secrets
   - Always run tests before commit
   - Use `src/secrets_manager.py` for all API access
   - Prefer edit over rewrite

### 2.2 Prioritized Tasks

| Priority | Task | Size | Value |
|----------|------|------|-------|
| P0 | Create GitHub Environment "Production" | XS | Human gate for deploys |
| P1 | Write comprehensive CLAUDE.md | M | Agent operating context |
| P2 | Implement WIF for GitHub Actions | M | Eliminate static SA key |
| P3 | Add test framework (pytest) | S | Verification capability |
| P4 | Create agent-dev workflow | M | Autonomous issue handling |

---

## Governance Model

### Autonomous (No Approval Needed)

Claude Code agent can autonomously:
- Read any file in the repository
- Run tests and linters
- Create/update feature branches (not main)
- Open/update Pull Requests
- Add comments to issues
- Generate documentation

### Requires Human Approval

The following always require explicit human approval:

| Action | Approval Mechanism |
|--------|-------------------|
| Merge to main | PR review |
| Deploy to Railway | GitHub Environment gate |
| Modify workflows | PR review |
| Change IAM/permissions | Ask first + manual execution |
| Create/rotate secrets | Ask first + manual execution |
| Add dependencies | Propose in PR, human reviews |
| Modify SECURITY.md | PR review |

### Dangerous Actions (Ask First, Wait for Explicit Approval)

- Any GCP IAM changes
- Any WIF configuration changes
- Any secret creation/deletion/rotation
- Any Railway project/environment changes
- Any workflow changes that increase permissions or broaden triggers
- Adding new pip/npm dependencies

---

## Secret Management Strategy

### Current Secrets Inventory

| Secret Name | Purpose | Used In |
|-------------|---------|---------|
| ANTHROPIC-API | Claude API access | Agent runtime |
| GEMINI-API | Google Gemini access | Future use |
| N8N-API | n8n workflow automation | Notifications |
| OPENAI-API | OpenAI API access | Future use |
| RAILWAY-API | Railway deployment | CI/CD |
| TELEGRAM-BOT-TOKEN | Telegram notifications | Alerts |
| github-app-private-key | GitHub App auth | Future: higher rate limits |
| GCP_SERVICE_ACCOUNT_KEY | Bootstrap (GitHub Secret) | CI auth to GCP |

### Rotation Strategy

1. **Routine Rotation (Quarterly):**
   - Rotate API keys via provider dashboards
   - Update in GCP Secret Manager
   - Railway apps auto-fetch on restart

2. **Emergency Rotation:**
   - Revoke immediately at provider
   - Update in GCP Secret Manager
   - Force Railway service restart

### Access Principle

- **Least Privilege**: Each workflow/service gets only needed secrets
- **No Logging**: Secrets never printed to logs
- **Memory Only**: Runtime fetches to RAM, not disk

---

## Architecture Decisions Summary

Based on research analysis:

| Decision | Rationale | Source |
|----------|-----------|--------|
| MkDocs + Material for docs | FastAPI ecosystem alignment | Research 01 |
| SQLModel + asyncpg | Pydantic integration, Railway compatibility | Research 02 |
| Hooks for agent control | Deterministic security gates | Research 03 |
| PostgreSQL as backbone | Simplicity over Redis/RabbitMQ | Research 04 |
| WIF over static keys | Ephemeral credentials | Research 05 |
| GitHub App for automation | Higher rate limits, audit trail | Research 06 |
| Skills for standardization | Version-controlled agent behaviors | Research 07 |

---

## Next Actions (Ordered)

### ✅ Completed (2026-01-11)

**Phase 1: Foundation & Security (2026-01-10)**
- [x] Harden workflows
- [x] Create research summaries
- [x] Write BOOTSTRAP_PLAN.md
- [x] Create CLAUDE.md with project context
- [x] Implement agent-dev workflow
- [x] Add testing framework (pytest with 100% coverage)
- [x] Build autonomous skills (doc-updater, test-runner, security-checker, pr-helper)
- [x] Create CI/CD workflows (test, lint, docs-check)
- [x] Document GitHub MCP Server setup

**Phase 2: WIF Migration & GitHub Admin (2026-01-11)**
- [x] **GitHub Branch Protection configured** - Rules active on main branch
  - Required status checks: test, lint, docs-check
  - Required PR reviews: 1 approval
  - Conversation resolution required
  - Force pushes blocked
- [x] **GitHub Environment "Production" created** - Deployment approval gates enabled
  - Protected branches only policy
  - Environment ID: 11168582234
- [x] **WIF Setup completed in GCP** - Workload Identity Federation active
  - Pool: `github-pool`
  - Provider: `github-provider`
  - Project: 979429709900
  - Resource: `projects/979429709900/locations/global/workloadIdentityPools/github-pool/providers/github-provider`
- [x] **All GCP workflows migrated to WIF** - 5 workflows updated
  - verify-secrets.yml, gcp-secret-manager.yml, quick-check.yml
  - report-secrets.yml, test-wif.yml
- [x] **WIF tested and verified** - 2 successful workflow runs
  - Workflow run 20894119675: ✅ success
  - Workflow run (main branch): ✅ success
- [x] **Static credentials eliminated** - GCP_SERVICE_ACCOUNT_KEY deleted from GitHub Secrets
- [x] **Documentation updated** - CLAUDE.md, changelog.md reflect WIF migration

**Skills Enhancement (2026-01-11)**
- [x] **dependency-checker skill (v1.0.0)** - Audits Python dependencies for security vulnerabilities
  - Scans for known CVEs using pip-audit
  - Identifies outdated packages
  - Validates requirements.txt format and version pinning
  - Blocks deployment on CRITICAL/HIGH vulnerabilities
  - Location: `.claude/skills/dependency-checker/SKILL.md`
- [x] **changelog-updater skill (v1.0.0)** - Automatically generates changelog entries from git commits
  - Analyzes git commit history using conventional commits
  - Categorizes changes (Added/Changed/Fixed/Security)
  - Updates `docs/changelog.md` under [Unreleased]
  - Reduces manual changelog maintenance
  - Location: `.claude/skills/changelog-updater/SKILL.md`
- [x] **session-start-hook skill (v1.0.0)** - Creates SessionStart hooks for Claude Code environment setup
  - Generates `.claude/.claude-settings.json` configuration
  - Creates `.claude/hooks/session-start.sh` for automated checks
  - Verifies Python tools (pytest, ruff, pydocstyle)
  - Displays git status and project context on session start
  - Fast startup (< 10 seconds), works in local and web environments
  - Location: `.claude/skills/session-start-hook/SKILL.md`

### 📋 Future Enhancements

1. **Implement Railway Deployment Pipeline**
   - Create `deploy-railway.yml` workflow
   - Use "Production" environment for approval gate
   - Document Railway-specific secrets strategy

2. **Enhance Skills System**
   - Add `performance-monitor` skill (track workflow execution times)
   - Expand skill library based on development patterns

3. **Advanced CI/CD**
   - Implement preview deployments for PRs
   - Add integration tests with test database
   - Set up monitoring/alerting for production

---

## Success Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Secrets in GitHub Secrets | 1 (bootstrap only) | **0** | ✅ **Exceeded** (WIF eliminates secrets) |
| Workflows with explicit permissions | 100% | 100% | ✅ Target met |
| Push triggers in workflows | 0 (except docs) | **1** (docs.yml only) | ✅ **Acceptable** (low-risk documentation deployment) |
| PRs auto-deployed without review | 0 | 0 | ✅ Target met |
| Test coverage | >80% | **100%** | ✅ Exceeded target |
| Autonomous Skills | 3+ | **7** | ✅ Exceeded target |
| Documentation coverage | 100% | **100%** | ✅ Target met |
| Branch protection enabled | Yes | **Active** | ✅ **Completed** (2026-01-11) |
| GitHub Environment configured | Yes | **Production** | ✅ **Completed** (2026-01-11) |
| WIF migration completed | Yes | **Active** | ✅ **Completed** (2026-01-11) |
| Static credentials eliminated | Yes | **Deleted** | ✅ **Completed** (2026-01-11) |
