# ADR-004: Google Workspace OAuth Integration

## Status
**Accepted** - Implemented 2026-01-16

## Context

The project38-or autonomous system requires the ability to interact with Google Workspace services (Gmail, Calendar, Drive, Sheets, Docs) to enable full operational autonomy. This enables Claude to:
- Send notifications and reports via Gmail
- Schedule and manage calendar events
- Store and retrieve files from Drive
- Read/write structured data in Sheets
- Create and edit documents

### Constraints
1. OAuth 2.0 is required for Google Workspace APIs (no API key option)
2. User consent must be obtained via browser (Google security requirement)
3. Refresh tokens must be stored securely
4. APIs must be explicitly enabled per GCP project

## Decision

We implemented a **workflow-based OAuth flow** that:

1. **Stores credentials in GCP Secret Manager** (not GitHub Secrets or env vars)
   - `GOOGLE-OAUTH-CLIENT-ID`
   - `GOOGLE-OAUTH-CLIENT-SECRET`
   - `GOOGLE-OAUTH-REFRESH-TOKEN`

2. **Uses GitHub Actions workflows** for OAuth operations:
   - `generate-oauth-url.yml` - Creates authorization URL, posts to issue #149
   - `exchange-oauth-code.yml` - Exchanges auth code for refresh token
   - `verify-oauth-config.yml` - Validates credentials match
   - `check-oauth-secrets.yml` - Lists all OAuth secrets status

3. **Requires one-time human consent** via browser, then fully autonomous

4. **Enables 5 Google Workspace APIs**:
   - Gmail API
   - Calendar API
   - Drive API
   - Sheets API
   - Docs API

## Alternatives Considered

### Alternative 1: Service Account with Domain-Wide Delegation
- **Pros**: No user consent needed after setup
- **Cons**: Requires Google Workspace admin access, complex setup, overkill for personal use
- **Decision**: Rejected - user has personal Gmail, not Workspace organization

### Alternative 2: Store credentials in GitHub Secrets
- **Pros**: Simpler workflow access
- **Cons**: Not accessible from Claude Code sessions, violates principle of GCP as single source of truth
- **Decision**: Rejected - consistency with existing secrets architecture

### Alternative 3: Manual token refresh
- **Pros**: Simpler implementation
- **Cons**: Tokens expire, requires human intervention
- **Decision**: Rejected - breaks autonomy requirement

## Consequences

### Positive
- Full autonomy over Google Workspace once set up
- Credentials secured in GCP Secret Manager with WIF access
- Verifiable with actual API calls (Message IDs, Event IDs)
- Consistent with existing secrets architecture

### Negative
- One-time human intervention required for OAuth consent
- Must enable each API manually in GCP Console
- Refresh token can expire if unused for 6 months (rare)

### Neutral
- Adds 6 new GitHub Actions workflows
- Requires 5 APIs enabled in GCP project

## Implementation Checklist

- [x] Create OAuth Client ID in GCP Console (2026-01-16)
- [x] Store Client ID in Secret Manager: `GOOGLE-OAUTH-CLIENT-ID`
- [x] Store Client Secret in Secret Manager: `GOOGLE-OAUTH-CLIENT-SECRET`
- [x] Create `generate-oauth-url.yml` workflow
- [x] Create `exchange-oauth-code.yml` workflow
- [x] Create `verify-oauth-config.yml` workflow
- [x] Create `check-oauth-secrets.yml` workflow
- [x] Obtain user consent and exchange code
- [x] Store Refresh Token: `GOOGLE-OAUTH-REFRESH-TOKEN`
- [x] Enable Gmail API
- [x] Enable Calendar API
- [x] Enable Drive API
- [x] Enable Sheets API
- [x] Enable Docs API
- [x] Verify Gmail works (Message ID: `19bc65f638f5c271`)
- [x] Verify Calendar works (Event ID: `9ke4vrm7to190gugfht64tnoso`)
- [x] Verify Drive works (Folder created and deleted)
- [x] Verify Sheets works (Sheet created, 3 rows written)
- [x] Verify Docs works (Doc created, text inserted)

## Verification Evidence

All tests performed on 2026-01-16 and verified via GitHub Actions:

| Service | Status | Evidence |
|---------|--------|----------|
| Gmail | ✅ Verified | Message ID: `19bc65f638f5c271` |
| Calendar | ✅ Verified | Event ID: `9ke4vrm7to190gugfht64tnoso` |
| Drive | ✅ Verified | Folder ID: `1KezQCmI...` (created & cleaned) |
| Sheets | ✅ Verified | Sheet ID: `1KS7dfBA...` (wrote 3 rows) |
| Docs | ✅ Verified | Doc ID: `1OwArBwC...` (inserted text) |

## Related Documents
- `CLAUDE.md` (root) - Project context with Workspace status
- [docs/changelog.md](../changelog.md) - Version history
- [Issue #149](https://github.com/edri2or-commits/project38-or/issues/149) - OAuth setup tracking

## Update Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-16 | Initial creation - full implementation complete | Claude |
