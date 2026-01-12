# Railway Deployment Setup Guide

Complete guide for deploying project38-or to Railway.

---

## Prerequisites

1. **Railway Account** - Create at [railway.app](https://railway.app)
2. **Railway API Token** - Generate from Railway dashboard
3. **GCP Secret Manager Access** - For storing Railway API token
4. **PostgreSQL Database** - Will be provisioned on Railway

---

## Step 1: Create Railway Project

### 1.1 Create New Project

1. Log in to [Railway Dashboard](https://railway.app/dashboard)
2. Click **New Project**
3. Select **Deploy from GitHub repo**
4. Connect your GitHub account
5. Select `edri2or-commits/project38-or`
6. Railway will detect Python project automatically

### 1.2 Add PostgreSQL Database

1. In your Railway project, click **New**
2. Select **Database** → **PostgreSQL**
3. Railway will provision a PostgreSQL instance
4. Connection string is auto-available as `DATABASE_URL`

### 1.3 Get Project IDs

```bash
# From Railway dashboard
# Settings → General

PROJECT_ID="your-project-id-here"
ENVIRONMENT_ID="your-environment-id-here"  # Usually "production"
```

**Save these IDs** - you'll need them for GitHub Actions.

---

## Step 2: Configure Environment Variables

### 2.1 Railway Dashboard

Go to **Variables** tab and set:

| Variable | Value | Description |
|----------|-------|-------------|
| `PYTHONPATH` | `/app` | Python module path |
| `DATABASE_URL` | *auto-provided* | PostgreSQL connection |
| `PORT` | *auto-provided* | Railway assigns port |
| `ENVIRONMENT` | `production` | Environment name |

### 2.2 GCP Secrets (Accessed via Secret Manager)

The application will fetch these from GCP Secret Manager:

| Secret Name | Purpose |
|-------------|---------|
| `ANTHROPIC-API` | Claude API key |
| `OPENAI-API` | OpenAI API key (if used) |
| `TELEGRAM-BOT-TOKEN` | Telegram notifications |
| `N8N-API` | n8n automation |

**Note:** Railway does NOT have direct access to GCP secrets. The application fetches them at runtime using WIF authentication.

---

## Step 3: Store Railway API Token in GCP

### 3.1 Get Railway API Token

1. Go to [Railway Account Settings](https://railway.app/account/tokens)
2. Click **Create New Token**
3. Name it: `project38-deployment`
4. Copy the token (starts with `railway_...`)

### 3.2 Add to GCP Secret Manager

```bash
# Using gcloud CLI
echo -n "railway_YOUR_TOKEN_HERE" | gcloud secrets create RAILWAY-API \
  --data-file=- \
  --project=project38-483612 \
  --replication-policy="automatic"

# Grant access to service account
gcloud secrets add-iam-policy-binding RAILWAY-API \
  --member="serviceAccount:claude-code-agent@project38-483612.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=project38-483612
```

### 3.3 Verify Token

```bash
# Test access
gcloud secrets versions access latest \
  --secret="RAILWAY-API" \
  --project=project38-483612
```

---

## Step 4: Update GitHub Actions Workflow

### 4.1 Edit `.github/workflows/deploy-railway.yml`

Replace placeholders:

```yaml
# Line 100-101
RESPONSE=$(curl -s -X POST \
  "https://backboard.railway.app/graphql" \
  -H "Authorization: Bearer $RAILWAY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { deploymentTrigger(projectId: \"YOUR_PROJECT_ID\", environmentId: \"YOUR_ENV_ID\") { id status } }"
  }')
```

**Replace:**
- `YOUR_PROJECT_ID` → Your Railway project ID
- `YOUR_ENV_ID` → Your Railway environment ID (usually `production`)

### 4.2 Update Health Check URL

```yaml
# Line 122
RAILWAY_URL="https://project38-or-production.up.railway.app"  # Your actual URL
```

Get your Railway URL from: **Settings** → **Networking** → **Public Networking**

---

## Step 5: Configure Railway Build

### 5.1 Verify `railway.toml`

File should exist at project root:

```toml
[build]
builder = "NIXPACKS"
buildCommand = "pip install -r requirements.txt"

[deploy]
startCommand = "uvicorn src.api.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 100
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
```

### 5.2 Verify `Procfile`

```
web: uvicorn src.api.main:app --host 0.0.0.0 --port $PORT
```

Railway will auto-detect and use these files.

---

## Step 6: Initial Deployment (Manual)

### 6.1 Test Deployment from Railway Dashboard

1. Go to your Railway project
2. Click **Deployments** tab
3. Click **Deploy** → Deploy latest from `main`
4. Watch logs for errors

### 6.2 Verify Health Check

```bash
curl https://your-app.up.railway.app/health

# Expected response:
{
  "status": "healthy",
  "version": "1.0.0",
  "database": "connected"
}
```

### 6.3 Check Application Logs

```bash
# From Railway dashboard
# Deployments → Click on active deployment → View Logs

# Or via Railway CLI
railway logs
```

---

## Step 7: Run Database Migrations

### 7.1 Connect to Railway PostgreSQL

```bash
# From Railway dashboard: Database → Connect → Copy connection string
export DATABASE_URL="postgresql://user:pass@host:port/database"

# Run migrations (if any)
# alembic upgrade head  # (future)
```

### 7.2 Initialize TimescaleDB Extension

```sql
-- Connect via psql or Railway dashboard
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Verify
SELECT * FROM pg_extension WHERE extname = 'timescaledb';
```

### 7.3 Create Observability Tables

```bash
# From project root
psql $DATABASE_URL < sql/observability_schema.sql
```

---

## Step 8: Automated Deployments via GitHub Actions

### 8.1 Trigger Deployment

```bash
# From GitHub repository
# Actions → Deploy to Railway → Run workflow

# Select:
# - Branch: main
# - Environment: production
```

### 8.2 Deployment Flow

1. **Pre-deployment Checks**
   - ✅ Lint (ruff)
   - ✅ Tests (pytest)
   - ✅ Documentation (mkdocs)

2. **Deploy**
   - Fetch Railway API token from GCP
   - Trigger Railway deployment via GraphQL API
   - Wait for deployment

3. **Health Check**
   - Verify `/health` endpoint returns 200
   - Validate database connection

4. **Rollback** (if deployment fails)
   - Automatic rollback to previous version

---

## Step 9: Monitoring & Logs

### 9.1 Railway Dashboard

- **Metrics**: View CPU, memory, network usage
- **Logs**: Real-time application logs
- **Deployments**: History of all deployments

### 9.2 Observability Endpoints

```bash
# Health check
curl https://your-app.up.railway.app/health

# Metrics summary
curl https://your-app.up.railway.app/metrics/summary

# Agent metrics
curl https://your-app.up.railway.app/metrics/agents
```

### 9.3 OpenTelemetry (Phase 2)

Future: Export traces to Honeycomb, DataDog, or Grafana Cloud.

---

## Troubleshooting

### Issue: Deployment Fails with "Build Error"

**Solution:**
1. Check Railway build logs
2. Verify `requirements.txt` dependencies
3. Ensure Python 3.11+ is specified

### Issue: Health Check Returns 503

**Solution:**
1. Check application logs for startup errors
2. Verify `DATABASE_URL` is set correctly
3. Test database connection:
   ```python
   from src.api.database import check_database_connection
   await check_database_connection()
   ```

### Issue: Can't Connect to GCP Secret Manager

**Solution:**
1. Verify WIF configuration (see `CLAUDE.md`)
2. Check service account permissions
3. Test locally:
   ```bash
   gcloud secrets versions access latest --secret="ANTHROPIC-API"
   ```

### Issue: Railway API Token Invalid

**Solution:**
1. Regenerate token from Railway dashboard
2. Update GCP secret:
   ```bash
   echo -n "new_token" | gcloud secrets versions add RAILWAY-API --data-file=-
   ```

---

## Security Notes

1. **Secrets Management**
   - ✅ Use GCP Secret Manager (NOT Railway environment variables)
   - ✅ Secrets fetched at runtime via WIF
   - ✅ No secrets in code or logs

2. **Database**
   - ✅ PostgreSQL uses TLS by default on Railway
   - ✅ Connection string never logged
   - ✅ Use connection pooling (`pool_pre_ping=True`)

3. **API Keys**
   - ✅ Railway API token stored in GCP (not GitHub Secrets)
   - ✅ GitHub Actions uses WIF (no long-lived credentials)
   - ✅ Tokens auto-masked in logs

---

## Cost Estimation (Railway Pricing)

| Resource | Estimated Cost | Notes |
|----------|---------------|-------|
| Hobby Plan | $5/month | Up to 500 execution hours |
| PostgreSQL | Included | Up to 1GB storage |
| Bandwidth | Included | Up to 100GB/month |
| **Total** | **~$5-10/month** | For low-traffic usage |

**Pro Tier** ($20/month) recommended for production:
- Dedicated resources
- Custom domains
- Priority support

---

## Next Steps

After deployment:
1. ✅ Set up custom domain (optional)
2. ✅ Configure CORS for frontend (if needed)
3. ✅ Enable auto-scaling (Pro tier)
4. ✅ Set up Grafana dashboards (Phase 3.5)
5. ✅ Implement CI/CD rollback strategy

---

## References

- [Railway Documentation](https://docs.railway.app/)
- [Railway GraphQL API](https://docs.railway.app/reference/api)
- [TimescaleDB on PostgreSQL](https://docs.timescale.com/self-hosted/latest/install/installation-docker/)
- [Uvicorn Deployment](https://www.uvicorn.org/deployment/)
