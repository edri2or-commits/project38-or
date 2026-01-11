# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **changelog-updater skill (v1.0.0)** for automatically generating changelog entries from git commit history in `.claude/skills/changelog-updater/SKILL.md`
  - Analyzes git commit history from branch divergence point
  - Parses conventional commit messages (feat, fix, docs, security, etc.)
  - Categorizes changes into appropriate changelog sections (Added/Changed/Fixed/Security)
  - Generates well-formatted, human-readable changelog entries with file references
  - Groups related commits to reduce clutter
  - Updates `docs/changelog.md` under [Unreleased] section automatically
  - Validates markdown syntax and completeness
  - Updated Skills README in `.claude/skills/README.md:221-282` with complete documentation
  - Updated CLAUDE.md in `CLAUDE.md:507-564` with skill description and usage examples
- **100% test coverage achieved** - Added 4 new tests to reach complete code coverage (174/174 statements)
  - PermissionError handling in `ensure_gh_cli()`
  - SubprocessError handling in `ensure_gh_cli()` and `create_pr_with_gh()`
  - Failed branch detection in `create_pr()`
  - All edge cases now covered
- **github_pr API documentation** in `docs/api/github_pr.md` - Complete documentation coverage achieved (3/3 modules)
  - Function reference with docstrings
  - Usage examples and patterns
  - Security guidelines
  - Troubleshooting guide
  - Comparison: gh CLI vs requests
- **Updated Success Metrics** in `docs/BOOTSTRAP_PLAN.md` - Corrected Autonomous Skills count from 4 to 5
- **Git troubleshooting documentation** in `CLAUDE.md:673-810` - Comprehensive guide for handling 403 errors and merge conflicts
  - Problem 1: HTTP 403 on git push (branch protection, merge conflicts)
  - Problem 2: Merge conflicts in PRs (clean branch approach)
  - Problem 3: "Everything up-to-date" with 403 errors
  - Best practices for branch management
  - Real example from PR #28 → PR #29 resolution
- dependency-checker skill (v1.0.0) for auditing Python dependencies for security vulnerabilities in `.claude/skills/dependency-checker/SKILL.md`
  - Scans for known vulnerabilities using pip-audit
  - Identifies outdated packages
  - Validates requirements.txt format and version pinning
  - Checks for dependency conflicts
  - Generates prioritized remediation plans
  - Blocks deployment on CRITICAL/HIGH vulnerabilities
  - Updated Skills README and CLAUDE.md with dependency-checker documentation
- **Universal GitHub PR operations** (`src/github_pr.py`) - Works in any environment, with or without gh CLI
  - Automatic fallback from gh CLI to requests library
  - Handles GitHub tokens from multiple sources (GH_TOKEN, GITHUB_TOKEN, gh auth)
  - Proven to work with Anthropic egress proxy
  - 16 comprehensive tests with 97% overall code coverage
  - Documentation in `CLAUDE.md:581-617`
- GitHub App authentication API documentation in `docs/api/github_auth.md` (complete documentation coverage achieved)
- **Workload Identity Federation (WIF)** - Full migration from static Service Account keys to OIDC-based authentication
- WIF setup complete with Pool: `github-pool` and Provider: `github-provider` (Project: 979429709900)
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
- **All GCP workflows migrated to WIF** - No more static credentials in GitHub Secrets
- Updated `verify-secrets.yml`, `gcp-secret-manager.yml`, `quick-check.yml`, `report-secrets.yml`, and `test-wif.yml` to use WIF
- CLAUDE.md GCP Configuration section updated with WIF details and Provider Resource Name
- Updated BOOTSTRAP_PLAN.md with completed tasks and pending manual execution items
- Enhanced Success Metrics table with current status indicators (100% test coverage achieved)

### Security
- ✅ **Eliminated long-lived Service Account keys** - GitHub Actions now use ephemeral OIDC tokens (1-hour lifetime)
- ✅ **Least privilege access** - WIF restricted to `edri2or-commits/project38-or` repository only
- ✅ **Automatic token rotation** - No manual credential rotation needed
- ✅ **Audit trail** - All WIF authentications logged in GCP Cloud Logging
- Workflow hardening (removed push triggers)
- Branch protection on main
- GitHub Environment "Production" for deploy gates
- OWNER-only agent triggers

## [0.1.0] - 2026-01-10

### Added
- Initial project setup
- GCP Secret Manager integration
- Basic GitHub Actions workflows
