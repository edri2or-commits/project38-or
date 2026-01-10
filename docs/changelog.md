# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive WIF migration plan in `docs/wif-migration-plan.md` with step-by-step GCP setup instructions
- Manual setup guide for GitHub Admin tasks in `docs/manual-setup-guide.md` (branch protection + environments)
- test-runner skill (v1.0.0) for automated test execution before commits in `.claude/skills/test-runner/SKILL.md`
- security-checker skill (v1.0.0) for validating no secrets in commits in `.claude/skills/security-checker/SKILL.md`
- pr-helper skill (v1.0.0) for standardized PR creation in `.claude/skills/pr-helper/SKILL.md`
- Complete skills documentation in `CLAUDE.md:272-453` for all four skills
- Updated Skills README with test-runner, security-checker, and pr-helper documentation in `.claude/skills/README.md:51-176`

- Claude Skills infrastructure in `.claude/skills/` directory
- doc-updater skill (v1.0.0) for autonomous documentation maintenance in `.claude/skills/doc-updater/SKILL.md`
- Skills README with usage guide and best practices in `.claude/skills/README.md`
- Available Skills section in `CLAUDE.md:220-283` documenting skill system
- Manual trigger (workflow_dispatch) for docs-check.yml workflow
- Complete test coverage for exception handling scenarios (100% coverage achieved)
- Test for RequestException in github_auth.get_installation_token()
- Test for SubprocessError in github_auth.configure_gh_cli()
- Test for generic exceptions in secrets_manager.get_secret()
- Test for exception handling in secrets_manager.list_secrets()
- Test for failure scenario in secrets_manager.load_secrets_to_env()
- Test for successful gh CLI configuration
- GitHub PAT security guidelines in docs/SECURITY.md
- Claude Code Web environment configuration documentation in CLAUDE.md
- GitHub MCP Server documentation in CLAUDE.md (autonomy configuration)
- Tests for github_auth module
- pytest pythonpath configuration in pyproject.toml
- GitHub App authentication module (github_auth.py, github_auth.sh)
- Mandatory CI verification process in CLAUDE.md
- CI enforcement for documentation (docs-check.yml)
- Automatic changelog verification on PRs modifying src/
- Docstring validation with pydocstyle (Google style)
- MkDocs documentation with Material theme
- Automatic documentation system with mkdocstrings
- GitHub Pages deployment
- pytest framework with coverage
- Python linting with ruff
- Agent workflow for issue handling (`/claude` command)
- SecretManager for GCP Secret Manager access
- CLAUDE.md project context file
- Research summaries (7 documents in docs/research/)
- Requirements lockfile for reproducible builds

### Changed
- Updated BOOTSTRAP_PLAN.md with completed tasks and pending manual execution items
- Enhanced Success Metrics table with current status indicators (100% test coverage achieved)

### Security
- Workflow hardening (removed push triggers)
- Branch protection on main
- GitHub Environment "Production" for deploy gates
- OWNER-only agent triggers

## [0.1.0] - 2026-01-10

### Added
- Initial project setup
- GCP Secret Manager integration
- Basic GitHub Actions workflows
