# Workload Identity Federation (WIF) Migration Plan

## Executive Summary

This document outlines the migration from **static Service Account keys** to **Workload Identity Federation (WIF)** for GitHub Actions authentication to GCP.

**Current State:**
- GitHub Actions uses `GCP_SERVICE_ACCOUNT_KEY` (static JSON key) stored in GitHub Secrets
- Security risk: Long-lived credentials that never expire
- Manual rotation required

**Target State:**
- GitHub Actions uses OpenID Connect (OIDC) tokens via WIF
- No static credentials stored in GitHub Secrets
- Automatic token expiration (1 hour)
- Ephemeral, least-privilege authentication

**Security Improvement:**
- Eliminates "Secret Zero" problem for GitHub Actions
- Reduces attack surface (no long-lived keys)
- Follows Google Cloud security best practices
- Enables audit trail via Cloud Logging

---

## Current Architecture

```
┌─────────────────┐
│ GitHub Actions  │
│                 │
│ Secret:         │
│ GCP_SERVICE_    │
│ ACCOUNT_KEY     │──────┐
│ (JSON key)      │      │
└─────────────────┘      │
                         │ Authenticate
                         ▼
                 ┌────────────────┐
                 │ GCP API        │
                 │                │
                 │ Service:       │
                 │ claude-code-   │
                 │ agent@...      │
                 └────────────────┘
                         │
                         │ Access
                         ▼
                 ┌────────────────┐
                 │ Secret Manager │
                 │                │
                 │ Secrets:       │
                 │ - ANTHROPIC    │
                 │ - OPENAI       │
                 │ - RAILWAY      │
                 │ ...            │
                 └────────────────┘
```

---

## Target Architecture (WIF)

```
┌─────────────────┐
│ GitHub Actions  │
│                 │
│ OIDC Token ──┐  │
│ (automatic)  │  │
└──────────────┼──┘
               │
               │ 1. Request OIDC token
               ▼
       ┌────────────────┐
       │ GitHub OIDC    │
       │ Provider       │
       └────────┬───────┘
                │ 2. Issue JWT token
                │
                │ 3. Exchange token
                ▼
       ┌─────────────────────┐
       │ GCP Workload        │
       │ Identity Pool       │
       │                     │
       │ Pool: github-pool   │
       │ Provider: github    │
       └────────┬────────────┘
                │ 4. Federate identity
                │
                │ 5. Grant access
                ▼
       ┌─────────────────────┐
       │ Service Account     │
       │                     │
       │ claude-code-agent@  │
       │ ...                 │
       └────────┬────────────┘
                │ 6. Access resources
                │
                ▼
       ┌─────────────────────┐
       │ Secret Manager      │
       │                     │
       │ Secrets:            │
       │ - ANTHROPIC         │
       │ - OPENAI            │
       │ ...                 │
       └─────────────────────┘
```

---

## Prerequisites

### 1. GCP Project Permissions Required

You (the human owner) must have these roles:
- `roles/iam.workloadIdentityPoolAdmin` (to create WIF pools)
- `roles/iam.serviceAccountAdmin` (to modify service accounts)
- `roles/resourcemanager.projectIamAdmin` (to grant IAM bindings)

### 2. GitHub Repository Information

- **Repository:** `edri2or-commits/project38-or`
- **Repository ID:** (will be retrieved during setup)
- **Branch:** `main` (and `claude/**` for testing)

### 3. GCP Project Information

- **Project ID:** `project38-483612`
- **Project Number:** (will be retrieved during setup)
- **Service Account:** `claude-code-agent@project38-483612.iam.gserviceaccount.com`

---

## Migration Steps

### Phase 1: WIF Setup (GCP Console/CLI)

#### Step 1.1: Get Project Number

```bash
gcloud projects describe project38-483612 --format="value(projectNumber)"
```

Save this value as `PROJECT_NUMBER`.

#### Step 1.2: Enable Required APIs

```bash
gcloud services enable \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  --project=project38-483612
```

#### Step 1.3: Create Workload Identity Pool

```bash
gcloud iam workload-identity-pools create "github-pool" \
  --project="project38-483612" \
  --location="global" \
  --display-name="GitHub Actions Pool"
```

**Verify:**
```bash
gcloud iam workload-identity-pools describe "github-pool" \
  --project="project38-483612" \
  --location="global"
```

#### Step 1.4: Create Workload Identity Provider

```bash
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project="project38-483612" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="assertion.repository_owner == 'edri2or-commits'" \
  --issuer-uri="https://token.actions.githubusercontent.com"
```

**Explanation:**
- `attribute-mapping`: Maps GitHub OIDC token claims to GCP attributes
- `attribute-condition`: Restricts to your GitHub username only
- `issuer-uri`: GitHub's OIDC endpoint

**Verify:**
```bash
gcloud iam workload-identity-pools providers describe "github-provider" \
  --project="project38-483612" \
  --location="global" \
  --workload-identity-pool="github-pool"
```

#### Step 1.5: Grant Service Account Impersonation

Allow the Workload Identity Pool to impersonate your service account:

```bash
gcloud iam service-accounts add-iam-policy-binding \
  "claude-code-agent@project38-483612.iam.gserviceaccount.com" \
  --project="project38-483612" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/edri2or-commits/project38-or"
```

**Replace `PROJECT_NUMBER` with the value from Step 1.1.**

**Verify:**
```bash
gcloud iam service-accounts get-iam-policy \
  "claude-code-agent@project38-483612.iam.gserviceaccount.com" \
  --project="project38-483612"
```

You should see a binding with `roles/iam.workloadIdentityUser`.

#### Step 1.6: Get Workload Identity Provider Resource Name

```bash
gcloud iam workload-identity-pools providers describe "github-provider" \
  --project="project38-483612" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --format="value(name)"
```

This outputs the full resource name:
```
projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider
```

**Save this as `WORKLOAD_IDENTITY_PROVIDER`.**

---

### Phase 2: Update GitHub Actions Workflows

#### Step 2.1: Add WIF Configuration to Workflows

Update all workflows that access GCP (e.g., `verify-secrets.yml`, `gcp-secret-manager.yml`):

**Before (using Service Account key):**
```yaml
- name: Authenticate to GCP
  uses: google-github-actions/auth@v2
  with:
    credentials_json: ${{ secrets.GCP_SERVICE_ACCOUNT_KEY }}
```

**After (using WIF):**
```yaml
- name: Authenticate to GCP
  uses: google-github-actions/auth@v2
  with:
    workload_identity_provider: 'projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider'
    service_account: 'claude-code-agent@project38-483612.iam.gserviceaccount.com'
```

**Example: `verify-secrets.yml` (migrated)**
```yaml
name: Verify Secret Access

on:
  workflow_dispatch:

permissions:
  contents: read
  id-token: write  # 👈 Required for OIDC token

jobs:
  verify:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Authenticate to GCP via WIF
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: 'projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider'
          service_account: 'claude-code-agent@project38-483612.iam.gserviceaccount.com'

      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v2

      - name: Verify Secret Manager Access
        run: |
          python src/secrets_manager.py
```

**Key changes:**
1. Added `id-token: write` permission (required for OIDC)
2. Replaced `credentials_json` with `workload_identity_provider` + `service_account`
3. No more `GCP_SERVICE_ACCOUNT_KEY` secret needed

#### Step 2.2: List of Workflows to Update

Update these workflows:
- `.github/workflows/verify-secrets.yml`
- `.github/workflows/gcp-secret-manager.yml`
- `.github/workflows/report-secrets.yml`
- `.github/workflows/quick-check.yml`
- `.github/workflows/agent-dev.yml` (when it needs GCP access)

---

### Phase 3: Testing & Validation

#### Step 3.1: Test WIF Authentication

Create a test workflow to verify WIF works:

`.github/workflows/test-wif.yml`:
```yaml
name: Test WIF Authentication

on:
  workflow_dispatch:

permissions:
  contents: read
  id-token: write

jobs:
  test-wif:
    runs-on: ubuntu-latest

    steps:
      - name: Authenticate to GCP via WIF
        id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: 'projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider'
          service_account: 'claude-code-agent@project38-483612.iam.gserviceaccount.com'

      - name: Test GCP Access
        run: |
          gcloud auth list
          gcloud projects list

      - name: Test Secret Manager Access
        run: |
          gcloud secrets list --project=project38-483612
```

**Run manually:**
```bash
gh workflow run test-wif.yml
gh run watch
```

**Expected output:**
- Authentication succeeds
- Service account is `claude-code-agent@project38-483612.iam.gserviceaccount.com`
- Secrets are listed successfully

#### Step 3.2: Validation Checklist

- [ ] WIF authentication succeeds in test workflow
- [ ] Service account identity is correct
- [ ] Secret Manager access works
- [ ] No `GCP_SERVICE_ACCOUNT_KEY` used
- [ ] OIDC token is issued (visible in workflow logs)
- [ ] Token expires after 1 hour (ephemeral)

---

### Phase 4: Cleanup & Hardening

#### Step 4.1: Delete GitHub Secret (After Successful Migration)

⚠️ **Only after verifying all workflows work with WIF:**

```bash
gh secret delete GCP_SERVICE_ACCOUNT_KEY --repo edri2or-commits/project38-or
```

#### Step 4.2: Disable Service Account Key (Optional)

In GCP Console:
1. Go to IAM & Admin → Service Accounts
2. Select `claude-code-agent@project38-483612.iam.gserviceaccount.com`
3. Go to "Keys" tab
4. Delete the key that was stored in GitHub Secrets

**Note:** Keep a backup key in a secure location (e.g., 1Password) for emergency access.

#### Step 4.3: Update CLAUDE.md

Update the GCP Configuration section:

```markdown
## GCP Configuration

| Setting | Value |
|---------|-------|
| Project ID | `project38-483612` |
| Service Account | `claude-code-agent@project38-483612.iam.gserviceaccount.com` |
| Auth Method | **Workload Identity Federation (WIF)** |
| WIF Pool | `github-pool` |
| WIF Provider | `github-provider` |
```

---

## Railway Deployment Considerations

⚠️ **Important:** Railway does **not** support WIF (no OIDC capability).

### Railway Must Use Bootstrap Secret

Railway deployment will continue to require a **bootstrap secret**:

**Option 1: Railway Environment Variable (Recommended)**
- Create a new Service Account key specifically for Railway
- Store in Railway environment variables (not in GitHub Secrets)
- Key only has Secret Manager read permissions
- Fetch other secrets at runtime into memory

**Option 2: GCP Secret Manager Reference (Advanced)**
- Railway can use `railway-api` secret to trigger deployment
- GitHub Actions (via WIF) fetches secrets and injects into Railway deployment
- No GCP credentials stored in Railway

**Architecture:**
```
GitHub Actions (WIF) → Fetch Secrets → Deploy to Railway with Secrets as Env Vars
```

This way, Railway never stores GCP credentials.

---

## Security Benefits Summary

| Aspect | Before (Service Account Key) | After (WIF) |
|--------|------------------------------|-------------|
| **Credential Type** | Long-lived JSON key | Ephemeral OIDC token |
| **Expiration** | Never (manual rotation) | 1 hour (automatic) |
| **Storage** | GitHub Secrets | No storage (federated) |
| **Rotation** | Manual (quarterly) | Automatic (every workflow run) |
| **Audit Trail** | Limited | Full Cloud Logging |
| **Attack Surface** | High (if key leaks) | Low (token expires quickly) |
| **Compliance** | ⚠️ Static credentials | ✅ Best practice |

---

## Rollback Plan

If WIF migration fails, rollback is simple:

1. **Keep `GCP_SERVICE_ACCOUNT_KEY` secret in GitHub** (don't delete until verified)
2. **Revert workflows** to use `credentials_json`:
   ```bash
   git revert <wif-migration-commit>
   git push
   ```
3. **Re-enable service account key** (if disabled in GCP)

**Estimated rollback time:** < 5 minutes

---

## Timeline & Effort

| Phase | Duration | Complexity | Risk |
|-------|----------|------------|------|
| Phase 1: GCP Setup | 30 minutes | Medium | Low |
| Phase 2: Workflow Updates | 20 minutes | Low | Low |
| Phase 3: Testing | 15 minutes | Low | Medium |
| Phase 4: Cleanup | 10 minutes | Low | Low |
| **Total** | **~75 minutes** | **Medium** | **Low** |

---

## Next Steps

1. **Human Action Required:**
   - Obtain GCP Owner/Admin access to `project38-483612`
   - Execute Phase 1 commands (GCP setup)
   - Run test workflow to verify

2. **Claude Code Agent Can:**
   - Update workflows (Phase 2)
   - Create test workflow (Phase 3)
   - Update documentation (Phase 4)

3. **Post-Migration:**
   - Monitor workflows for authentication issues
   - Update `docs/BOOTSTRAP_PLAN.md` to mark WIF as completed
   - Document Railway deployment strategy

---

## References

- [GitHub Actions OIDC with GCP](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-google-cloud-platform)
- [GCP Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation)
- [google-github-actions/auth Documentation](https://github.com/google-github-actions/auth)
- [Best Practices for Service Accounts](https://cloud.google.com/iam/docs/best-practices-service-accounts)

---

**Document Version:** 1.0.0
**Last Updated:** 2026-01-10
**Author:** Claude Code Agent
**Status:** Ready for Implementation
