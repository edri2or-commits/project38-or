# Manual Setup Guide: GitHub Admin Tasks

## Overview

This guide provides step-by-step instructions for GitHub repository configurations that require Admin permissions.

**Prerequisites:**
- GitHub account with Admin access to `edri2or-commits/project38-or`
- GitHub web browser access

---

## 1. Branch Protection Rules for `main`

### Goal
Prevent accidental direct pushes to main and enforce PR workflow with required checks.

### Steps

1. **Navigate to Branch Protection Settings:**
   - Go to: https://github.com/edri2or-commits/project38-or/settings/branches
   - Click "Add branch protection rule" (or "Add rule")

2. **Branch Name Pattern:**
   ```
   main
   ```

3. **Configure Protection Rules:**

   #### ✅ Required Status Checks
   - [x] Require status checks to pass before merging
   - [x] Require branches to be up to date before merging
   - Select these status checks:
     - `test` (from `.github/workflows/test.yml`)
     - `lint` (from `.github/workflows/lint.yml`)
     - `docs-check` (from `.github/workflows/docs-check.yml`)

   #### ✅ Required Pull Request Reviews
   - [x] Require a pull request before merging
   - [x] Require approvals: **1**
   - [x] Dismiss stale pull request approvals when new commits are pushed
   - [x] Require review from Code Owners: ⬜ (optional)

   #### ✅ Additional Rules
   - [x] Require conversation resolution before merging
   - [x] Do not allow bypassing the above settings (for admins)
   - [x] Restrict who can push to matching branches: ⬜ (leave unchecked for flexibility)

   #### ❌ Force Push & Deletion
   - [ ] Allow force pushes: **Disabled**
   - [ ] Allow deletions: **Disabled**

4. **Save Changes:**
   - Click "Create" or "Save changes"

### Verification

Run this command to verify:
```bash
gh api repos/edri2or-commits/project38-or/branches/main/protection
```

Expected output should include:
```json
{
  "required_status_checks": {
    "contexts": ["test", "lint", "docs-check"]
  },
  "required_pull_request_reviews": {
    "required_approving_review_count": 1
  }
}
```

---

## 2. GitHub Environment: "Production"

### Goal
Create a deployment environment with required reviewers for Railway deployments.

### Steps

1. **Navigate to Environments:**
   - Go to: https://github.com/edri2or-commits/project38-or/settings/environments
   - Click "New environment"

2. **Environment Name:**
   ```
   Production
   ```

3. **Configure Environment Protection Rules:**

   #### ✅ Required Reviewers
   - [x] Required reviewers
   - Add yourself (`edri2or-commits`) as a reviewer
   - You can add up to 6 reviewers

   #### ✅ Wait Timer
   - [ ] Wait timer: **0 minutes** (optional: set to 5 minutes for safety)

   #### ✅ Deployment Branches
   - Select: **Protected branches only**
   - This ensures only code from `main` (protected branch) can deploy to Production

   #### ✅ Environment Secrets (Optional)
   - Add Railway-specific secrets here if needed:
     - `RAILWAY_TOKEN` (if different from global `RAILWAY-API`)

4. **Save Environment:**
   - Click "Save protection rules"

### Verification

Run this command to verify:
```bash
gh api repos/edri2or-commits/project38-or/environments/Production
```

Expected output:
```json
{
  "name": "Production",
  "protection_rules": [
    {
      "type": "required_reviewers",
      "reviewers": [...]
    }
  ],
  "deployment_branch_policy": {
    "protected_branches": true
  }
}
```

---

## 3. Update Workflows to Use Production Environment

Once the "Production" environment is created, update deployment workflows to reference it:

### Example: `.github/workflows/deploy-railway.yml` (future)

```yaml
name: Deploy to Railway

on:
  workflow_dispatch:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment:
      name: Production  # 👈 This triggers required reviewers
      url: https://your-app.railway.app

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to Railway
        run: |
          # Deployment commands here
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_API }}
```

---

## 4. Grant Additional PAT Permissions (Optional)

If you want Claude Code to manage these settings autonomously, update your Fine-grained PAT:

### Navigate to:
https://github.com/settings/personal-access-tokens/

### Required Permissions:
- **Repository permissions:**
  - `Administration`: **Read and write** ✅
  - `Contents`: **Read and write** ✅
  - `Pull requests`: **Read and write** ✅
  - `Environments`: **Read and write** ✅
  - `Metadata`: **Read-only** (automatic) ✅

### Update Environment Variable:
```bash
# In Claude Code Web UI:
# Environment → Edit → Update GH_TOKEN with new PAT
```

---

## Success Checklist

- [ ] Branch protection rules created for `main`
- [ ] Status checks required: `test`, `lint`, `docs-check`
- [ ] Pull request reviews required (1 approval)
- [ ] GitHub Environment "Production" created
- [ ] Required reviewers configured
- [ ] Deployment branch policy set to "Protected branches only"
- [ ] Verification commands run successfully

---

## Next Steps

After completing these manual steps:
1. Update `docs/BOOTSTRAP_PLAN.md` to mark these tasks as completed
2. Proceed with WIF migration planning (see `docs/wif-migration-plan.md`)
3. Test the protection by attempting a direct push to main (should fail)

---

## Troubleshooting

### Issue: "Resource not accessible by personal access token"
**Solution:** Your PAT lacks admin permissions. Follow section 4 to grant additional permissions.

### Issue: "Status checks not found"
**Solution:** Run the workflows at least once so GitHub recognizes them:
```bash
gh workflow run test.yml
gh workflow run lint.yml
gh workflow run docs-check.yml
```

### Issue: "No reviewers available for Environment"
**Solution:** Ensure you have at least one collaborator or team member. Personal repos with single owner can skip required reviewers.

---

**Document Version:** 1.0.0
**Last Updated:** 2026-01-10
**Author:** Claude Code Agent
