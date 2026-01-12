# Preview Deployments Guide

## Overview

Preview deployments allow you to test Pull Requests in isolated Railway environments before merging to production. Each PR gets its own temporary deployment with a unique URL and isolated database.

**Benefits:**
- 🔍 Test changes in production-like environment
- 🗄️ Isolated database per PR (no data pollution)
- 🔗 Unique URL for each PR
- 🔄 Automatic updates on new commits
- 🧹 Automatic cleanup when PR closes
- 💬 PR comments with deployment status

---

## How It Works

### Automatic Workflow

1. **PR Opened** → Preview deployment triggered
2. **New Commit Pushed** → Preview automatically updated
3. **PR Closed/Merged** → Preview environment cleaned up

### Architecture

```
Pull Request #123
    ↓
GitHub Actions (.github/workflows/preview-deploy.yml)
    ↓
Railway CLI (railway up --service preview-pr-123)
    ↓
Railway Environment: preview-pr-123
    ├── FastAPI Application (ephemeral)
    ├── PostgreSQL Database (isolated)
    └── HTTPS URL: https://preview-pr-123.up.railway.app
```

---

## Workflow Details

### preview-deploy.yml

**Trigger:**
- Pull request opened
- New commit pushed to PR
- PR reopened

**Process:**
1. Authenticate to GCP via WIF
2. Fetch RAILWAY-API token from Secret Manager
3. Deploy to Railway with service name `preview-pr-{PR_NUMBER}`
4. Wait for deployment and health check
5. Comment on PR with preview URL and status

**Permissions:**
- `contents: read` - Read repository code
- `id-token: write` - WIF authentication
- `pull-requests: write` - Comment on PR

**Concurrency:**
- Group: `preview-deploy-{PR_NUMBER}`
- Cancel in progress: `true` (cancel old when new commit pushed)

### preview-cleanup.yml

**Trigger:**
- Pull request closed (merged or not merged)

**Process:**
1. Authenticate to GCP via WIF
2. Fetch RAILWAY-API token
3. Delete Railway service `preview-pr-{PR_NUMBER}`
4. Comment on PR with cleanup confirmation

---

## Using Preview Deployments

### For PR Authors

When you open a PR, GitHub Actions automatically:
1. Deploys your branch to a preview environment
2. Comments on the PR with preview URL
3. Updates status as deployment progresses

**Example PR Comment:**
```markdown
## 🚀 Preview Deployment

**Status:** ✅ Healthy
**URL:** https://preview-pr-42.up.railway.app
**Commit:** `abc1234`
**PR:** #42

### Quick Links
- 📊 [API Docs](https://preview-pr-42.up.railway.app/docs)
- 🏥 [Health Check](https://preview-pr-42.up.railway.app/health)
- 📖 [ReDoc](https://preview-pr-42.up.railway.app/redoc)
```

### For Reviewers

1. Click preview URL in PR comment
2. Test API endpoints interactively via `/docs`
3. Verify health check at `/health`
4. Test with real HTTP requests (isolated database)

### Testing Checklist

- [ ] Preview URL loads successfully
- [ ] `/health` endpoint returns 200 OK
- [ ] `/docs` shows correct API documentation
- [ ] Test API endpoints return expected responses
- [ ] Database operations work correctly
- [ ] No errors in Railway logs

---

## Environment Isolation

Each preview environment is **completely isolated**:

| Resource | Isolation Level |
|----------|----------------|
| **Application Code** | Per-PR branch code |
| **Database** | Separate PostgreSQL instance |
| **Secrets** | Same as production (from GCP Secret Manager) |
| **URL** | Unique subdomain per PR |
| **Logs** | Separate Railway logs |

**Important:** Preview environments share secrets with production, but have isolated databases. Be careful with API rate limits and external service calls.

---

## Cost Estimation

Railway charges per resource usage:

| PR Activity | Estimated Cost |
|-------------|----------------|
| 1 PR, 1 day active | ~$0.50 |
| 1 PR, 1 week active | ~$3.50 |
| 5 PRs simultaneously, 1 week | ~$17.50 |

**Free Tier:**
- Railway provides $5/month credit
- Sufficient for ~10 PR-days per month
- Production deployment cost is separate

**Cost Optimization Tips:**
1. Close PRs when not actively reviewing
2. Use draft PRs to prevent automatic deployments
3. Mark PRs as ready for review when deployment needed
4. Cleanup happens automatically on PR close

---

## Troubleshooting

### Issue: Preview deployment fails with "Service not found"

**Cause:** Railway service creation failed

**Solution:**
1. Check Railway Dashboard for error logs
2. Verify RAILWAY-API token has correct permissions
3. Ensure Railway project exists
4. Check GitHub Actions logs for detailed error

### Issue: Health check times out

**Cause:** Application startup takes > 100 seconds

**Solution:**
1. Check Railway logs for startup errors
2. Verify dependencies install correctly
3. Ensure database migrations run successfully
4. Check `railway.json` healthcheckTimeout setting

### Issue: Database connection fails

**Cause:** PostgreSQL not provisioned for preview

**Solution:**
1. Verify Railway project has PostgreSQL database
2. Check `DATABASE_URL` environment variable is set
3. Ensure database auto-attach is enabled in Railway
4. Check Railway service configuration

### Issue: Preview URL returns 404

**Cause:** Deployment succeeded but routing not configured

**Solution:**
1. Wait 1-2 minutes for DNS propagation
2. Check Railway Dashboard for deployment status
3. Verify application is listening on `$PORT`
4. Check Railway service domain settings

### Issue: "Exceeded Railway service limit"

**Cause:** Too many preview environments active

**Solution:**
1. Close unused PRs to trigger cleanup
2. Manually delete old preview services in Railway Dashboard
3. Consider upgrading Railway plan for more services

---

## Configuration

### Workflow Configuration

**Paths ignored (no deployment triggered):**
```yaml
paths-ignore:
  - 'docs/**'
  - '*.md'
  - '.github/workflows/docs*.yml'
```

**Customization:**
- Edit `.github/workflows/preview-deploy.yml`
- Adjust `paths-ignore` for your needs
- Modify health check retries (default: 10)
- Change timeout (default: 100 seconds)

### Railway Configuration

Preview deployments use the same configuration as production:
- `railway.json` - Build and deploy settings
- `Procfile` - Process definition (fallback)

**Environment-specific settings:**
- Each preview gets unique `SERVICE_NAME`
- PostgreSQL auto-provisioned per service
- Secrets fetched from GCP Secret Manager

---

## GitHub Environment Setup

### Required GitHub Environment: "Preview"

Create in GitHub repository settings:

1. Go to Settings → Environments
2. Click "New environment"
3. Name: `Preview`
4. **Do NOT** require approval (automatic deployments)
5. Save environment

**Why separate environment?**
- Different permissions than Production
- No approval gate (automatic)
- Isolated deployment history
- Can have different secrets if needed

---

## Security Considerations

### Secrets Handling

- ✅ Preview environments use production secrets
- ✅ RAILWAY-API token fetched via WIF (no GitHub Secrets)
- ✅ Secrets never logged or exposed
- ✅ Automatic cleanup prevents secret leaks

### Access Control

- ✅ Only repository contributors can trigger deployments
- ✅ Forks do NOT trigger preview deployments (security)
- ✅ Preview URLs are public but database is isolated
- ⚠️ Be careful with rate-limited APIs (shared across previews)

### Best Practices

1. **Never expose secrets in preview logs**
2. **Test with mock data, not production data**
3. **Close PRs promptly to cleanup resources**
4. **Review Railway logs for security issues**
5. **Limit external API calls in preview environments**

---

## Advanced Usage

### Manual Preview Deployment

If automatic deployment doesn't trigger:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Set RAILWAY_TOKEN environment variable
export RAILWAY_TOKEN="your-token-here"

# Deploy to preview service
railway up --service preview-pr-123
```

### Debugging Preview Environments

```bash
# View logs
railway logs --service preview-pr-123

# Check service status
railway status --service preview-pr-123

# Open Railway Dashboard
railway open
```

### Forcing Redeployment

1. Close and reopen the PR, OR
2. Push empty commit:
   ```bash
   git commit --allow-empty -m "trigger: redeploy preview"
   git push
   ```

---

## Integration with CI/CD

### Workflow Dependencies

Preview deployments integrate with other workflows:

```
PR Opened
    ↓
├─ lint.yml (check code quality)
├─ test.yml (run tests)
├─ docs-check.yml (verify documentation)
└─ preview-deploy.yml (deploy preview)
    ↓
All checks pass
    ↓
Reviewer approves
    ↓
PR Merged
    ↓
├─ preview-cleanup.yml (cleanup preview)
└─ deploy-railway.yml (deploy to production)
```

### Blocking Deployments

To prevent preview deployment for specific PRs:

1. **Use Draft PR:**
   - GitHub Actions don't run for draft PRs
   - Mark as "Ready for review" to trigger deployment

2. **Add `[skip ci]` to commit message:**
   ```bash
   git commit -m "docs: update README [skip ci]"
   ```

3. **Close PR temporarily:**
   - Closes PR = cleanup triggered
   - Reopen PR = new deployment

---

## Monitoring and Metrics

### What to Monitor

- **Deployment Success Rate:** Target >95%
- **Health Check Pass Rate:** Target >98%
- **Average Deployment Time:** Target <5 minutes
- **Preview Environment Lifetime:** Average 2-3 days

### Railway Dashboard Metrics

View in Railway Dashboard:
1. Deployment history per service
2. Resource usage (CPU, memory, network)
3. Logs and error tracking
4. Build times and durations

### GitHub Actions Insights

View in repository:
1. Actions → Workflows → preview-deploy.yml
2. Check success/failure rate
3. View average run duration
4. Identify bottlenecks

---

## Cost Management

### Monthly Budget Estimation

| Scenario | PRs/Month | Avg Days Active | Estimated Cost |
|----------|-----------|-----------------|----------------|
| Low activity | 5 | 2 days | ~$5 (Free tier) |
| Medium activity | 15 | 3 days | ~$22.50 |
| High activity | 30 | 4 days | ~$60 |

**Production cost is additional:** ~$23/month

### Cost Reduction Strategies

1. **Auto-cleanup enabled** ✅ (already implemented)
2. **Ignore documentation changes** ✅ (paths-ignore configured)
3. **Cancel in-progress deployments** ✅ (concurrency configured)
4. **Use Draft PRs for WIP** (manual)
5. **Close stale PRs** (manual)

---

## Migration from Manual Testing

### Before (Manual Testing)

```
1. Developer: "Please test my branch"
2. Reviewer: git fetch && git checkout feature-branch
3. Reviewer: pip install -r requirements.txt
4. Reviewer: python -m uvicorn src.api.main:app
5. Reviewer: Manual testing on localhost
6. Reviewer: Switch back to main branch
```

**Time:** ~15-30 minutes per review

### After (Preview Deployments)

```
1. Developer: Opens PR
2. GitHub Actions: Deploys preview automatically
3. Reviewer: Click preview URL in PR comment
4. Reviewer: Test live API in browser
```

**Time:** ~2-5 minutes per review

**Savings:** 10-25 minutes per PR × 20 PRs/month = **200-500 minutes/month**

---

## Next Steps

After successful preview deployment setup:

1. ✅ Test first preview deployment on a real PR
2. ✅ Verify cleanup workflow on PR close
3. ✅ Monitor Railway costs for first month
4. ✅ Add integration tests (next phase)
5. ✅ Set up monitoring/alerting for production (future)

---

## Support

- Railway Documentation: [docs.railway.app](https://docs.railway.app)
- Railway Discord: [discord.gg/railway](https://discord.gg/railway)
- Project Issues: [github.com/edri2or-commits/project38-or/issues](https://github.com/edri2or-commits/project38-or/issues)
- Workflow Issues: Check GitHub Actions logs
