# Maintenance Runbook

**Last Updated**: 2026-01-14
**Status**: Post-Launch Maintenance Phase (Week 1)
**Owner**: Autonomous Claude Agent

---

## Table of Contents

1. [Overview](#overview)
2. [Daily Operations](#daily-operations)
3. [Weekly Operations](#weekly-operations)
4. [Monthly Operations](#monthly-operations)
5. [Monitoring Procedures](#monitoring-procedures)
6. [Performance Tuning](#performance-tuning)
7. [Incident Response](#incident-response)
8. [Maintenance Scripts](#maintenance-scripts)

---

## Overview

This runbook provides operational procedures for maintaining the project38-or autonomous AI system in production. The system consists of:

- **Railway**: Infrastructure and deployment platform
- **GitHub**: Source code and CI/CD
- **n8n**: Workflow orchestration
- **GCP Secret Manager**: Secrets management

**Production URL**: https://or-infra.com

---

## Daily Operations

### 1. Health Check Verification

```bash
# Check production health
curl -s https://or-infra.com/api/health | jq .

# Expected response:
# {
#   "status": "healthy",
#   "version": "0.1.0",
#   "database": "connected",
#   "timestamp": "2026-01-14T..."
# }
```

**If status is "degraded"**:
1. Check database connectivity
2. Review Railway logs
3. Restart service if necessary

### 2. Metrics Review

```bash
# System metrics
curl -s https://or-infra.com/metrics/system | jq .

# Summary metrics
curl -s https://or-infra.com/metrics/summary | jq .
```

**Key metrics to monitor**:
- `cpu_percent` < 80%
- `memory_percent` < 85%
- `disk_percent` < 90%
- Deployment success rate > 95%

### 3. Railway Logs Check

```bash
# Using Railway CLI
railway logs --service web --environment production --tail 100

# Or via Railway Dashboard
# https://railway.app/project/95ec21cc-9ada-41c5-8485-12f9a00e0116
```

**Look for**:
- ERROR level logs
- Authentication failures
- Database connection issues
- Rate limit warnings

### 4. GitHub Actions Status

```bash
# Check recent workflow runs
gh run list --repo edri2or-commits/project38-or --limit 10

# Check for failed runs
gh run list --repo edri2or-commits/project38-or --status failure
```

**Automated Health Check**:
- Runs every 6 hours via `production-health-check.yml`
- Auto-creates issues on failures

---

## Weekly Operations

### 1. Dependency Security Audit

```bash
# Run pip-audit for vulnerabilities
pip-audit

# Check for outdated packages
pip list --outdated
```

**Action required if**:
- CRITICAL or HIGH severity vulnerabilities found
- Dependencies more than 2 minor versions behind

### 2. Performance Review

Check the following metrics over the past week:

| Metric | Target | Action if Exceeded |
|--------|--------|-------------------|
| Average response time | < 500ms | Review slow endpoints |
| Error rate | < 1% | Investigate error patterns |
| Deployment time | < 5 min | Check build optimizations |
| OODA cycle time | < 5s | Review observation sources |

### 3. Cost Review

Monitor Railway usage:
1. Go to Railway Dashboard → Usage
2. Check current month spending
3. Compare against budget ($20/month Pro Plan)

**Alert thresholds**:
- Warning: 80% of budget
- Critical: 90% of budget

### 4. Log Analysis

Review structured JSON logs for patterns:

```bash
# Search for error patterns
railway logs --service web | grep '"level":"ERROR"'

# Count errors by type
railway logs --service web | jq 'select(.level == "ERROR") | .message' | sort | uniq -c
```

---

## Monthly Operations

### 1. Security Token Rotation

**Rotation Schedule**:

| Secret | Rotation Interval | Last Rotated |
|--------|-------------------|--------------|
| RAILWAY-API | 90 days | Check GCP |
| N8N-API | 180 days | Check GCP |
| github-app-private-key | 365 days | Check GCP |
| TELEGRAM-BOT-TOKEN | As needed | - |

**Rotation Procedure**:

```bash
# 1. Generate new token in service dashboard
# 2. Update in GCP Secret Manager
gcloud secrets versions add <SECRET_NAME> --data-file=-

# 3. Trigger Railway redeploy (picks up new secret)
gh workflow run deploy-railway.yml

# 4. Verify new token works
curl -s https://or-infra.com/api/health
```

### 2. GCP Audit Log Review

```bash
# Review Secret Manager access logs
gcloud logging read 'protoPayload.serviceName="secretmanager.googleapis.com"' \
  --project=project38-483612 \
  --limit=100 \
  --format=json | jq '.[] | {timestamp, method: .protoPayload.methodName, user: .protoPayload.authenticationInfo.principalEmail}'
```

**Look for**:
- Unexpected access patterns
- Failed authentication attempts
- Access from unknown principals

### 3. GitHub App Permissions Review

1. Go to https://github.com/settings/apps
2. Review installed permissions
3. Verify minimal required permissions:
   - Contents: Read and write
   - Pull requests: Read and write
   - Workflows: Read and write
   - Issues: Read and write

### 4. Backup Verification

```bash
# Verify PostgreSQL backups exist
# Railway provides automatic daily backups
# Check Railway Dashboard → Database → Backups

# Test restore procedure (staging only)
# See docs/deployment.md Emergency Procedures
```

### 5. Documentation Update

- Review and update CLAUDE.md if structure changed
- Update JOURNEY.md with major milestones
- Create ADR if architectural decisions made
- Update changelog with all changes

---

## Monitoring Procedures

### Automated Monitoring

| System | Method | Frequency |
|--------|--------|-----------|
| Health endpoint | `production-health-check.yml` | Every 6 hours |
| CI/CD workflows | GitHub Actions | On every push |
| Secrets access | GCP Cloud Logging | Continuous |
| Railway metrics | Railway Dashboard | Real-time |

### Manual Monitoring Checklist

- [ ] Health endpoint returns 200
- [ ] Database connection active
- [ ] Memory usage < 85%
- [ ] No ERROR logs in last 24h
- [ ] All CI workflows passing
- [ ] No open production issues

### Alert Escalation

| Severity | Response Time | Action |
|----------|---------------|--------|
| Critical | 5 minutes | Rollback, create issue |
| High | 30 minutes | Investigate, fix |
| Medium | 4 hours | Schedule fix |
| Low | 24 hours | Track in backlog |

---

## Performance Tuning

### Week 1 Tuning Tasks

Based on the implementation roadmap, focus on:

1. **Polling Intervals**
   - OODA cycle interval: Default 60s, adjust based on load
   - Health check interval: Default 30s
   - Token refresh: 5 minutes before expiration

2. **Timeout Values**
   - Deployment timeout: 600s (10 min)
   - API request timeout: 30s
   - Database connection timeout: 10s

3. **Retry Configuration**
   - Max retries: 5
   - Exponential backoff: 2^n seconds
   - Max wait: 60s

### Optimization Opportunities

| Area | Current | Target | Action |
|------|---------|--------|--------|
| OODA cycle | ~3s | < 2s | Parallel observations |
| Deployment | ~3 min | < 2 min | Build caching |
| Webhook response | < 1s | < 500ms | Request batching |

---

## Incident Response

### Severity Levels

- **Critical**: Production down, data loss risk
- **High**: Degraded performance, functionality impaired
- **Medium**: Non-critical feature broken
- **Low**: Minor issue, workaround available

### Response Procedure

1. **Identify**: Check health endpoint, logs, metrics
2. **Contain**: Rollback if needed, isolate issue
3. **Investigate**: Review logs, identify root cause
4. **Resolve**: Apply fix, verify resolution
5. **Document**: Update runbook, create ADR if needed

### Rollback Procedure

```bash
# Option 1: Railway Dashboard
# Go to Deployments → Select previous → Redeploy

# Option 2: Railway CLI
railway redeploy <previous-deployment-id>

# Option 3: GitHub Actions
gh workflow run deploy-railway.yml -f rollback=true
```

---

## Maintenance Scripts

### Health Check Script

```bash
#!/bin/bash
# scripts/health-check.sh

PROD_URL="https://or-infra.com"

echo "Checking production health..."

HEALTH=$(curl -s "$PROD_URL/api/health")
STATUS=$(echo $HEALTH | jq -r '.status')
DATABASE=$(echo $HEALTH | jq -r '.database')

if [ "$STATUS" = "healthy" ] && [ "$DATABASE" = "connected" ]; then
    echo "✅ Production healthy"
    exit 0
else
    echo "❌ Production unhealthy: $HEALTH"
    exit 1
fi
```

### Metrics Collection Script

```bash
#!/bin/bash
# scripts/collect-metrics.sh

PROD_URL="https://or-infra.com"

echo "=== System Metrics ==="
curl -s "$PROD_URL/metrics/system" | jq .

echo ""
echo "=== Summary Metrics ==="
curl -s "$PROD_URL/metrics/summary" | jq .

echo ""
echo "=== Health Status ==="
curl -s "$PROD_URL/api/health" | jq .
```

### Log Analysis Script

```bash
#!/bin/bash
# scripts/analyze-logs.sh

echo "=== Error Summary (Last 24h) ==="
railway logs --service web --environment production | \
    jq 'select(.level == "ERROR")' | \
    jq -r '.message' | \
    sort | uniq -c | sort -rn | head -10

echo ""
echo "=== Warning Summary ==="
railway logs --service web --environment production | \
    jq 'select(.level == "WARNING")' | \
    jq -r '.message' | \
    sort | uniq -c | sort -rn | head -10
```

---

## Quick Reference

### Key URLs

| Service | URL |
|---------|-----|
| Production | https://or-infra.com |
| Health Check | https://or-infra.com/api/health |
| Metrics | https://or-infra.com/metrics/summary |
| Railway Dashboard | https://railway.app/project/95ec21cc-9ada-41c5-8485-12f9a00e0116 |
| GitHub Repo | https://github.com/edri2or-commits/project38-or |

### Key Commands

```bash
# Health check
curl -s https://or-infra.com/api/health | jq .

# Railway logs
railway logs --service web --environment production

# GitHub workflow status
gh run list --repo edri2or-commits/project38-or

# GCP secrets list
gcloud secrets list --project=project38-483612
```

### Emergency Contacts

- **Railway Support**: https://railway.app/help
- **GCP Support**: https://cloud.google.com/support
- **GitHub Issues**: https://github.com/edri2or-commits/project38-or/issues

---

*This runbook should be reviewed and updated monthly or after any significant incident.*
