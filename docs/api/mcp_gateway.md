# MCP Gateway API Reference

The MCP Gateway provides Claude Code with autonomous access to Railway and n8n operations through the Model Context Protocol (MCP).

## Overview

The MCP Gateway is a Remote MCP Server that bridges Claude Code to infrastructure services that are normally blocked by the Anthropic proxy.

```
Claude Code → MCP Protocol → MCP Gateway (Railway) → Railway API / n8n
```

## Module Structure

```
src/mcp_gateway/
├── __init__.py       # Package initialization
├── server.py         # FastMCP server with tool definitions
├── config.py         # Configuration from GCP Secret Manager
├── auth.py           # Bearer token authentication
└── tools/
    ├── railway.py    # Railway deployment operations
    ├── n8n.py        # n8n workflow operations
    └── monitoring.py # Health checks and metrics
```

## Server Module

::: src.mcp_gateway.server
    options:
        show_root_heading: true
        heading_level: 3

## Configuration Module

::: src.mcp_gateway.config
    options:
        show_root_heading: true
        heading_level: 3

## Authentication Module

::: src.mcp_gateway.auth
    options:
        show_root_heading: true
        heading_level: 3

## Railway Tools

::: src.mcp_gateway.tools.railway
    options:
        show_root_heading: true
        heading_level: 3

## n8n Tools

::: src.mcp_gateway.tools.n8n
    options:
        show_root_heading: true
        heading_level: 3

## Monitoring Tools

::: src.mcp_gateway.tools.monitoring
    options:
        show_root_heading: true
        heading_level: 3

## Available MCP Tools

| Tool | Description |
|------|-------------|
| `railway_deploy` | Trigger a new Railway deployment |
| `railway_status` | Get current deployment status |
| `railway_deployments` | List recent deployments |
| `railway_rollback` | Rollback to previous deployment |
| `n8n_trigger` | Trigger an n8n workflow |
| `n8n_list` | List available workflows |
| `n8n_status` | Check workflow webhook status |
| `health_check` | Check all service health |
| `get_metrics` | Get system metrics |
| `deployment_health` | Comprehensive health + deployment check |

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `RAILWAY_SERVICE_ID` | Yes | Railway service ID for deployments |
| `RAILWAY_ENVIRONMENT_ID` | No | Environment ID (default: production) |
| `RAILWAY_PROJECT_ID` | No | Railway project ID |
| `N8N_BASE_URL` | No | n8n instance base URL |
| `PRODUCTION_URL` | No | Production app URL for health checks |
| `MCP_PORT` | No | Port for standalone server (default: 8080) |
| `MCP_HOST` | No | Host for standalone server (default: 0.0.0.0) |

### GCP Secrets

| Secret | Purpose |
|--------|---------|
| `RAILWAY-API` | Railway API token |
| `N8N-API` | n8n API key |
| `MCP-GATEWAY-TOKEN` | Bearer token for MCP authentication |

## Usage

### Standalone Server

```bash
python -m src.mcp_gateway.server
```

### Mount in FastAPI

```python
from fastapi import FastAPI
from src.mcp_gateway.server import create_mcp_app

app = FastAPI()
mcp_app = create_mcp_app()
if mcp_app:
    app.mount("/mcp", mcp_app)
```

### Claude Code Configuration

```bash
claude mcp add \
  --transport http \
  --header "Authorization: Bearer <MCP-GATEWAY-TOKEN>" \
  --scope user \
  claude-gateway \
  https://or-infra.com/mcp
```

## Security

- All requests require bearer token authentication
- Tokens stored in GCP Secret Manager
- HTTPS transport via Railway
- Rate limiting recommended for production

See [MCP Gateway Architecture](../autonomous/08-mcp-gateway-architecture.md) for detailed security design.
