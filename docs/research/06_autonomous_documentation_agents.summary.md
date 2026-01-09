# Summary: Autonomous Documentation Agents

**Source**: `research/06_autonomous_documentation_agents.md`

---

## Summary

Technical specification for an Auto-Documentation Agent that eliminates "documentation drift" by treating doc generation as a CI process. Primary implementation on GitHub Actions with n8n as fallback.

**Key Patterns:**
- **Idempotent PR**: Fixed branch (`ci/auto-docs`) as natural idempotency key
- **Incremental Hashing**: Only regenerate changed files
- **Progressive Disclosure**: Lightweight discovery, full load on activation

---

## Actionable Practices

1. **GitHub App over PAT:**
   - 15,000 req/hr vs 5,000 (Enterprise)
   - Automatic token rotation (1 hour)
   - Clear audit trail ("BotApp[bot]")

2. **Schedule Offset (Avoid Thundering Herd):**
   ```yaml
   schedule:
     - cron: '17 */6 * * *'  # 17th minute, not :00
   ```

3. **Hash Manifest for Incremental Builds:**
   ```json
   {
     "src/auth/login.py": "a1b2c3d4...",
     "docs/adr/0001-record.md": "e5f6g7h8..."
   }
   ```

4. **Artifact Retention:**
   - Set `retention-days: 3` to reduce storage costs
   - Logs are sufficient for debugging

5. **Validation Toolchain:**
   - Links: Lychee (Rust, fast)
   - Linting: markdownlint-cli2
   - Secrets: Gitleaks (entropy-based)
   - Diagrams: mermaid-cli validation

6. **Conflict Resolution:**
   - Prefer rebase over merge
   - Agent is authority on generated files

---

## Risks / Assumptions

| Risk | Impact | Mitigation |
|------|--------|------------|
| Rate limit exhaustion | CI failures | GitHub App, efficient API usage |
| Schedule latency | Delayed runs | Offset from :00, avoid peak hours |
| Thrashing (noise diffs) | Review fatigue | Diff thresholds, whitespace ignore |
| Secret in docs | Exposure | Gitleaks pre-commit check |

**Assumptions:**
- GitHub Actions as primary platform
- Markdown-based documentation
- Mermaid for diagrams

---

## Architecture Decisions Impact

| Decision | Implication |
|----------|-------------|
| GitHub App auth | Higher limits, better audit |
| Fixed branch strategy | No duplicate PRs |
| Hash manifest | Minimal regeneration |
| Git tags for state | No external DB needed |

**Tool Selection:**
| Category | Tool | Why |
|----------|------|-----|
| Link Check | Lychee | Rust speed, offline mode |
| Lint | markdownlint-cli2 | Faster, better config |
| Secrets | Gitleaks | Lightweight, entropy-based |
| ERD | paracelsus | Direct Mermaid output |
