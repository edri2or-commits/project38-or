# Bootstrap Plan: Project38-OR

## Current State (2026-01-09)

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

### ✅ Completed (2026-01-10)
- [x] Harden workflows
- [x] Create research summaries
- [x] Write BOOTSTRAP_PLAN.md
- [x] Create CLAUDE.md with project context
- [x] Implement agent-dev workflow
- [x] Add testing framework (pytest with 100% coverage)
- [x] Build autonomous skills (doc-updater, test-runner, security-checker, pr-helper)
- [x] Create CI/CD workflows (test, lint, docs-check)
- [x] Document GitHub MCP Server setup
- [x] **Plan WIF migration** (documented in `docs/wif-migration-plan.md`)
- [x] **Plan Branch Protection** (documented in `docs/manual-setup-guide.md`)
- [x] **Plan GitHub Environment** (documented in `docs/manual-setup-guide.md`)

### 🔄 Pending Manual Execution (Requires Admin Access)

These tasks are **planned and documented**, but require **human execution** with GitHub Admin and GCP Owner permissions:

1. **GitHub Branch Protection** (5 min)
   - Follow: `docs/manual-setup-guide.md` Section 1
   - Requires: GitHub Admin access
   - Impact: Prevents direct pushes to main

2. **GitHub Environment "Production"** (5 min)
   - Follow: `docs/manual-setup-guide.md` Section 2
   - Requires: GitHub Admin access
   - Impact: Enables deployment approval gates

3. **WIF Migration** (75 min)
   - Follow: `docs/wif-migration-plan.md`
   - Requires: GCP Owner/Admin access
   - Impact: Eliminates static Service Account keys
   - Risk: Low (rollback plan documented)

### 📋 Future Sessions

1. **Execute WIF Migration** (after gaining GCP access)
   - Run Phase 1 commands from `docs/wif-migration-plan.md`
   - Claude Code can handle Phase 2-4 (workflow updates, testing, cleanup)

2. **Implement Railway Deployment Pipeline**
   - Create `deploy-railway.yml` workflow
   - Use "Production" environment for approval gate
   - Document Railway-specific secrets strategy

3. **Enhance Skills System**
   - Add `changelog-updater` skill (auto-update changelog on commits)
   - Add `dependency-checker` skill (audit npm/pip dependencies)
   - Add `performance-monitor` skill (track workflow execution times)

4. **Advanced CI/CD**
   - Implement preview deployments for PRs
   - Add integration tests with test database
   - Set up monitoring/alerting for production

---

## Success Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Secrets in GitHub Secrets | 1 (bootstrap only) | 1 | ✅ Target met |
| Workflows with explicit permissions | 100% | 100% | ✅ Target met |
| Push triggers in workflows | 0 | 0 | ✅ Target met |
| PRs auto-deployed without review | 0 | 0 | ✅ Target met |
| Test coverage | >80% | **100%** | ✅ Exceeded target |
| Autonomous Skills | 3+ | **4** | ✅ Exceeded target |
| Documentation coverage | 100% | **100%** | ✅ Target met |
| Branch protection enabled | Yes | **Pending** | ⏳ Requires manual setup |
| GitHub Environment configured | Yes | **Pending** | ⏳ Requires manual setup |
| WIF migration completed | Yes | **Pending** | ⏳ Requires GCP access |
