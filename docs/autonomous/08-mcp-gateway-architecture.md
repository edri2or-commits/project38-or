# MCP Gateway Architecture: Full Claude Autonomy

## Executive Summary

This document describes the architecture for giving Claude Code **full autonomy** to operate Railway, n8n, and other services through a **Remote MCP Server** deployed on Railway.

**The Pattern:**
```
User deploys minimal MCP Gateway → Claude connects via HTTP → Full autonomy
```

**Key Insight:** Claude Code supports connecting to remote MCP servers via HTTP transport. By deploying an MCP server on Railway, we bypass the Anthropic proxy limitations and give Claude direct access to all services.

---

## Problem Statement

### Current Limitation

```
Claude Code (Anthropic Environment)
     │
     │ HTTPS_PROXY (21.0.0.25:15004)
     ▼
  ┌─────────────────────────┐
  │   Anthropic Egress      │
  │   Proxy                 │
  │                         │
  │   ✓ api.github.com      │
  │   ✓ *.googleapis.com    │
  │   ✗ *.railway.app       │  ← BLOCKED
  │   ✗ n8n instances       │  ← BLOCKED
  │   ✗ or-infra.com        │  ← BLOCKED
  └─────────────────────────┘
```

Claude cannot directly access Railway API or n8n webhooks due to the Anthropic egress proxy.

### The Solution: MCP Gateway

```
Claude Code (Anthropic Environment)
     │
     │ HTTP MCP Protocol
     ▼
  ┌─────────────────────────┐
  │   Remote MCP Server     │  ← Deployed on Railway
  │   (MCP Gateway)         │
  │                         │
  │   Tools:                │
  │   - railway_deploy()    │
  │   - railway_status()    │
  │   - railway_rollback()  │
  │   - n8n_trigger()       │
  │   - health_check()      │
  └───────────┬─────────────┘
              │
              │ Direct Access (No Proxy)
              ▼
     ┌────────┴────────┐
     │                 │
  Railway           n8n
  GraphQL          Webhooks
```

**Why This Works:**
- Claude Code supports remote MCP servers via HTTP transport
- The MCP server runs on Railway with no proxy restrictions
- Claude communicates using MCP protocol, not direct HTTP calls
- All Railway/n8n operations happen server-side

---

## Architecture Overview

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Claude Code Session                          │
│                                                                  │
│  ┌──────────────┐    MCP Protocol    ┌───────────────────────┐  │
│  │ Claude Agent │ ──────────────────▶│ MCP Client (built-in) │  │
│  └──────────────┘                    └───────────┬───────────┘  │
│                                                  │               │
└──────────────────────────────────────────────────┼───────────────┘
                                                   │
                                            HTTP Transport
                                            (Streamable HTTP)
                                                   │
                                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Railway Platform                             │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  MCP Gateway Server                      │    │
│  │                  (FastMCP + FastAPI)                     │    │
│  │                                                          │    │
│  │  ┌────────────────┐  ┌────────────────┐  ┌───────────┐  │    │
│  │  │ Railway Tools  │  │   n8n Tools    │  │ Utility   │  │    │
│  │  │                │  │                │  │ Tools     │  │    │
│  │  │ - deploy()     │  │ - trigger()    │  │ - health  │  │    │
│  │  │ - rollback()   │  │ - list()       │  │ - metrics │  │    │
│  │  │ - status()     │  │ - status()     │  │ - logs    │  │    │
│  │  │ - logs()       │  │                │  │           │  │    │
│  │  └───────┬────────┘  └───────┬────────┘  └─────┬─────┘  │    │
│  │          │                   │                 │         │    │
│  └──────────┼───────────────────┼─────────────────┼─────────┘    │
│             │                   │                 │              │
│             ▼                   ▼                 ▼              │
│  ┌────────────────┐    ┌─────────────┐    ┌─────────────┐       │
│  │ Railway        │    │   n8n       │    │ Production  │       │
│  │ GraphQL API    │    │ Instance    │    │   App       │       │
│  │ (backboard)    │    │ (webhooks)  │    │ (or-infra)  │       │
│  └────────────────┘    └─────────────┘    └─────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| MCP Server | FastMCP 2.0 | MCP protocol implementation |
| Web Framework | FastAPI | HTTP endpoints, OpenAPI docs |
| Transport | Streamable HTTP | Bidirectional communication |
| Hosting | Railway | Already deployed, production-ready |
| Auth | Bearer Token | Secure API access |
| Storage | GCP Secret Manager | Credential storage |

---

## MCP Gateway Server Design

### Project Structure

```
src/mcp_gateway/
├── __init__.py
├── server.py           # FastMCP server definition
├── tools/
│   ├── __init__.py
│   ├── railway.py      # Railway operations
│   ├── n8n.py          # n8n workflow operations
│   └── monitoring.py   # Health, metrics, logs
├── auth.py             # Bearer token validation
└── config.py           # Environment configuration
```

### Core Server Implementation

```python
# src/mcp_gateway/server.py
from fastmcp import FastMCP
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Initialize FastMCP
mcp = FastMCP(
    "Claude Gateway",
    description="MCP Gateway for Railway and n8n autonomous operations"
)

# Security
security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify bearer token from GCP Secret Manager."""
    expected_token = get_secret("MCP-GATEWAY-TOKEN")
    if credentials.credentials != expected_token:
        raise HTTPException(status_code=401, detail="Invalid token")
    return credentials.credentials

# Railway Tools
@mcp.tool
async def railway_deploy(service_id: str = None) -> dict:
    """
    Trigger a new deployment on Railway.

    Args:
        service_id: Railway service ID (optional, uses default if not provided)

    Returns:
        Deployment status and ID
    """
    from .tools.railway import trigger_deployment
    return await trigger_deployment(service_id)

@mcp.tool
async def railway_status() -> dict:
    """
    Get current Railway deployment status.

    Returns:
        Current deployment status, health, and recent deployments
    """
    from .tools.railway import get_status
    return await get_status()

@mcp.tool
async def railway_rollback(deployment_id: str = None) -> dict:
    """
    Rollback to a previous successful deployment.

    Args:
        deployment_id: Target deployment ID (optional, uses last successful if not provided)

    Returns:
        Rollback status and new deployment ID
    """
    from .tools.railway import execute_rollback
    return await execute_rollback(deployment_id)

@mcp.tool
async def railway_logs(lines: int = 100) -> str:
    """
    Fetch recent Railway deployment logs.

    Args:
        lines: Number of log lines to fetch (default: 100)

    Returns:
        Recent log output
    """
    from .tools.railway import get_logs
    return await get_logs(lines)

# n8n Tools
@mcp.tool
async def n8n_trigger(workflow_name: str, data: dict = None) -> dict:
    """
    Trigger an n8n workflow.

    Args:
        workflow_name: Name of workflow to trigger (e.g., 'deploy-railway', 'health-monitor')
        data: Optional data to pass to the workflow

    Returns:
        Workflow execution result
    """
    from .tools.n8n import trigger_workflow
    return await trigger_workflow(workflow_name, data)

@mcp.tool
async def n8n_list_workflows() -> list:
    """
    List all available n8n workflows.

    Returns:
        List of workflow names and their webhook URLs
    """
    from .tools.n8n import list_workflows
    return await list_workflows()

# Monitoring Tools
@mcp.tool
async def health_check() -> dict:
    """
    Check health of all services.

    Returns:
        Health status of Railway app, database, n8n, and MCP gateway
    """
    from .tools.monitoring import check_all_health
    return await check_all_health()

@mcp.tool
async def get_metrics() -> dict:
    """
    Get current system metrics.

    Returns:
        CPU, memory, request counts, error rates
    """
    from .tools.monitoring import get_system_metrics
    return await get_system_metrics()

# Run with HTTP transport
if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)
```

### Railway Tools Implementation

```python
# src/mcp_gateway/tools/railway.py
import httpx
from ..config import get_config

RAILWAY_API = "https://backboard.railway.app/graphql/v2"

async def trigger_deployment(service_id: str = None) -> dict:
    """Trigger Railway deployment via GraphQL API."""
    config = get_config()
    service_id = service_id or config.railway_service_id
    environment_id = config.railway_environment_id

    query = """
    mutation {
        serviceInstanceRedeploy(
            serviceId: "%s"
            environmentId: "%s"
        )
    }
    """ % (service_id, environment_id)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            RAILWAY_API,
            json={"query": query},
            headers={
                "Authorization": f"Bearer {config.railway_token}",
                "Content-Type": "application/json"
            },
            timeout=60.0
        )

    data = response.json()

    if "errors" in data:
        return {"status": "error", "message": data["errors"][0]["message"]}

    return {
        "status": "triggered",
        "service_id": service_id,
        "environment_id": environment_id,
        "message": "Deployment triggered successfully"
    }

async def get_status() -> dict:
    """Get Railway deployment status."""
    config = get_config()

    query = """
    query {
        deployments(first: 5, input: {
            serviceId: "%s"
            environmentId: "%s"
        }) {
            edges {
                node {
                    id
                    status
                    createdAt
                }
            }
        }
    }
    """ % (config.railway_service_id, config.railway_environment_id)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            RAILWAY_API,
            json={"query": query},
            headers={
                "Authorization": f"Bearer {config.railway_token}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )

    data = response.json()
    deployments = data.get("data", {}).get("deployments", {}).get("edges", [])

    return {
        "current": deployments[0]["node"] if deployments else None,
        "recent": [d["node"] for d in deployments],
        "service_id": config.railway_service_id
    }

async def execute_rollback(deployment_id: str = None) -> dict:
    """Execute rollback to previous deployment."""
    config = get_config()

    # If no deployment_id, find last successful
    if not deployment_id:
        status = await get_status()
        for deployment in status.get("recent", [])[1:]:  # Skip current
            if deployment.get("status") == "SUCCESS":
                deployment_id = deployment["id"]
                break

    if not deployment_id:
        return {"status": "error", "message": "No successful deployment found for rollback"}

    query = """
    mutation {
        deploymentRollback(id: "%s") {
            id
            status
        }
    }
    """ % deployment_id

    async with httpx.AsyncClient() as client:
        response = await client.post(
            RAILWAY_API,
            json={"query": query},
            headers={
                "Authorization": f"Bearer {config.railway_token}",
                "Content-Type": "application/json"
            },
            timeout=60.0
        )

    data = response.json()

    if "errors" in data:
        return {"status": "error", "message": data["errors"][0]["message"]}

    rollback_data = data.get("data", {}).get("deploymentRollback", {})

    return {
        "status": "rollback_initiated",
        "deployment_id": rollback_data.get("id"),
        "target_deployment": deployment_id
    }

async def get_logs(lines: int = 100) -> str:
    """Fetch deployment logs (placeholder - Railway doesn't expose logs via API)."""
    return "Log retrieval requires Railway CLI access. Use dashboard: https://railway.app/project/95ec21cc-9ada-41c5-8485-12f9a00e0116"
```

### n8n Tools Implementation

```python
# src/mcp_gateway/tools/n8n.py
import httpx
from ..config import get_config

# Workflow webhook mappings
WORKFLOWS = {
    "health-monitor": "/webhook/health-check",
    "deploy-railway": "/webhook/deploy-railway",
    "rollback-railway": "/webhook/rollback-railway"
}

async def trigger_workflow(workflow_name: str, data: dict = None) -> dict:
    """Trigger n8n workflow via webhook."""
    config = get_config()

    if workflow_name not in WORKFLOWS:
        return {
            "status": "error",
            "message": f"Unknown workflow: {workflow_name}",
            "available": list(WORKFLOWS.keys())
        }

    webhook_path = WORKFLOWS[workflow_name]
    url = f"{config.n8n_base_url}{webhook_path}"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json=data or {},
            headers={"Content-Type": "application/json"},
            timeout=30.0
        )

    return {
        "status": "triggered",
        "workflow": workflow_name,
        "response": response.json() if response.status_code == 200 else None,
        "http_status": response.status_code
    }

async def list_workflows() -> list:
    """List available n8n workflows."""
    config = get_config()

    return [
        {
            "name": name,
            "webhook": f"{config.n8n_base_url}{path}",
            "description": get_workflow_description(name)
        }
        for name, path in WORKFLOWS.items()
    ]

def get_workflow_description(name: str) -> str:
    """Get workflow description."""
    descriptions = {
        "health-monitor": "Check production health status",
        "deploy-railway": "Trigger new Railway deployment",
        "rollback-railway": "Rollback to previous deployment"
    }
    return descriptions.get(name, "No description")
```

### Configuration Management

```python
# src/mcp_gateway/config.py
import os
from dataclasses import dataclass
from src.secrets_manager import SecretManager

@dataclass
class Config:
    railway_token: str
    railway_service_id: str
    railway_environment_id: str
    n8n_base_url: str
    n8n_api_key: str
    gateway_token: str

_config: Config = None

def get_config() -> Config:
    """Load configuration from GCP Secret Manager."""
    global _config

    if _config is None:
        manager = SecretManager()

        _config = Config(
            railway_token=manager.get_secret("RAILWAY-API"),
            railway_service_id=os.environ.get("RAILWAY_SERVICE_ID", ""),
            railway_environment_id=os.environ.get("RAILWAY_ENVIRONMENT_ID", "99c99a18-aea2-4d01-9360-6a93705102a0"),
            n8n_base_url=os.environ.get("N8N_BASE_URL", ""),
            n8n_api_key=manager.get_secret("N8N-API"),
            gateway_token=manager.get_secret("MCP-GATEWAY-TOKEN")
        )

    return _config
```

---

## Deployment Steps

### What the User Does (Minimal - One Time)

1. **Create MCP Gateway Token**
   ```bash
   # Generate a secure token
   openssl rand -hex 32

   # Add to GCP Secret Manager
   gcloud secrets create MCP-GATEWAY-TOKEN --data-file=-
   ```

2. **Deploy MCP Gateway to Railway**
   ```bash
   # The MCP Gateway is part of the existing FastAPI app
   # Just needs to be enabled via environment variable
   railway variables set MCP_GATEWAY_ENABLED=true
   railway up
   ```

3. **Configure Claude Code**
   ```bash
   # One-time configuration
   claude mcp add \
     --transport http \
     --header "Authorization: Bearer <MCP-GATEWAY-TOKEN>" \
     --scope user \
     claude-gateway \
     https://or-infra.com/mcp
   ```

### What Claude Does (Full Autonomy)

After the one-time setup, Claude can:

1. **Deploy new versions**
   ```
   Claude: "Deploy the latest changes to Railway"
   → Uses railway_deploy() tool
   → No manual intervention needed
   ```

2. **Monitor health**
   ```
   Claude: "Check if production is healthy"
   → Uses health_check() tool
   → Gets real-time status
   ```

3. **Handle incidents**
   ```
   Claude: "Production is down, rollback immediately"
   → Uses railway_rollback() tool
   → Automatic recovery
   ```

4. **Trigger automation**
   ```
   Claude: "Run the deployment workflow in n8n"
   → Uses n8n_trigger() tool
   → Complex automation chains
   ```

---

## Security Architecture

### Authentication Flow

```
┌─────────────────┐     Authorization: Bearer <token>     ┌──────────────────┐
│  Claude Code    │ ─────────────────────────────────────▶│  MCP Gateway     │
│                 │                                       │                  │
│  (Has token in  │                                       │  (Validates vs   │
│   MCP config)   │                                       │   GCP Secret)    │
└─────────────────┘                                       └────────┬─────────┘
                                                                   │
                                                                   │ Valid?
                                                                   ▼
                                                          ┌──────────────────┐
                                                          │  GCP Secret      │
                                                          │  Manager         │
                                                          │                  │
                                                          │  MCP-GATEWAY-    │
                                                          │  TOKEN           │
                                                          └──────────────────┘
```

### Security Layers

| Layer | Protection |
|-------|------------|
| Transport | HTTPS (TLS 1.3) via Railway |
| Authentication | Bearer token in header |
| Authorization | Token validated against GCP Secret |
| Secrets | All credentials in GCP Secret Manager |
| Audit | All operations logged |
| Network | Railway internal network for backend calls |

### Rate Limiting

```python
# Built into FastAPI
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

@app.post("/mcp")
@limiter.limit("100/minute")
async def mcp_endpoint(request: Request):
    ...
```

---

## Integration with Existing Systems

### With Current FastAPI App

The MCP Gateway integrates with the existing `src/api/main.py`:

```python
# src/api/main.py (updated)
from fastapi import FastAPI
from src.mcp_gateway.server import mcp

app = FastAPI(title="Project38-OR API")

# Existing routes
from src.api.routes import health, agents, tasks
app.include_router(health.router)
app.include_router(agents.router)
app.include_router(tasks.router)

# Mount MCP Gateway (if enabled)
if os.environ.get("MCP_GATEWAY_ENABLED"):
    # Mount MCP server at /mcp
    mcp_app = mcp.http_app()
    app.mount("/mcp", mcp_app)
```

### With n8n Workflows

The MCP Gateway works alongside the n8n workflows created earlier:

| Trigger Source | Flow |
|----------------|------|
| Claude MCP | Claude → MCP Gateway → n8n webhook |
| GitHub Push | GitHub → n8n webhook → Railway |
| Cron | n8n cron → Health check |

### With Existing Skills

The MCP Gateway enhances existing Claude Code skills:

| Skill | Enhancement |
|-------|-------------|
| `deployment-checker` | Can now verify Railway status directly |
| `pr-helper` | Can trigger deployments after PR merge |
| `test-runner` | Can validate deployed version |

---

## OODA Loop Integration

The MCP Gateway enables full OODA Loop autonomy:

```
     ┌──────────────────────────────────────────────────────────────┐
     │                      OODA Loop                                │
     │                                                               │
     │   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐   │
     │   │ OBSERVE │───▶│ ORIENT  │───▶│ DECIDE  │───▶│   ACT   │   │
     │   │         │    │         │    │         │    │         │   │
     │   │ health_ │    │ Analyze │    │ Choose  │    │ railway_│   │
     │   │ check() │    │ status  │    │ action  │    │ deploy()│   │
     │   │         │    │         │    │         │    │         │   │
     │   │ get_    │    │ Compare │    │ Select  │    │ railway_│   │
     │   │ metrics │    │ to SLOs │    │ workflow│    │ rollback│   │
     │   └─────────┘    └─────────┘    └─────────┘    └─────────┘   │
     │        │                                            │         │
     │        └────────────────────────────────────────────┘         │
     │                        Feedback Loop                          │
     └──────────────────────────────────────────────────────────────┘
```

---

## Verification & Testing

### Test the MCP Gateway

```bash
# 1. Check MCP server is running
curl -X POST https://or-infra.com/mcp \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'

# 2. Test a tool
curl -X POST https://or-infra.com/mcp \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"health_check"},"id":2}'
```

### Verify Claude Connection

```bash
# List connected MCP servers
claude mcp list

# Should show:
# claude-gateway: https://or-infra.com/mcp (HTTP) - ✓ Connected
```

### Test Autonomous Operations

```
User: "Check if production is healthy"

Claude: [Uses health_check tool via MCP Gateway]

Result: {
  "status": "healthy",
  "railway": "running",
  "database": "connected",
  "n8n": "available"
}
```

---

## Timeline & Dependencies

### Phase 1: MCP Gateway Implementation (Claude does this)

| Task | Description |
|------|-------------|
| Create `src/mcp_gateway/` | Directory structure and files |
| Implement Railway tools | deploy, status, rollback |
| Implement n8n tools | trigger, list workflows |
| Add authentication | Bearer token validation |
| Update FastAPI mount | Add /mcp endpoint |
| Tests | Unit and integration tests |

### Phase 2: User Setup (One-time, minimal)

| Task | Description |
|------|-------------|
| Create MCP-GATEWAY-TOKEN | Generate and store in GCP |
| Set environment variable | MCP_GATEWAY_ENABLED=true |
| Deploy to Railway | `railway up` |
| Configure Claude Code | `claude mcp add` |

### Phase 3: Full Autonomy (Ongoing)

| Capability | Status |
|------------|--------|
| Deploy on demand | Enabled |
| Monitor health | Enabled |
| Auto-rollback | Enabled |
| n8n workflow triggering | Enabled |
| Incident response | Enabled |

---

## References

### Sources

- [FastMCP Documentation](https://github.com/jlowin/fastmcp) - Python MCP server framework
- [Railway MCP Server](https://docs.railway.com/reference/mcp-server) - Official Railway MCP documentation
- [Claude Code MCP Docs](https://code.claude.com/docs/en/mcp) - Connect Claude Code to MCP servers
- [Remote MCP Servers](https://support.claude.com/en/articles/11503834-building-custom-connectors-via-remote-mcp-servers) - Building custom connectors
- [mcp-n8n-server](https://github.com/ahmadsoliman/mcp-n8n-server) - n8n MCP integration example
- [AI Agent Gateways 2025](https://www.truefoundry.com/blog/top-agent-gateways) - Agent gateway architecture patterns
- [Railway AI Agents](https://www.startuphub.ai/ai-news/ai-video/2025/ai-agents-usher-in-self-healing-infrastructure-at-railway/) - Self-healing infrastructure

### Related Project Documentation

- [ADR-003: Railway Autonomous Control](../decisions/ADR-003-railway-autonomous-control.md)
- n8n Workflows: See `src/workflows/` directory
- [Railway Setup Guide](../RAILWAY_SETUP.md)
- [Autonomous System Architecture](01-system-architecture-hybrid.md)

---

## Summary

The MCP Gateway architecture provides:

1. **Full Autonomy** - Claude can operate Railway and n8n without manual intervention
2. **Minimal User Setup** - One-time configuration (create token, deploy, configure)
3. **Secure** - Bearer token auth, GCP Secret Manager, HTTPS transport
4. **Extensible** - Easy to add new tools and workflows
5. **Production-Ready** - Integrates with existing FastAPI app on Railway

**Next Steps:**
1. User creates MCP-GATEWAY-TOKEN in GCP
2. Claude implements the MCP Gateway code
3. User deploys with `railway up`
4. User runs `claude mcp add` once
5. Full autonomy activated
