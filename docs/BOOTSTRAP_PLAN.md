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

## Phase 3: Agent Platform Foundation

**Goal**: Build core infrastructure for autonomous agent creation and orchestration system that enables users to create AI agents through natural language chat interface.

### 3.1 Vision Statement

**Target Capability**: User says "צור לי סוכן שעוקב אחרי מניות" → System automatically generates, tests, validates, and deploys a working agent that monitors stocks 24/7 and sends notifications.

**Architecture Transformation**:
- **From**: Secret management + CI/CD system
- **To**: Full AI agent platform with autonomous agent factory

### 3.2 Research Integration

This phase is built on 3 comprehensive research documents:

#### Research Document 1: Ralph Wiggum Framework
**Source**: `research/claude-code-ralph-wiggum-framework.md`

**Key Concepts**:
- Ralph Loop: Recursive execution until validation passes (`<promise>DONE</promise>`)
- Stop Hook intercepts Claude Code session end
- Automatic retry with TDD (Test-Driven Development)
- Docker Sandbox for safety
- Cost: ~$2.25 per feature (30 iterations average)

**Usage in Platform**:
- Agent Factory code generation
- Automatic validation and testing
- Cost-effective iterative development

#### Research Document 2: Long-Running Agent Harness
**Source**: `research/long-running-agent-harness.md`

**Key Concepts**:
- Dual-Agent Pattern: Initializer Agent (setup) + Worker Agent (execution)
- Handoff Artifacts: Structured context transfer between sessions
- Context Saturation Solution: Execute → Summarize → Reset loop
- 24/7 orchestration with Linear/Git integration
- State storage strategy: Linear (global), Git (code), JSON (session)

**Usage in Platform**:
- Agent Orchestrator implementation
- Context management for long-running agents
- Task scheduling and execution

#### Research Document 3: Hybrid Browser Agent Architecture
**Source**: `research/hybrid-browser-agent-architecture.md`

**Key Concepts**:
- MCP (Model Context Protocol) as central communication layer
- Hybrid approach: DOM/Accessibility Tree (cheap) + Computer Use API (expensive)
- Docker isolation for browser automation
- HumanLayer (HITL) for critical approvals
- Cost: DOM ~$0.0015/step, Computer Use ~$0.005/step

**Usage in Platform**:
- MCP Tools implementation
- Browser automation for SaaS interactions
- Future feature for web-based agents

### 3.3 System Architecture

```
┌─────────────────────────────────────────────┐
│          User Interface (Chat)              │
│     "צור לי סוכן שעוקב אחרי מניות"          │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│       Agent Factory (NL → Code)             │
│  - Natural Language Parser                  │
│  - Code Generator (Ralph Loop)              │
│  - Validator (pytest + linter)              │
│  - Template Library                         │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│      Agent Registry (PostgreSQL)            │
│  - Agent metadata and code                  │
│  - Task definitions and schedules           │
│  - Execution history and logs               │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│      Agent Harness (Orchestrator)           │
│  - 24/7 execution loop                      │
│  - Context management (Handoff)             │
│  - Docker sandbox isolation                 │
│  - Task scheduler (cron-like)               │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│         Action Layer (MCP Tools)            │
│  - Browser automation (Puppeteer)           │
│  - File operations (local data)             │
│  - API calls (external services)            │
│  - Notifications (Telegram, Email)          │
│  - Secrets (GCP Secret Manager - existing)  │
└─────────────────────────────────────────────┘
```

### 3.4 Implementation Phases

#### Phase 3.1: Core Infrastructure (Week 1-2)
**Goal**: Establish FastAPI + PostgreSQL foundation for agent storage

- [ ] Create `src/api/` module structure
  - `main.py` - FastAPI application entry point
  - `database.py` - PostgreSQL connection with asyncpg
  - `routes/health.py` - Health check endpoint
- [ ] Create `src/models/` for database schemas
  - `agent.py` - Agent entity (SQLModel)
  - `task.py` - Task entity (SQLModel)
- [ ] Set up PostgreSQL on Railway
  - Database creation and connection string
  - Environment variable configuration
- [ ] Create basic CRUD endpoints
  - `POST /agents` - Create agent
  - `GET /agents/{id}` - Retrieve agent
  - `GET /agents` - List all agents
- [ ] Add integration tests for API endpoints
- [ ] Update requirements.txt with FastAPI, SQLModel, asyncpg

**Success Criteria**:
- FastAPI server runs successfully
- Database connection established
- All CRUD operations functional
- Test coverage > 80%

#### Phase 3.2: Agent Factory (Week 3-4)
**Goal**: Implement Natural Language → Agent Code generation

- [ ] Create `src/factory/` module
  - `nl_parser.py` - Parse natural language requests
  - `code_generator.py` - Generate Python agent code
  - `validator.py` - Validate generated code (pytest + ruff)
  - `templates/` - Pre-built agent templates
- [ ] Implement Ralph Loop integration
  - Stop Hook for validation
  - Iterative generation until tests pass
  - Cost tracking and limits
- [ ] Create agent template library
  - `monitoring_agent.py` - Data monitoring template
  - `notification_agent.py` - Alert sending template
  - `data_agent.py` - Data fetching template
- [ ] Add `POST /agents/generate` endpoint
  - Accept natural language input
  - Return generated agent code
  - Store in database

**Success Criteria**:
- Natural language parsed correctly (>70% accuracy)
- Generated code passes validation
- Ralph Loop completes within budget (<$5/agent)
- Template library covers 3+ use cases

#### Phase 3.3: Agent Harness (Week 5-6)
**Goal**: 24/7 orchestration with context management

- [ ] Create `src/harness/` module
  - `orchestrator.py` - Main execution loop
  - `scheduler.py` - Cron-like task scheduling
  - `handoff.py` - Context transfer implementation
  - `docker_sandbox.py` - Docker container management
- [ ] Implement Handoff Artifact system
  - Structured context (Markdown/XML)
  - State persistence (harness_state.json)
  - Git integration for code versioning
- [ ] Set up Docker isolation
  - Agent execution in containers
  - Volume mounts for workspace
  - Network restrictions
- [ ] Add monitoring and logging
  - Agent execution status
  - Error tracking
  - Performance metrics

**Success Criteria**:
- Agents run continuously (>99% uptime)
- Context preserved across restarts
- Docker isolation functional
- Error recovery mechanisms work

#### Phase 3.4: MCP Tools (Week 7-8)
**Goal**: Provide agents with external interaction capabilities

- [ ] Create `src/mcp/` module for MCP servers
  - `browser_server.py` - Web automation (Puppeteer)
  - `filesystem_server.py` - File operations
  - `notifications_server.py` - Telegram/Email alerts
- [ ] Integrate existing GCP Secret Manager
  - `secrets_server.py` - Wrap existing secrets_manager.py
- [ ] Implement MCP protocol (stdio transport)
- [ ] Add tool documentation and examples
- [ ] Security review for MCP tools

**Success Criteria**:
- All MCP tools functional
- Agents can use tools successfully
- Security review passed
- Documentation complete

### 3.5 Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **API Framework** | FastAPI | Async support, auto-docs, Pydantic integration |
| **Database** | PostgreSQL | Reliability, Railway compatibility, relational data |
| **ORM** | SQLModel | Pydantic + SQLAlchemy, type safety |
| **DB Driver** | asyncpg | Fastest async PostgreSQL driver |
| **Agent Execution** | Docker | Isolation, security, reproducibility |
| **MCP Protocol** | stdio transport | Simple, secure, local communication |
| **Code Generation** | Claude 3.5 Sonnet | Best for code tasks ($3/1M input, $15/1M output) |
| **Browser Automation** | Puppeteer | Standard, well-documented |
| **Task Queue** | In-memory (Phase 3) | Simplicity, add Redis/Celery later |
| **Deployment** | Railway | Existing infrastructure, PostgreSQL support |

### 3.6 Cost Projection

| Item | Monthly Cost | Notes |
|------|-------------|-------|
| Railway PostgreSQL | $5-10 | Hobby tier, scales with usage |
| Railway API hosting | $5-10 | Hobby tier |
| Claude API usage | $10-30 | ~10-50 agent generations/month |
| GCP Secret Manager | $0.06 | Existing, minimal additional cost |
| Linear (Optional) | $0 | Not required in Phase 3 |
| **Total Estimated** | **$25-60** | Scales with actual usage |

**Cost Controls**:
- Per-agent generation budget ($5 max)
- Monthly spending limits
- Usage monitoring dashboard
- Automatic alerts at 80% budget

### 3.7 Security Considerations

| Risk | Mitigation |
|------|-----------|
| **Generated code malicious** | Validator scans for dangerous patterns, Docker isolation |
| **Agent data leakage** | PostgreSQL with encryption, secrets in GCP only |
| **Unauthorized API access** | Authentication required, rate limiting |
| **Container escape** | Minimal Docker image, no privileged mode |
| **Secret exposure** | Existing GCP Secret Manager, never in logs |

### 3.8 Success Metrics

| Metric | Target | Why |
|--------|--------|-----|
| Agent creation time | < 2 min | User experience |
| Agent generation success rate | > 80% | Factory effectiveness |
| Average cost per agent | < $5 | Sustainability |
| Agent uptime | > 99% | Reliability |
| API response time | < 200ms | Performance |
| Test coverage | > 80% | Code quality |

### 3.9 Prioritized Tasks

| Priority | Task | Size | Dependencies |
|----------|------|------|--------------|
| P0 | FastAPI + PostgreSQL setup | M | None |
| P0 | Agent/Task SQLModel schemas | S | PostgreSQL |
| P1 | Agent Factory NL parser | M | FastAPI |
| P1 | Ralph Loop integration | L | Factory |
| P2 | Agent Harness orchestrator | L | Factory, Docker |
| P2 | Handoff Artifacts | M | Harness |
| P3 | MCP Tools (browser) | M | Harness |
| P3 | Linear integration | L | Optional, future |

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
