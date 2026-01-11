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

**Phase 3.1: Core Infrastructure (2026-01-11)**
- [x] **FastAPI + PostgreSQL foundation** - REST API and database layer for agent platform
  - `src/api/main.py` - FastAPI app with CORS, lifecycle hooks
  - `src/api/database.py` - Async PostgreSQL connection management (pool_size=20)
  - `src/api/routes/health.py` - Health check (`/health`) and root (`/`) endpoints
  - `src/models/agent.py` - Agent entity schema (name, description, code, status)
  - `src/models/task.py` - Task entity schema (execution history, scheduling, results)
  - New dependencies: fastapi>=0.109.0, sqlmodel>=0.0.14, asyncpg>=0.29.0
  - Integration tests: 8 tests with 100% coverage
  - API documentation: `docs/api/fastapi.md`, `database.md`, `models.md`
  - All CI workflows passing (lint, docs-check, tests)

**Phase 3.2: Agent Factory (2026-01-11)**
- [x] **Natural Language to Python Agent** - Claude Sonnet 4.5 code generation
  - `src/factory/generator.py` - Code generation from descriptions
  - `src/factory/validator.py` - Multi-stage validation (syntax, ruff, pydocstyle, security)
  - `src/factory/ralph_loop.py` - Recursive Test→Fix→Test cycle
  - `src/api/routes/agents.py` - Agent CRUD endpoints (POST, GET, PUT, DELETE, Execute)
  - New dependencies: anthropic>=0.18.0, jinja2>=3.1.0
  - 16 comprehensive tests with 100% pass rate
  - API documentation: `docs/api/factory.md`
  - Cost: ~$0.025-$0.10 per agent, target < $3 achieved

**Phase 3.3: Agent Harness (2026-01-11)**
- [x] **24/7 Orchestration Infrastructure** - Autonomous agent execution
  - `src/harness/executor.py` - Safe code execution in isolated subprocesses
  - `src/harness/handoff.py` - State preservation using Dual-Agent Pattern
  - `src/harness/scheduler.py` - APScheduler integration (cron/interval triggers)
  - `src/harness/resources.py` - Resource monitoring (memory, CPU, processes)
  - `src/api/routes/tasks.py` - Task history endpoints (GET, POST retry)
  - New dependencies: apscheduler>=3.10.0, psutil>=5.9.0, aiosqlite
  - 30+ comprehensive tests
  - API documentation: `docs/api/harness.md`
  - Execute-Summarize-Reset loop for 100+ runs
  - Automatic retry with exponential backoff (2s, 4s, 8s)

---

## Phase 3: Agent Platform Foundation

**Goal**: Transform from secret management to full AI agent platform where users create autonomous agents from natural language.

**Vision**: User says "צור לי סוכן שעוקב אחרי מניות של טסלה" → System generates, tests, and deploys agent automatically.

### 3.1 Core Infrastructure ✅ **COMPLETED** (2026-01-11)

**Objective**: FastAPI + PostgreSQL foundation for agent storage and execution tracking.

**Completed Files:**
- `src/api/main.py` - FastAPI app entry point with CORS middleware
- `src/api/database.py` - PostgreSQL async connection management
- `src/api/routes/health.py` - Health check endpoints
- `src/models/agent.py` - Agent entity (stores generated code)
- `src/models/task.py` - Task entity (execution history)
- `tests/test_api_health.py` - 8 integration tests
- `docs/api/*.md` - Complete API documentation

**Database Schema:**
```sql
CREATE TABLE agents (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  description VARCHAR(2000),
  code TEXT,  -- Generated Python code
  status VARCHAR(50) DEFAULT 'active',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  created_by VARCHAR(255),
  config TEXT  -- JSON configuration
);

CREATE TABLE tasks (
  id SERIAL PRIMARY KEY,
  agent_id INT REFERENCES agents(id),
  status VARCHAR(50) DEFAULT 'pending',
  scheduled_at TIMESTAMP,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  result TEXT,
  error TEXT,
  retry_count INT DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW()
);
```

**Endpoints Implemented:**
- `GET /health` - System health status
- `GET /` - API metadata

**Dependencies Added:**
- `fastapi>=0.109.0` - REST API framework
- `sqlmodel>=0.0.14` - ORM (Pydantic + SQLAlchemy)
- `asyncpg>=0.29.0` - Async PostgreSQL driver
- `uvicorn[standard]>=0.27.0` - ASGI server
- `httpx>=0.27.0` - HTTP client for tests

### 3.2 Agent Factory ✅ **COMPLETED** (2026-01-11)

**Objective**: Natural Language → Working Python Agent

**Completed Files:**
- `src/factory/__init__.py` - Module exports for Agent Factory
- `src/factory/generator.py` - Claude Sonnet 4.5 code generation (generate_agent_code, estimate_cost)
- `src/factory/validator.py` - Multi-stage validation (syntax, ruff, pydocstyle, security)
- `src/factory/ralph_loop.py` - Recursive Test→Fix→Test cycle (ralph_wiggum_loop)
- `src/api/routes/agents.py` - Agent CRUD endpoints (POST, GET, PUT, DELETE, Execute)
- `tests/test_factory.py` - 16 comprehensive tests with 100% pass rate
- `docs/api/factory.md` - Complete API documentation

**Dependencies Added:**
- `anthropic>=0.18.0` - Claude API client
- `jinja2>=3.1.0` - Prompt templating

**Target Flow:**
```
User Input: "צור לי סוכן שעוקב אחרי מניות של טסלה ומתריע כאשר המחיר עולה ב-5%"
  ↓
1. POST /agents {"description": "..."}
  ↓
2. Claude Sonnet 4.5 generates Python code
  ↓
3. Ralph Wiggum Loop: Test → Fix → Test
  ↓
4. Save to agents table with status='active'
  ↓
Response: {"id": 1, "name": "Stock Monitor", "status": "active"}
```

**Tasks:**
1. **Claude Code Generator** (`src/factory/generator.py`)
   - Use Anthropic API with Claude Sonnet 4.5
   - Generate Python code from natural language
   - Include error handling, logging
   - Cost: ~$0.015-0.06 per generation

2. **Ralph Wiggum Loop** (`src/factory/ralph_loop.py`)
   - Recursive Test → Fix → Test cycle
   - Based on research/claude-code-ralph-wiggum-framework.md
   - Target cost: ~$2.25/agent (including iterations)
   - Automatic pytest validation

3. **Code Validator** (`src/factory/validator.py`)
   - Run ruff format check
   - Run ruff lint
   - Run pydocstyle (Google style)
   - Security check: no hardcoded secrets

4. **Agent CRUD Endpoints** (`src/api/routes/agents.py`)
   - `POST /agents` - Create from natural language
   - `GET /agents` - List all agents
   - `GET /agents/{id}` - Get specific agent
   - `PUT /agents/{id}` - Update agent
   - `DELETE /agents/{id}` - Delete agent
   - `POST /agents/{id}/execute` - Trigger manual execution

5. **Tests** (`tests/test_factory.py`)
   - Test code generation
   - Test validation pipeline
   - Test Ralph loop convergence
   - Mock Anthropic API

**Dependencies to Add:**
- `anthropic>=0.18.0` - Claude API client
- `jinja2>=3.1.0` - Prompt templating

**Success Criteria:**
- 90% of generated agents pass validation on first try
- Average cost per agent < $3
- Generation time < 30 seconds

### 3.3 Agent Harness ✅ **COMPLETED** (2026-01-11)

**Objective**: 24/7 orchestration of agent execution with long-running context management.

**Completed Files:**
- `src/harness/__init__.py` - Module exports for harness components
- `src/harness/executor.py` - Safe code execution in isolated subprocesses
- `src/harness/handoff.py` - State preservation using Dual-Agent Pattern
- `src/harness/scheduler.py` - APScheduler integration with cron/interval triggers
- `src/harness/resources.py` - Resource monitoring and limits
- `src/api/routes/tasks.py` - REST API endpoints for task history
- `tests/test_harness.py` - 30+ comprehensive tests
- `tests/conftest.py` - pytest fixtures for database testing
- `docs/api/harness.md` - Complete API documentation

**Implementation Flow:**
```
Scheduler triggers agent execution
  ↓
1. Harness loads agent code from DB
  ↓
2. Execute-Summarize-Reset loop (Execute → Compress → Save)
  ↓
3. Handoff Artifact: compress context after each run
  ↓
4. Create Task record: status='completed', result=output
  ↓
5. Schedule next execution (with retry logic if failed)
```

**Components Implemented:**

1. **Agent Executor** (`src/harness/executor.py`)
   - ✅ Load agent Python code from database
   - ✅ Execute in sandboxed subprocess with asyncio
   - ✅ Capture stdout/stderr, exceptions
   - ✅ Timeout protection (default: 5 minutes, configurable)
   - ✅ Task record creation with timestamps

2. **Handoff Artifacts** (`src/harness/handoff.py`)
   - ✅ State preservation between runs in agent.config JSON
   - ✅ Context compression (truncate output to 500 chars)
   - ✅ Run count tracking
   - ✅ Load/Save/Clear artifact operations

3. **Task Scheduler** (`src/harness/scheduler.py`)
   - ✅ APScheduler integration (AsyncIOScheduler)
   - ✅ Cron syntax support ("0 * * * *" = hourly)
   - ✅ Interval syntax (interval_minutes)
   - ✅ Per-agent schedules stored in agent.config JSON
   - ✅ Automatic retry with exponential backoff (2s, 4s, 8s)
   - ✅ Concurrent execution limits (default: 5 agents)

4. **Task Endpoints** (`src/api/routes/tasks.py`)
   - ✅ `GET /api/tasks/agents/{id}/tasks` - Execution history with pagination
   - ✅ `GET /api/tasks/{id}` - Specific task details
   - ✅ `POST /api/tasks/{id}/retry` - Retry failed tasks

5. **Resource Management** (`src/harness/resources.py`)
   - ✅ Memory usage monitoring (psutil)
   - ✅ CPU usage monitoring
   - ✅ Process count limits (default: 5)
   - ✅ System resource overview
   - ✅ Process termination (SIGTERM/SIGKILL)

6. **Tests** (`tests/test_harness.py`)
   - ✅ Test executor: simple agent, error handling, timeout, context injection
   - ✅ Test handoff: save/load artifacts, run count, compression
   - ✅ Test resources: process usage, limits detection, system resources
   - ✅ Test scheduler: interval/cron schedules, add/remove, disabled schedules

**Dependencies Added:**
- `apscheduler>=3.10.0` - Task scheduling
- `psutil>=5.9.0` - Resource monitoring
- `aiosqlite` - SQLite async driver for tests

**Success Criteria:**
- ✅ Agents run 24/7 without manual intervention
- ✅ Execute-Summarize-Reset loop implemented
- ✅ Context preserved across 100+ consecutive runs (via HandoffArtifact)
- ✅ Automatic retry with exponential backoff
- ✅ Resource limits enforced
- ✅ Comprehensive test coverage (30+ tests)
- ✅ Complete API documentation

### 3.4 MCP Tools 🚧 **PLANNED**

**Objective**: Provide agents with browser automation, filesystem, and notification capabilities via MCP.

**Target Capability:**
- Agents browse web pages (research, data extraction)
- Agents read/write files in sandboxed workspace
- Agents send notifications (Telegram, n8n)

**Tasks:**
1. **Browser MCP Server** (`src/mcp/browser.py`)
   - Playwright-based automation
   - Navigate, click, extract text, screenshot
   - Based on research/hybrid-browser-agent-architecture.md
   - Headless Chrome in production

2. **Filesystem MCP Server** (`src/mcp/filesystem.py`)
   - Safe read/write operations
   - Sandboxed to `/workspace/{agent_id}/`
   - No access to secrets or system files
   - File size limits (max: 10MB per file)

3. **Notification MCP Server** (`src/mcp/notifications.py`)
   - Telegram bot integration (TELEGRAM-BOT-TOKEN)
   - n8n webhook integration (N8N-API)
   - Email via SendGrid (future)

4. **Agent Tool Registry** (`src/mcp/registry.py`)
   - Agents declare required tools in config
   - Runtime tool injection
   - Usage tracking and rate limiting
   - Cost attribution per agent

5. **Tests** (`tests/test_mcp.py`)
   - Mock browser operations
   - Test filesystem sandboxing
   - Test notification delivery

**Dependencies to Add:**
- `playwright>=1.40.0` - Browser automation
- `mcp>=1.0.0` - Model Context Protocol SDK
- `python-telegram-bot>=20.0` - Telegram API

**Success Criteria:**
- Agents can autonomously browse web pages
- 100% sandboxing (no filesystem escapes)
- Notifications delivered in < 3 seconds

---

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
