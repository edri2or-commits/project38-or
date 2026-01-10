# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Manual trigger (workflow_dispatch) for docs-check.yml workflow
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
