# Disaster Recovery Plan - project38-or

**Document Version**: 1.0
**Last Updated**: 2026-01-14
**Owner**: Infrastructure Team
**Status**: Active

---

## Executive Summary

This document outlines the disaster recovery (DR) procedures for the project38-or autonomous AI system, including PostgreSQL database restoration, application recovery, and service continuity strategies.

**Recovery Time Objective (RTO)**: < 15 minutes
**Recovery Point Objective (RPO)**: < 24 hours (daily backups)

---

## Table of Contents

1. [Backup System Overview](#backup-system-overview)
2. [Disaster Scenarios](#disaster-scenarios)
3. [Recovery Procedures](#recovery-procedures)
4. [Testing & Validation](#testing--validation)
5. [Contacts & Escalation](#contacts--escalation)
6. [Appendix](#appendix)

---

## Backup System Overview

### Backup Schedule

| Backup Type | Frequency | Retention | Storage Location |
|-------------|-----------|-----------|------------------|
| **Automated Full Backup** | Daily at 00:00 UTC | 30 days | GCS: `project38-backups` |
| **Manual Backup** | On-demand | 30 days | GCS: `project38-backups` |
| **Verification Check** | Weekly (Sunday) | N/A | Automated workflow |

### Backup Architecture

```
PostgreSQL Database (Railway)
    ↓
pg_dump (full SQL dump)
    ↓
gzip compression
    ↓
SHA256 checksum calculation
    ↓
GCS Upload (encrypted)
    ↓
Verification & Metadata Storage
    ↓
Telegram Notification
```

### Backup Metadata

Each backup includes:
- **Backup ID**: Unique timestamp-based identifier
- **Database Name**: Source database
- **Size**: Compressed backup size (MB)
- **Checksum**: SHA256 hash for integrity
- **GCS Path**: Cloud Storage location
- **pg_dump Version**: PostgreSQL dump version
- **Created At**: Timestamp (ISO 8601)
- **Expiry Date**: When backup will be deleted

### Monitoring

- **Automated Health Checks**: Every 6 hours (production-health-check.yml)
- **Backup Success Notifications**: Telegram alerts on completion
- **Failure Alerts**: Immediate Telegram alerts on backup failure

---

## Disaster Scenarios

### Scenario 1: Database Corruption

**Symptoms:**
- Application errors: "database connection failed"
- Data integrity issues
- PostgreSQL crashes repeatedly

**Impact:**
- **Critical**: Application unavailable
- **RTO**: 15 minutes (database restore)
- **RPO**: Last successful backup (< 24 hours)

**Recovery**: [Procedure DR-1](#dr-1-database-restore)

---

### Scenario 2: Accidental Data Deletion

**Symptoms:**
- Users report missing data
- Tables unexpectedly empty
- Accidental `DELETE` or `DROP` executed

**Impact:**
- **High**: Data loss
- **RTO**: 30 minutes (partial restore)
- **RPO**: Last successful backup

**Recovery**: [Procedure DR-2](#dr-2-partial-data-restore)

---

### Scenario 3: Railway Complete Outage

**Symptoms:**
- Railway dashboard inaccessible
- All services down
- Deployment failures

**Impact:**
- **Critical**: Complete service unavailable
- **RTO**: 2-4 hours (deploy to new Railway project)
- **RPO**: Last successful backup

**Recovery**: [Procedure DR-3](#dr-3-complete-environment-rebuild)

---

### Scenario 4: GCP Secret Manager Unavailable

**Symptoms:**
- Secrets fetch failures
- Application cannot start
- "Permission denied" errors

**Impact:**
- **Critical**: Application cannot authenticate
- **RTO**: 1 hour (restore WIF bindings)
- **RPO**: N/A (secrets not backed up to GCS)

**Recovery**: [Procedure DR-4](#dr-4-secret-manager-recovery)

---

## Recovery Procedures

### DR-1: Database Restore

**When to use**: Database corruption, complete data loss

**Prerequisites:**
- Access to GCP Cloud Storage (`project38-backups` bucket)
- Railway project access
- PostgreSQL client tools (`pg_restore`, `psql`)

**Steps:**

1. **Identify Latest Backup**
   ```bash
   # List available backups
   curl https://or-infra.com/api/backups?limit=10

   # Output:
   # {
   #   "count": 10,
   #   "backups": [
   #     {
   #       "backup_id": "backup-testdb-20260114-000000",
   #       "created_at": "2026-01-14T00:00:00Z",
   #       "size_mb": 50.0,
   #       "gcs_path": "gs://project38-backups/backups/backup-testdb-20260114-000000.sql.gz"
   #     }
   #   ]
   # }
   ```

2. **Download Backup from GCS**
   ```bash
   # Download compressed backup
   gsutil cp gs://project38-backups/backups/backup-testdb-20260114-000000.sql.gz ./

   # Decompress
   gunzip backup-testdb-20260114-000000.sql.gz

   # Result: backup-testdb-20260114-000000.sql
   ```

3. **Verify Backup Integrity**
   ```bash
   # Calculate checksum
   sha256sum backup-testdb-20260114-000000.sql.gz

   # Compare with metadata
   curl https://or-infra.com/api/backups/verify \
     -X POST \
     -H "Content-Type: application/json" \
     -d '{"backup_id": "backup-testdb-20260114-000000"}'
   ```

4. **Restore to Railway PostgreSQL**
   ```bash
   # Get DATABASE_URL from Railway
   # Go to Railway dashboard → project → postgres → Connect → DATABASE_URL

   # Restore database
   psql $DATABASE_URL < backup-testdb-20260114-000000.sql

   # Expected output:
   # CREATE TABLE
   # CREATE INDEX
   # INSERT 0 1000
   # ...
   ```

5. **Verify Restoration**
   ```bash
   # Check table counts
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM agents;"
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM tasks;"

   # Check application health
   curl https://or-infra.com/api/health
   ```

6. **Restart Application**
   ```bash
   # Via Railway Dashboard:
   # Project → Service → Settings → Restart

   # Or via Railway CLI:
   railway restart --service web
   ```

**Verification Checklist:**
- [ ] Database connection successful
- [ ] All tables present
- [ ] Row counts match expectations
- [ ] Application health check returns 200 OK
- [ ] Test API endpoints respond correctly

**Expected Duration**: 10-15 minutes

---

### DR-2: Partial Data Restore

**When to use**: Accidental deletion of specific records/tables

**Prerequisites:**
- Latest backup available
- Temporary database for staging

**Steps:**

1. **Create Temporary Database**
   ```bash
   # Create temp database on Railway or locally
   createdb temp_restore

   # Set temp DATABASE_URL
   export TEMP_DB_URL="postgresql://user:pass@host:5432/temp_restore"
   ```

2. **Restore Backup to Temporary Database**
   ```bash
   # Download and restore to temp DB
   gsutil cp gs://project38-backups/backups/BACKUP_ID.sql.gz ./
   gunzip BACKUP_ID.sql.gz
   psql $TEMP_DB_URL < BACKUP_ID.sql
   ```

3. **Extract Missing Data**
   ```bash
   # Example: Restore deleted agent records
   psql $TEMP_DB_URL -c "COPY (SELECT * FROM agents WHERE id IN (1,2,3)) TO STDOUT WITH CSV HEADER" > missing_agents.csv

   # Or export specific table
   pg_dump $TEMP_DB_URL -t agents --data-only > agents_data.sql
   ```

4. **Import to Production Database**
   ```bash
   # Import missing records
   psql $PRODUCTION_DB_URL < agents_data.sql

   # Or use COPY command
   psql $PRODUCTION_DB_URL -c "\COPY agents FROM 'missing_agents.csv' WITH CSV HEADER"
   ```

5. **Verify Data**
   ```bash
   # Check imported records
   psql $PRODUCTION_DB_URL -c "SELECT * FROM agents WHERE id IN (1,2,3);"
   ```

6. **Cleanup**
   ```bash
   # Drop temporary database
   dropdb temp_restore

   # Remove local files
   rm -f BACKUP_ID.sql missing_agents.csv agents_data.sql
   ```

**Expected Duration**: 20-30 minutes

---

### DR-3: Complete Environment Rebuild

**When to use**: Railway outage, project corruption, region failure

**Prerequisites:**
- GCP project access (`project38-483612`)
- Railway account access
- GitHub repository access
- Latest database backup

**Steps:**

1. **Create New Railway Project**
   ```bash
   # Via Railway Dashboard:
   # 1. New Project → Empty Project
   # 2. Name: "project38-or-recovery"
   # 3. Add PostgreSQL database

   # Or via CLI:
   railway init
   railway add postgresql
   ```

2. **Configure Environment Variables**
   ```bash
   # Set required variables in Railway
   RAILWAY_ENVIRONMENT=production
   DATABASE_URL=(auto-set by Railway)
   PORT=8000
   LOG_LEVEL=INFO
   GCS_BACKUP_BUCKET=project38-backups

   # Get from GCP Secret Manager:
   ANTHROPIC_API=(secret)
   RAILWAY_API=(secret)
   TELEGRAM_BOT_TOKEN=(secret)
   ```

3. **Restore Database**
   ```bash
   # Follow DR-1 procedure to restore database
   # Use new Railway DATABASE_URL
   ```

4. **Deploy Application**
   ```bash
   # Connect GitHub repository
   railway link

   # Deploy from main branch
   railway up

   # Or trigger via GitHub Actions:
   gh workflow run deploy-railway.yml
   ```

5. **Update DNS (if using custom domain)**
   ```bash
   # Update DNS records to point to new Railway URL
   # Railway Dashboard → Project → Settings → Domains
   ```

6. **Verify All Services**
   ```bash
   # Health check
   curl https://NEW_URL/api/health

   # Backup system
   curl https://NEW_URL/api/backups/health

   # Test backup creation
   curl https://NEW_URL/api/backups/create \
     -X POST \
     -H "Content-Type: application/json" \
     -d '{"retention_days": 30, "verify": true}'
   ```

7. **Update GitHub Variables**
   ```bash
   # Update repository variables
   gh variable set RAILWAY_PROJECT_ID --body="NEW_PROJECT_ID"
   gh variable set RAILWAY_ENVIRONMENT_ID --body="NEW_ENV_ID"
   gh variable set RAILWAY_URL --body="https://NEW_URL"
   ```

8. **Update MCP Gateway Configuration**
   ```bash
   # Update src/mcp_gateway/config.py if needed
   # Redeploy MCP Gateway
   ```

**Expected Duration**: 2-4 hours

---

### DR-4: Secret Manager Recovery

**When to use**: WIF authentication failures, Secret Manager access denied

**Prerequisites:**
- GCP project owner access
- GitHub repository admin access

**Steps:**

1. **Verify WIF Configuration**
   ```bash
   # Check WIF pool exists
   gcloud iam workload-identity-pools describe github-pool \
     --location=global \
     --project=project38-483612

   # Check provider exists
   gcloud iam workload-identity-pools providers describe github-provider \
     --workload-identity-pool=github-pool \
     --location=global \
     --project=project38-483612
   ```

2. **Verify Service Account Bindings**
   ```bash
   # Check IAM bindings
   gcloud projects get-iam-policy project38-483612 \
     --flatten="bindings[].members" \
     --filter="bindings.role:roles/secretmanager.secretAccessor"

   # Should show: claude-code-agent@project38-483612.iam.gserviceaccount.com
   ```

3. **Re-create WIF if Needed**
   ```bash
   # Follow setup guide in .github/workflows/setup-wif.md
   # Or run setup script:
   ./scripts/setup-wif.sh
   ```

4. **Test Secret Access**
   ```bash
   # Run test workflow
   gh workflow run test-wif.yml

   # Check results
   gh run list --workflow=test-wif.yml --limit=1
   ```

5. **Verify Application Secrets**
   ```bash
   # Test from Railway environment
   railway run python -c "from src.secrets_manager import SecretManager; m = SecretManager(); print(m.verify_access('ANTHROPIC-API'))"
   ```

**Expected Duration**: 30-60 minutes

---

## Testing & Validation

### Monthly DR Test Schedule

| Test Type | Frequency | Last Tested | Next Test |
|-----------|-----------|-------------|-----------|
| **DR-1: Database Restore** | Monthly | 2026-01-14 | 2026-02-14 |
| **DR-2: Partial Restore** | Quarterly | 2026-01-14 | 2026-04-14 |
| **DR-3: Environment Rebuild** | Annually | 2026-01-14 | 2027-01-14 |
| **DR-4: Secret Manager** | Quarterly | 2026-01-14 | 2026-04-14 |

### Test Procedure Template

```markdown
**DR Test Report**

- **Date**: YYYY-MM-DD
- **Test Type**: DR-X
- **Tester**: Name
- **Environment**: Production/Staging
- **Backup Used**: backup-id-timestamp

**Steps Executed:**
- [ ] Step 1: ...
- [ ] Step 2: ...
- [ ] ...

**Results:**
- RTO Actual: X minutes (Target: Y minutes)
- RPO Verified: Yes/No
- Issues Found: None / [Description]

**Lessons Learned:**
- ...

**Action Items:**
- ...
```

### Verification Checklist

After any DR procedure, verify:

- [ ] Application accessible at production URL
- [ ] Database connection healthy (`/api/health`)
- [ ] All tables present with expected row counts
- [ ] API endpoints respond correctly (test 5 endpoints)
- [ ] Backup system operational (`/api/backups/health`)
- [ ] Automated workflows running (check GitHub Actions)
- [ ] Monitoring alerts configured (Telegram notifications)
- [ ] Secrets accessible from application
- [ ] No errors in application logs (last 100 lines)
- [ ] Performance metrics within normal range

---

## Contacts & Escalation

### Incident Severity Levels

| Severity | Description | Response Time | Escalation |
|----------|-------------|---------------|------------|
| **P0 - Critical** | Complete service outage | Immediate | Owner + Team |
| **P1 - High** | Partial outage, data loss | < 1 hour | Owner |
| **P2 - Medium** | Degraded performance | < 4 hours | On-call |
| **P3 - Low** | Minor issues, no impact | < 24 hours | Team |

### Contact Information

| Role | Contact | Availability |
|------|---------|--------------|
| **Primary Owner** | edri2or@gmail.com | 24/7 |
| **Telegram Alerts** | @project38_alerts | 24/7 |
| **Railway Support** | https://railway.app/help | Business hours |
| **GCP Support** | https://cloud.google.com/support | 24/7 (paid) |

### Escalation Path

```
Incident Detected
    ↓
Severity Assessment (P0-P3)
    ↓
P0/P1: Immediate notification via Telegram
P2/P3: Create GitHub issue
    ↓
Execute DR Procedure
    ↓
Update stakeholders every 30 minutes
    ↓
Complete Recovery
    ↓
Post-Mortem within 48 hours
```

---

## Appendix

### A. Backup File Naming Convention

```
backup-{database_name}-{YYYYMMDD}-{HHMMSS}.sql.gz
```

Example: `backup-testdb-20260114-000000.sql.gz`

### B. GCS Bucket Structure

```
project38-backups/
├── backups/
│   ├── backup-testdb-20260114-000000.sql.gz
│   ├── backup-testdb-20260114-000000.json (metadata)
│   ├── backup-testdb-20260113-000000.sql.gz
│   └── backup-testdb-20260113-000000.json
└── (retention policy: 30 days auto-delete)
```

### C. Useful Commands

**Check backup age:**
```bash
# List backups older than 7 days
gsutil ls -l gs://project38-backups/backups/*.sql.gz | awk '$2 > "2026-01-07"'
```

**Calculate total backup storage:**
```bash
# Get total size
gsutil du -s gs://project38-backups/
```

**Manual backup trigger:**
```bash
# Trigger backup via API
curl https://or-infra.com/api/backups/create \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"retention_days": 90, "verify": true}'
```

### D. Related Documentation

- Backup System Source Code: `src/backup_manager.py`
- Backup API Endpoints: `src/api/routes/backups.py`
- [Railway Deployment Guide](../RAILWAY_SETUP.md)
- [Implementation Roadmap - Week 3](../integrations/implementation-roadmap.md)
- [Maintenance Runbook](../maintenance-runbook.md)

---

**Document Control:**
- **Version**: 1.0
- **Approved By**: Infrastructure Team
- **Next Review**: 2026-02-14
- **Classification**: Internal Use

