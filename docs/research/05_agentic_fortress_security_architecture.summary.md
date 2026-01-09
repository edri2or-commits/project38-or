# Summary: Agentic Fortress - Security Architecture

**Source**: `research/05_agentic_fortress_security_architecture.md`

---

## Summary

Comprehensive security blueprint for a "Claude Code-first" ecosystem. Eliminates long-lived secrets from GitHub via **Workload Identity Federation (WIF)** and implements runtime secret fetching from GCP Secret Manager.

**Core Pattern: Federated Bootstrap Architecture**
1. GitHub Actions authenticates to GCP via OIDC (no static keys)
2. CI fetches Railway bootstrap key from GCP
3. Bootstrap key injected to Railway env vars
4. App fetches runtime secrets (OpenAI, etc.) into memory at startup

---

## Actionable Practices

1. **WIF Setup:**
   ```bash
   gcloud iam workload-identity-pools create "github-agent-pool"
   gcloud iam workload-identity-pools providers create-oidc "github-provider" \
     --issuer-uri="https://token.actions.githubusercontent.com" \
     --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository"
   ```

2. **GitHub Action with WIF:**
   ```yaml
   permissions:
     id-token: write  # Required for OIDC
   steps:
     - uses: google-github-actions/auth@v2
       with:
         workload_identity_provider: 'projects/.../providers/github-provider'
   ```

3. **Runtime Secret Fetch (Fail Fast):**
   ```python
   if not BOOTSTRAP_CREDENTIALS:
       sys.exit(1)  # Don't run without secrets
   ```

4. **Human Approval Gate:**
   - Use GitHub Environments with Required Reviewers
   - Agent cannot deploy without human approval

5. **Sandboxed Branches:**
   - Agent works on feature branches only
   - Merge to main requires human review

---

## Risks / Assumptions

| Risk | Impact | Mitigation |
|------|--------|------------|
| OIDC token theft | 1-hour access window | Short token lifetime, repo claim binding |
| Bootstrap key exposure | Runtime secret access | Separate from CI secrets, rotatable |
| Agent goal hijacking | Malicious code | CLAUDE.md constitution, prompt hardening |
| Tool misuse | Exfiltration | Network egress policies |

**OWASP Agentic Mitigations:**
- ASI01 (Goal Hijacking): Prompt hardening, monitor output
- ASI02 (Tool Misuse): Network restrictions, sandboxed branches
- ASI03 (Privilege Abuse): Scoped GITHUB_TOKEN, no workflow:write

**Assumptions:**
- GCP as secret authority
- Railway as runtime (no native WIF support)
- GitHub Actions as CI/CD

---

## Architecture Decisions Impact

| Decision | Implication |
|----------|-------------|
| No GitHub Secrets for runtime | Secrets never in repo settings |
| WIF over PAT/SA Keys | Ephemeral credentials, better audit |
| Bootstrap pattern | One secret to fetch all secrets |
| Environment protection | Human gate before production |

**Identity Topology:**
| Entity | Location | Credential | Lifetime |
|--------|----------|------------|----------|
| Orchestrator | GitHub | OIDC Token | 1 hour |
| Runtime | Railway | Bootstrap Key | Until rotated |
| Agent | CLI | Anthropic API | Session |
