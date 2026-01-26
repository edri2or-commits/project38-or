# OAUTH_PLAN.md - OAuth Strategy for Domain Split

> **Generated**: 2026-01-26
> **Purpose**: Document OAuth strategy for PERSONAL domain

## Overview

The PERSONAL domain requires Google OAuth for accessing Gmail, Calendar, Drive, Sheets, and Docs.
This document outlines the OAuth strategy to enable non-interactive execution.

---

## Current OAuth Implementation

The workspace_mcp_bridge uses a **refresh token flow**:

1. **One-time setup**: Generate authorization URL, user grants access, exchange code for refresh token
2. **Store**: Refresh token stored in GCP Secret Manager (`GOOGLE-OAUTH-REFRESH-TOKEN`)
3. **Runtime**: Use refresh token to obtain short-lived access tokens

### Relevant Files

| File | Purpose |
|------|---------|
| `apps/personal/integrations/workspace_mcp_bridge/auth.py` | OAuth token management |
| `apps/personal/integrations/workspace_mcp_bridge/config.py` | Load OAuth secrets from GCP |
| `.github/workflows/generate-oauth-url.yml` | Generate authorization URL |
| `.github/workflows/exchange-oauth-code.yml` | Exchange code for refresh token |
| `.github/workflows/verify-oauth-config.yml` | Verify OAuth configuration |

### Secrets Required

| Secret Name | Purpose | Domain |
|-------------|---------|--------|
| `GOOGLE-OAUTH-CLIENT-ID` | OAuth 2.0 Client ID | PERSONAL |
| `GOOGLE-OAUTH-CLIENT-SECRET` | OAuth 2.0 Client Secret | PERSONAL |
| `GOOGLE-OAUTH-REFRESH-TOKEN` | Long-lived refresh token | PERSONAL |

---

## Non-Interactive Execution Strategy

### Approach: Refresh Token (Recommended)

The refresh token approach is already implemented and is the recommended path:

1. **Initial Setup** (one-time, interactive):
   ```bash
   # Generate authorization URL
   gh workflow run generate-oauth-url.yml

   # User visits URL and grants permissions
   # Copy the authorization code

   # Exchange code for refresh token
   gh workflow run exchange-oauth-code.yml -f code=<authorization_code>
   ```

2. **Runtime Execution** (non-interactive):
   ```python
   # In workspace_mcp_bridge/auth.py
   async def get_access_token(self):
       """Get valid access token, refreshing if needed."""
       if self._is_token_expired():
           await self._refresh_access_token()
       return self._access_token

   async def _refresh_access_token(self):
       """Refresh access token using refresh token from GCP secrets."""
       # Token exchange with Google OAuth endpoint
       response = await self._oauth_client.post(
           "https://oauth2.googleapis.com/token",
           data={
               "client_id": self._client_id,
               "client_secret": self._client_secret,
               "refresh_token": self._refresh_token,
               "grant_type": "refresh_token",
           }
       )
   ```

### Token Refresh Handling

The refresh token has the following properties:

- **Lifetime**: Indefinite (unless revoked)
- **Refresh**: Access tokens expire after 1 hour
- **Auto-refresh**: workspace_mcp_bridge auto-refreshes before expiry

### Failure Scenarios

| Scenario | Handling |
|----------|----------|
| Refresh token revoked | Manual re-authorization required |
| Token expired during request | Retry with fresh token |
| Network failure | Standard retry with backoff |
| Invalid client credentials | Alert, manual fix required |

---

## Alternative: Service Account (Not Recommended)

A service account could be used if:
- Domain-wide delegation is enabled
- The Google Workspace admin grants calendar/drive access to the service account

**Why not recommended**:
- Requires Google Workspace admin access
- More complex setup
- Personal Gmail may not support domain-wide delegation

---

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| OAuth refresh token flow | ✅ Implemented | In workspace_mcp_bridge/auth.py |
| Token storage in GCP | ✅ Implemented | GOOGLE-OAUTH-REFRESH-TOKEN |
| Auto-refresh logic | ✅ Implemented | Before token expiry |
| Error handling | ✅ Implemented | Retry with backoff |
| Setup workflows | ✅ Implemented | generate-oauth-url, exchange-oauth-code |

---

## Recommendations

1. **Keep the refresh token approach** - It's already working and is the simplest solution

2. **Monitor token health** - Add alerting for OAuth failures to detect token revocation early

3. **Document re-authorization** - If the refresh token is revoked, the user needs to:
   - Run `generate-oauth-url.yml`
   - Complete the OAuth flow in browser
   - Run `exchange-oauth-code.yml` with the new code
