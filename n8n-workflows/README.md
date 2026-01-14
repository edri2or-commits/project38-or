# n8n Autonomous Workflows

Workflows for autonomous Railway management via n8n.

## Overview

These workflows enable **autonomous operations** without manual intervention:

| Workflow | Purpose | Trigger |
|----------|---------|---------|
| `01-railway-health-monitor.json` | Monitor production health | Cron (every 5 min) |
| `02-deployment-trigger.json` | Auto-deploy on push to main | GitHub Webhook |
| `03-auto-rollback.json` | Rollback failed deployments | Webhook / Manual |

## Architecture

```
GitHub (push) ──────────────────────────────────────────────┐
                                                            │
                                                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                           n8n                                    │
│                                                                  │
│   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐     │
│   │    Health     │   │   Deployment  │   │   Rollback    │     │
│   │   Monitor     │   │    Trigger    │   │    Agent      │     │
│   │  (5 min cron) │   │  (webhook)    │   │  (webhook)    │     │
│   └───────┬───────┘   └───────┬───────┘   └───────┬───────┘     │
│           │                   │                   │              │
│           ▼                   ▼                   ▼              │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                   Railway API                            │   │
│   │            (GraphQL at backboard.railway.app)            │   │
│   └─────────────────────────────────────────────────────────┘   │
│           │                   │                   │              │
│           ▼                   ▼                   ▼              │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                    Notifications                         │   │
│   │              (Telegram + GitHub Issues)                  │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

### 1. n8n Instance

Deploy n8n on Railway using the template:
```
https://railway.app/new/template/n8n
```

Or self-host using Docker:
```bash
docker run -it --rm \
  -p 5678:5678 \
  -e N8N_BASIC_AUTH_ACTIVE=true \
  -e N8N_BASIC_AUTH_USER=admin \
  -e N8N_BASIC_AUTH_PASSWORD=<password> \
  n8nio/n8n
```

### 2. Required Credentials

Configure these credentials in n8n:

| Credential Name | Type | Value |
|-----------------|------|-------|
| `Telegram Bot` | Telegram API | Bot token from @BotFather |
| `GitHub PAT` | GitHub API | Fine-grained PAT with `issues:write` |
| `Railway API Token` | HTTP Header Auth | `Authorization: Bearer <token>` |

### 3. Environment Variables

Set these in n8n Settings → Variables:

| Variable | Value |
|----------|-------|
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID |
| `RAILWAY_SERVICE_ID` | `<your-service-id>` |
| `RAILWAY_ENVIRONMENT_ID` | `99c99a18-aea2-4d01-9360-6a93705102a0` |

## Installation

### Step 1: Import Workflows

1. Open n8n
2. Go to **Workflows** → **Import from File**
3. Import each JSON file:
   - `01-railway-health-monitor.json`
   - `02-deployment-trigger.json`
   - `03-auto-rollback.json`

### Step 2: Configure Credentials

For each workflow:
1. Open the workflow
2. Click on nodes that show credential errors
3. Select or create the required credential

### Step 3: Set Environment Variables

1. Go to n8n **Settings** → **Variables**
2. Add the required variables (see table above)

### Step 4: Configure GitHub Webhook

For deployment trigger:

1. Go to GitHub repo → **Settings** → **Webhooks**
2. Add webhook:
   - **URL**: `https://<your-n8n>/webhook/deploy-railway`
   - **Content type**: `application/json`
   - **Events**: `push`
   - **Active**: Yes

### Step 5: Activate Workflows

1. Open each workflow
2. Toggle **Active** to ON
3. Save

## Workflow Details

### 01. Health Monitor

**Purpose**: Check production health every 5 minutes

**Flow**:
```
[Every 5 min] → [Check /api/health] → [Is Healthy?]
                                           │
                    ┌──────────────────────┴──────────────────────┐
                    │                                              │
                    ▼                                              ▼
            [Log Success]                              [Send Telegram Alert]
            (disabled)                                         │
                                                               ▼
                                                    [Create GitHub Issue]
```

**Customization**:
- Change interval: Edit "Every 5 Minutes" node
- Enable success notifications: Enable "Notify Success" node
- Add more alert channels: Duplicate alert nodes

### 02. Deployment Trigger

**Purpose**: Auto-deploy when code pushed to main

**Flow**:
```
[GitHub Webhook] → [Is Main Branch?] → [Yes] → [Trigger Deploy]
                          │                          │
                          │                          ▼
                          │              [Wait 60s] → [Verify Health]
                          │                                   │
                          │                    ┌──────────────┴──────────────┐
                          │                    │                              │
                          ▼                    ▼                              ▼
                    [Respond Ignored]   [Notify Success]             [Notify Failure]
```

**Customization**:
- Change wait time: Edit "Wait 60s" node
- Add pre-deploy tests: Insert HTTP Request before deploy
- Add rollback on failure: Connect failure to rollback workflow

### 03. Auto-Rollback

**Purpose**: Rollback to previous working deployment

**Flow**:
```
[Webhook Trigger] → [Get Deployments] → [Find Last Success] → [Can Rollback?]
                                                                     │
                          ┌──────────────────────────────────────────┴────┐
                          │                                               │
                          ▼                                               ▼
                   [Execute Rollback]                            [Notify Failed]
                          │
                          ▼
                   [Wait 30s] → [Verify Health] → [Notify Success]
```

**Trigger manually**:
```bash
curl -X POST https://<your-n8n>/webhook/rollback-railway \
  -H "Content-Type: application/json" \
  -d '{"reason": "Manual rollback due to bug"}'
```

## Security

### Best Practices

1. **Use HTTPS** for n8n instance
2. **Enable Basic Auth** on n8n
3. **Rotate tokens** every 90 days
4. **Restrict webhook access** using IP whitelist if possible
5. **Never log tokens** in workflow execution

### Credential Storage

All credentials should be stored in n8n's encrypted credential store, NOT in workflow JSON files.

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Webhook not receiving | Check GitHub webhook delivery logs |
| Telegram not sending | Verify bot token and chat ID |
| Railway API failing | Check token permissions, rate limits |
| Health check timing out | Increase timeout in HTTP Request node |

### Debug Mode

1. Open workflow
2. Click **Execute Workflow** manually
3. View execution logs for each node

### Logs

View n8n execution logs:
```bash
# Railway logs
railway logs --service n8n

# Docker logs
docker logs <container-id>
```

## Integration with Claude Code

These workflows extend the autonomous capabilities documented in:
- `docs/autonomous/04-n8n-orchestration-hybrid.md`
- `docs/integrations/n8n-integration.md`

**Use Case**: When Claude Code cannot directly access Railway (due to proxy), it can trigger these n8n workflows via webhook to perform autonomous operations.

## Support

- **n8n Documentation**: https://docs.n8n.io
- **Railway GraphQL API**: https://docs.railway.app/reference/graphql-api
- **Project Issues**: https://github.com/edri2or-commits/project38-or/issues
