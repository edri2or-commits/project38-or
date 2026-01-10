# WIF Setup Scripts

This directory contains scripts to set up **Workload Identity Federation (WIF)** for GitHub Actions to authenticate with Google Cloud Platform.

## What is WIF?

Workload Identity Federation allows GitHub Actions to authenticate with GCP using short-lived OIDC tokens instead of long-lived Service Account keys. This is:

- ✅ **More secure** - No static keys to rotate or leak
- ✅ **Easier to manage** - No secrets to store in GitHub
- ✅ **Google recommended** - Best practice for CI/CD authentication

## Prerequisites

Before running these scripts, ensure you have:

1. **gcloud CLI installed**
   - Windows: Download from https://cloud.google.com/sdk/docs/install
   - Linux/macOS: `curl https://sdk.cloud.google.com | bash`
   - Verify: `gcloud --version`

2. **Authenticated with GCP**
   ```bash
   # Using Service Account key
   gcloud auth activate-service-account --key-file="path/to/key.json"
   gcloud config set project project38-483612

   # OR using user account (if you have permissions)
   gcloud auth login
   gcloud config set project project38-483612
   ```

3. **Required GCP Permissions**
   The authenticated account needs:
   - `iam.workloadIdentityPools.create`
   - `iam.workloadIdentityPoolProviders.create`
   - `iam.serviceAccounts.setIamPolicy`
   - Or roles: `roles/iam.workloadIdentityPoolAdmin` + `roles/iam.serviceAccountAdmin`

4. **Network Access**
   - These scripts make API calls to GCP
   - Claude Code in isolated containers **cannot** run them
   - Run from your local machine (Windows/Linux/macOS)

## Usage

### Option 1: Windows (PowerShell)

```powershell
# Navigate to project directory
cd C:\Users\edri2\claude-38\project38-or

# Run the PowerShell script
.\scripts\setup-wif.ps1
```

### Option 2: Linux/macOS/WSL (Bash)

```bash
# Navigate to project directory
cd ~/project38-or

# Make script executable
chmod +x scripts/setup-wif.sh

# Run the script
bash scripts/setup-wif.sh
```

### Option 3: Manual Setup (if scripts fail)

If the automated scripts don't work, you can run the commands manually. See the [Manual Setup Guide](#manual-setup-guide) below.

## What the Scripts Do

The scripts perform these steps:

1. **Get project number** - Required for IAM bindings
2. **Enable APIs** - `iamcredentials.googleapis.com` and `sts.googleapis.com`
3. **Create Workload Identity Pool** - Named `github-pool`
4. **Create OIDC Provider** - Named `github-provider`, configured for GitHub Actions
5. **Grant impersonation rights** - Allow GitHub repo to impersonate Service Account
6. **Output Provider Resource Name** - You'll need this for GitHub Actions workflows

## Expected Output

```
========================================
  ✓ WIF Setup Complete!
========================================

Provider Resource Name:
projects/123456789/locations/global/workloadIdentityPools/github-pool/providers/github-provider

Next steps:
1. Add this to your GitHub Actions workflow:
   permissions:
     id-token: write
     contents: read

2. Use the google-github-actions/auth action:
   - uses: google-github-actions/auth@v2
     with:
       workload_identity_provider: 'projects/.../github-provider'
       service_account: 'claude-code-agent@project38-483612.iam.gserviceaccount.com'

3. No Service Account key needed - GitHub will use OIDC tokens!
```

## Using WIF in GitHub Actions

After running the setup script, update your workflows:

```yaml
name: Example Workflow

on:
  push:
    branches: [main]

permissions:
  id-token: write    # Required for OIDC token
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # Authenticate with GCP using WIF
      - uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: 'projects/123456789/locations/global/workloadIdentityPools/github-pool/providers/github-provider'
          service_account: 'claude-code-agent@project38-483612.iam.gserviceaccount.com'

      # Now you can use gcloud, gsutil, etc.
      - name: Access GCP Secret Manager
        run: |
          gcloud secrets versions access latest --secret="ANTHROPIC-API"
```

## Troubleshooting

### "Pool already exists"
This is **not an error**. The script will skip creation and use the existing pool.

### "Permission denied"
- Verify you're authenticated: `gcloud auth list`
- Check project: `gcloud config get-value project`
- Ensure the authenticated account has the required IAM permissions

### "API not enabled"
The script enables APIs automatically. If this fails:
```bash
gcloud services enable iamcredentials.googleapis.com sts.googleapis.com --project=project38-483612
```

### "Network error" / "Connection timeout"
- Check internet connection
- Verify firewall isn't blocking GCP APIs
- Try again - GCP APIs can be slow sometimes

### Script runs but GitHub Actions still can't authenticate
1. Verify `permissions: id-token: write` is in your workflow
2. Check the `workload_identity_provider` value matches exactly
3. Ensure repository name matches: `edri2or-commits/project38-or`
4. Workflow must be triggered from the main repository (not a fork)

## Manual Setup Guide

If automated scripts fail, run these commands manually:

<details>
<summary>Click to expand manual commands</summary>

### 1. Get Project Number
```bash
PROJECT_ID="project38-483612"
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
echo "Project Number: $PROJECT_NUMBER"
```

### 2. Enable APIs
```bash
gcloud services enable \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  --project=$PROJECT_ID
```

### 3. Create Workload Identity Pool
```bash
gcloud iam workload-identity-pools create "github-pool" \
  --project=$PROJECT_ID \
  --location="global" \
  --display-name="GitHub Actions Pool"
```

### 4. Create OIDC Provider
```bash
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project=$PROJECT_ID \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="assertion.repository_owner == 'edri2or-commits'" \
  --issuer-uri="https://token.actions.githubusercontent.com"
```

### 5. Grant Impersonation Rights
```bash
SERVICE_ACCOUNT="claude-code-agent@project38-483612.iam.gserviceaccount.com"
GITHUB_REPO="edri2or-commits/project38-or"

gcloud iam service-accounts add-iam-policy-binding $SERVICE_ACCOUNT \
  --project=$PROJECT_ID \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/$GITHUB_REPO"
```

### 6. Get Provider Resource Name
```bash
gcloud iam workload-identity-pools providers describe "github-provider" \
  --project=$PROJECT_ID \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --format="value(name)"
```

Save the output from step 6 - you'll need it for GitHub Actions!

</details>

## Security Notes

- WIF is scoped to repository: `edri2or-commits/project38-or`
- Only workflows from this repo can impersonate the Service Account
- Tokens are short-lived (1 hour) and automatically rotated
- No long-lived credentials stored in GitHub Secrets
- Additional security: attribute condition limits to `edri2or-commits` owner

## References

- [Google Cloud WIF Documentation](https://cloud.google.com/iam/docs/workload-identity-federation)
- [GitHub Actions OIDC](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [google-github-actions/auth](https://github.com/google-github-actions/auth)

## Support

For issues with these scripts:
1. Check the [Troubleshooting](#troubleshooting) section
2. Verify all prerequisites are met
3. Try the manual setup commands
4. Open an issue in the repository with full error output

---

**Note:** These scripts are idempotent - running them multiple times is safe. They will skip resources that already exist.
