# AGENTS.md - Agent Context for project38-or

> Standard format for AI agent onboarding (2026 Agent Interop Standards)

## Project Overview

**Name:** project38-or
**Type:** Personal AI System with Autonomous Capabilities
**Status:** Production (https://or-infra.com)

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11+ |
| Framework | FastAPI |
| Database | PostgreSQL (Railway) |
| Secrets | GCP Secret Manager |
| CI/CD | GitHub Actions |
| Deployment | Railway |

## Code Conventions

### Python Style
- Type hints required
- Google-style docstrings
- `pathlib` over `os.path`
- `async/await` for I/O

### Git Commits
- Conventional commits: `type(scope): message`
- Types: `feat`, `fix`, `docs`, `security`, `refactor`, `test`
- One logical change per commit

## Security Rules (Critical)

1. **NEVER** print/log secret values
2. **NEVER** commit secrets to code
3. **NEVER** store secrets on disk
4. **ALWAYS** use `src/secrets_manager.py`

```python
# Correct usage
from src.secrets_manager import SecretManager
manager = SecretManager()
api_key = manager.get_secret("ANTHROPIC-API")  # Use, never print
```

## Testing Requirements

```bash
# Run before any commit
pytest tests/ -v
```

- Mock external APIs (GCP, GitHub)
- Test file naming: `test_<module>.py`

## Directory Structure

```
src/                    # Production code (29,000+ lines)
├── api/                # FastAPI endpoints
├── mcp_gateway/        # MCP tools (Railway, n8n, Workspace)
├── multi_agent/        # Agent orchestration
├── research/           # Research integration (ADR-009)
└── secrets_manager.py  # GCP secrets access

tests/                  # pytest tests
docs/                   # Documentation
.claude/skills/         # Agent Skills
experiments/            # Isolated experiments
```

## Available Skills

| Skill | Purpose |
|-------|---------|
| `research-ingestion` | Process research notes |
| `doc-updater` | Keep docs in sync |
| `test-runner` | Run tests before commit |
| `security-checker` | Scan for secrets |
| `pr-helper` | Create standardized PRs |

## Key Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Full context (~1300 lines) |
| `docs/JOURNEY.md` | Project timeline |
| `docs/decisions/` | Architecture decisions (ADRs) |

## What Agents Can Do

- Read any file
- Search codebase
- Run tests and linters
- Create feature branches
- Open Pull Requests

## What Requires Human Approval

- Merge to main
- Deploy to Railway
- Modify IAM/secrets
- Add dependencies

---

*For full context, see `CLAUDE.md`*
