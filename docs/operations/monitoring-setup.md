# Production Monitoring Setup

This document describes how to set up and configure production monitoring for the Agent Platform.

## Monitoring Components

### 1. GitHub Actions Uptime Monitor

**Workflow:** `.github/workflows/uptime-monitor.yml`

Automatic health checks every 5 minutes:
- Checks `/api/health` endpoint
- Creates GitHub issues on failures
- Auto-closes issues when resolved
- Records response time metrics

**Manual trigger:**
```bash
gh workflow run uptime-monitor.yml
```

### 2. External Monitoring (Recommended)

For true external monitoring, set up one of these services:

#### Option A: UptimeRobot (Free)

1. Sign up at https://uptimerobot.com
2. Create new monitor:
   - Monitor Type: HTTP(s)
   - Friendly Name: `Agent Platform Production`
   - URL: `https://or-infra.com/api/health`
   - Monitoring Interval: 5 minutes

3. Configure alerts:
   - Email notifications
   - Telegram bot (see below)
   - Webhook to n8n

#### Option B: Healthchecks.io (Free)

1. Sign up at https://healthchecks.io
2. Create new check:
   - Name: `Agent Platform Health`
   - Period: 5 minutes
   - Grace: 5 minutes

3. Ping from GitHub Actions:
   ```yaml
   - name: Ping Healthchecks.io
     if: success()
     run: curl -fsS --retry 3 ${{ secrets.HEALTHCHECKS_URL }}
   ```

#### Option C: Better Uptime

1. Sign up at https://betteruptime.com
2. Create monitor for `https://or-infra.com/api/health`
3. Configure incident management

## Alert Channels

### Telegram Notifications

1. **Create Bot:**
   ```bash
   # Message @BotFather on Telegram
   /newbot
   # Follow prompts to get BOT_TOKEN
   ```

2. **Get Chat ID:**
   ```bash
   # Start chat with your bot, then:
   curl https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
   # Find chat.id in response
   ```

3. **Store in GCP Secret Manager:**
   ```bash
   echo -n "YOUR_BOT_TOKEN" | gcloud secrets create TELEGRAM-BOT-TOKEN --data-file=-
   ```

4. **Send alert (Python):**
   ```python
   import httpx

   async def send_telegram_alert(message: str):
       token = get_secret("TELEGRAM-BOT-TOKEN")
       chat_id = get_secret("TELEGRAM-CHAT-ID")

       await httpx.post(
           f"https://api.telegram.org/bot{token}/sendMessage",
           json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
       )
   ```

### n8n Webhook Alerts

1. **Create n8n Workflow:**
   - Trigger: Webhook
   - Action: Send Telegram/Email/Slack

2. **Configure webhook URL:**
   - Store in `N8N-WEBHOOK-URL` secret
   - Call from alert workflow

3. **Example payload:**
   ```json
   {
     "event": "outage",
     "service": "agent-platform",
     "status": "unhealthy",
     "timestamp": "2026-01-15T12:00:00Z",
     "response_time_ms": 5000,
     "error": "Connection timeout"
   }
   ```

## Metrics Dashboard

### Key Metrics to Monitor

| Metric | Warning | Critical | Source |
|--------|---------|----------|--------|
| Response Time | > 1000ms | > 3000ms | `/api/health` |
| Error Rate | > 1% | > 5% | Application logs |
| CPU Usage | > 70% | > 90% | Railway metrics |
| Memory Usage | > 80% | > 95% | Railway metrics |
| Database Connections | > 15 | > 19 | PostgreSQL |

### Railway Dashboard

Access at: https://railway.app/project/95ec21cc-9ada-41c5-8485-12f9a00e0116

Monitor:
- Deployment status
- Resource usage (CPU, Memory)
- Network traffic
- Logs

### Custom Metrics Endpoint

**GET /metrics/summary**

Returns:
```json
{
  "total_requests": 1234,
  "error_count": 5,
  "avg_response_time_ms": 45.2,
  "active_agents": 10,
  "pending_tasks": 3
}
```

**GET /metrics/system**

Returns:
```json
{
  "cpu_percent": 25.5,
  "memory_percent": 60.2,
  "disk_percent": 45.0,
  "uptime_seconds": 86400
}
```

## Incident Response

### Severity Levels

| Level | Response Time | Examples |
|-------|---------------|----------|
| P1 - Critical | 15 minutes | Complete outage, data loss |
| P2 - High | 1 hour | Degraded performance, partial outage |
| P3 - Medium | 4 hours | Non-critical feature failure |
| P4 - Low | 24 hours | Minor issues, cosmetic bugs |

### Escalation Path

1. **Automatic Detection**
   - Uptime monitor creates GitHub issue
   - Telegram alert sent

2. **Initial Response**
   - Check Railway dashboard
   - Review recent deployments
   - Check database status

3. **Remediation**
   - Rollback if recent deployment
   - Restart service if hung
   - Scale up if overloaded

4. **Post-Incident**
   - Update issue with resolution
   - Document in incident log
   - Schedule post-mortem if P1/P2

## Quick Commands

```bash
# Check current health
curl https://or-infra.com/api/health | jq

# View recent workflow runs
gh run list --workflow=uptime-monitor.yml --limit=10

# Trigger manual health check
gh workflow run uptime-monitor.yml

# View Railway logs
railway logs --service web

# Rollback deployment
gh workflow run deploy-railway.yml
# Then use Railway dashboard to rollback
```

## Maintenance Windows

To suppress alerts during planned maintenance:

1. Create `maintenance` label in GitHub
2. Add to open outage issues before maintenance
3. Workflow will skip alerting for labeled issues

Or use the AlertManager maintenance window feature:
```python
from src.alert_manager import AlertManager

manager = AlertManager()
manager.add_maintenance_window(
    start=datetime.now(),
    end=datetime.now() + timedelta(hours=2),
    reason="Database migration"
)
```
