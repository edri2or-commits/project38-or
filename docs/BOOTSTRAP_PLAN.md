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

### Immediate (This Session)
- [x] Harden workflows (PR #2)
- [x] Create research summaries
- [x] Write BOOTSTRAP_PLAN.md

### Next Session
1. Create CLAUDE.md with project context
2. Set up GitHub Environment "Production"
3. Add branch protection rules
4. Consider WIF migration (requires your GCP project access)

### Future Sessions
1. Implement agent-dev workflow
2. Add testing framework
3. Build first autonomous skill (doc-updater)
4. Implement Railway deployment pipeline

---

## Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Secrets in GitHub Secrets | 1 (bootstrap only) | 1 |
| Workflows with explicit permissions | 100% | 100% |
| Push triggers in workflows | 0 | 0 |
| PRs auto-deployed without review | 0 | 0 |
| Test coverage | >80% | 0% |
