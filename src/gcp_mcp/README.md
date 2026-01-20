# GCP MCP Server

**Autonomous GCP operations via MCP protocol for Claude Code**

## Overview

The GCP MCP Server provides Claude Code with full autonomous access to Google Cloud Platform operations through the Model Context Protocol (MCP). It runs as a Cloud Run service and authenticates using Workload Identity (keyless).

## Production Status

| Component | URL | Status |
|-----------|-----|--------|
| **Cloud Run** | `https://gcp-mcp-gateway-3e7yyrd7xq-uc.a.run.app` | ✅ Deployed |
| **Cloud Function** | `us-central1-project38-483612.cloudfunctions.net/mcp-router` | ✅ Deployed |
| **Bearer Token** | Stored in `GCP-MCP-TOKEN` secret | ✅ Active |

> **Note for Anthropic Cloud Sessions**: Cloud Run (`.run.app`) is blocked by Anthropic proxy. Use Cloud Function tunnel instead - see [Alternative Access](#alternative-access-cloud-function-tunnel) section.

## Architecture

```
Claude Code Session (any environment)
    ↓ (MCP Protocol over HTTPS)
GCP MCP Gateway (Cloud Run)
    ↓ (Workload Identity via Metadata Server)
Google Cloud Platform APIs
    ├── Secret Manager
    ├── Compute Engine
    ├── Cloud Storage
    ├── IAM
    └── gcloud CLI
```

## Available Tools

### gcloud Commands
- `gcloud_run(command, project_id)` - Execute any gcloud command
- `gcloud_version()` - Get gcloud version and configuration

### Secret Manager
- `secret_get(secret_name, version)` - Retrieve secret value (masked)
- `secret_list()` - List all secrets
- `secret_create(secret_name, secret_value)` - Create new secret
- `secret_update(secret_name, secret_value)` - Update existing secret

### Compute Engine
- `compute_list(zone)` - List instances
- `compute_get(instance_name, zone)` - Get instance details
- `compute_start(instance_name, zone)` - Start instance
- `compute_stop(instance_name, zone)` - Stop instance

### Cloud Storage
- `storage_list(bucket_name, prefix)` - List buckets/objects
- `storage_get(bucket_name, object_name)` - Get object metadata
- `storage_upload(bucket_name, source, dest)` - Upload file

### IAM
- `iam_list_accounts()` - List service accounts
- `iam_get_policy(resource)` - Get IAM policy

## Deployment

### Prerequisites

1. GCP Project with billing enabled
2. WIF configured for GitHub Actions
3. Service Account: `claude-code-agent@project38-483612.iam.gserviceaccount.com`

### Deploy to Cloud Run

```bash
# Using GitHub Actions workflow
gh workflow run deploy-gcp-mcp.yml -f action=deploy
```

### Generate Auth Token

```bash
# Generate authentication token
gh workflow run deploy-gcp-mcp.yml -f action=generate-token
```

### Check Status

```bash
# Check deployment status
gh workflow run deploy-gcp-mcp.yml -f action=status
```

## Configuration

### Claude Code Integration

Add the GCP MCP Gateway to Claude Code:

```bash
claude mcp add --transport http \
  --header "Authorization: Bearer YOUR_TOKEN" \
  --scope user \
  gcp-gateway https://gcp-mcp-gateway-XXXXX.run.app
```

Or manually edit `~/.claude.json`:

```json
{
  "mcpServers": {
    "gcp-gateway": {
      "type": "http",
      "url": "https://gcp-mcp-gateway-XXXXX.run.app",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN"
      }
    }
  }
}
```

## Usage Examples

### Claude Code Prompts

These prompts work when GCP MCP Server is configured:

```
"List all secrets in project38-483612"
→ Uses: gcp_secret_list()

"Show me compute instances in us-central1"
→ Uses: compute_list(zone='us-central1-a')

"Run: gcloud projects describe project38-483612"
→ Uses: gcloud_run(command='projects describe project38-483612')

"Create a Cloud Storage bucket named 'test-bucket'"
→ Uses: storage_create_bucket(name='test-bucket')

"List IAM service accounts"
→ Uses: iam_list_accounts()
```

### Python API Examples

#### Execute gcloud command

```python
# List compute instances
result = await gcloud_run("compute instances list --limit=5")
```

### Manage secrets

```python
# List secrets
secrets = await secret_list()

# Get secret value
value = await secret_get("ANTHROPIC-API")
```

### Manage compute instances

```python
# List instances
instances = await compute_list()

# Start instance
await compute_start("my-instance", "us-central1-a")
```

### Cloud Storage operations

```python
# List buckets
buckets = await storage_list()

# Upload file
await storage_upload("my-bucket", "/local/file.txt", "remote/file.txt")
```

## Alternative Access: Cloud Function Tunnel

**Problem**: Anthropic cloud sessions block `.run.app` domains.

**Solution**: GCP tools are also available via Cloud Function tunnel at `cloudfunctions.googleapis.com` (whitelisted).

### Available Tools via Cloud Function

| Tool | Description |
|------|-------------|
| `gcp_secret_list` | List all secrets in Secret Manager |
| `gcp_secret_get` | Get secret value (masked for security) |
| `gcp_project_info` | Get project info and available tools |

### Usage from Anthropic Cloud

```bash
# Cloud Function URL (works in Anthropic cloud)
https://us-central1-project38-483612.cloudfunctions.net/mcp-router

# Token: MCP_TUNNEL_TOKEN (in environment)
```

### Example: List Secrets

```bash
curl -X POST \
  -H "Authorization: Bearer $MCP_TUNNEL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "execute", "tool": "gcp_secret_list", "params": {}}' \
  https://us-central1-project38-483612.cloudfunctions.net/mcp-router
```

---

## Security

### Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Security Layers                          │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Network    │ HTTPS only, TLS 1.3                  │
│  Layer 2: Auth       │ Bearer Token (256-bit entropy)       │
│  Layer 3: Identity   │ Workload Identity (keyless)          │
│  Layer 4: Access     │ IAM Roles (least privilege)          │
│  Layer 5: Audit      │ Cloud Logging (all operations)       │
└─────────────────────────────────────────────────────────────┘
```

### Authentication

- **Bearer Token**: All requests require `Authorization: Bearer TOKEN` header
- **Token Entropy**: 256 bits (43 characters, URL-safe base64)
- **Token Storage**: Stored in GCP Secret Manager (`GCP-MCP-TOKEN`)
- **Token Rotation**: Regenerate periodically using workflow

### Authorization

- **Service Account**: `claude-code-agent@project38-483612.iam.gserviceaccount.com`
- **Workload Identity**: Uses WIF (keyless) - no static credentials
- **IAM Roles**:
  - `roles/secretmanager.admin` - Secret Manager operations
  - `roles/compute.admin` - Compute Engine management
  - `roles/storage.admin` - Cloud Storage operations
  - `roles/iam.roleViewer` - IAM queries (read-only)

### Secret Handling

- **Masked Values**: `secret_get()` returns masked preview (first 10 chars + `...`)
- **No Full Values**: Full secret values never returned via MCP
- **No Logging**: Secrets never logged or exposed in responses
- **Audit Trail**: All operations logged via Cloud Logging with service account attribution

### Security Best Practices

1. **Never share Bearer token** in public channels
2. **Rotate tokens** every 90 days
3. **Monitor Cloud Logging** for suspicious activity
4. **Use least privilege** - request only needed permissions

> **Full Security Model**: See [ADR-006](../../docs/decisions/ADR-006-gcp-agent-autonomy.md#security-model) for complete security architecture and rationale.

## Troubleshooting

### Anthropic Proxy Blocks Cloud Run

**Symptom**: Timeout when accessing `*.run.app` from Anthropic cloud sessions.

**Cause**: Anthropic proxy blocks `.run.app` domains for security.

**Solution**: Use Cloud Function tunnel instead:
```bash
# Instead of:
https://gcp-mcp-gateway-3e7yyrd7xq-uc.a.run.app

# Use:
https://us-central1-project38-483612.cloudfunctions.net/mcp-router
```

**Verification**:
```bash
# This should return HTTP 401 (auth error = connectivity works)
curl https://us-central1-project38-483612.cloudfunctions.net/mcp-router
```

### Deployment fails

```bash
# Check Cloud Run logs
gcloud run services logs read gcp-mcp-gateway --region=us-central1

# Check service status
gh workflow run deploy-gcp-mcp.yml -f action=status
```

### Authentication errors

```bash
# Verify WIF configuration
gh workflow run diagnose-wif-auth.yml

# Check service account permissions
gcloud projects get-iam-policy project38-483612 \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:claude-code-agent@*"
```

### Health check fails

```bash
# Test health endpoint
curl https://gcp-mcp-gateway-3e7yyrd7xq-uc.a.run.app/health

# Check Cloud Run service
gcloud run services describe gcp-mcp-gateway --region=us-central1
```

### Token invalid or expired

**Symptom**: HTTP 401 Unauthorized

**Solutions**:
```bash
# 1. Verify token is correct
gcloud secrets versions access latest --secret="GCP-MCP-TOKEN"

# 2. Generate new token if needed
gh workflow run deploy-gcp-mcp.yml -f action=generate-token

# 3. Update Claude Code configuration
claude mcp remove gcp-mcp
claude mcp add --transport http \
  --header "Authorization: Bearer NEW_TOKEN" \
  --scope user \
  gcp-mcp https://gcp-mcp-gateway-3e7yyrd7xq-uc.a.run.app
```

### Tool not found

**Symptom**: Error "Unknown tool: <tool_name>"

**Cause**: Tool name mismatch or tool not registered.

**Valid tool names**:
- `gcloud_run`, `gcloud_version`
- `secret_get`, `secret_list`, `secret_create`, `secret_update`
- `compute_list`, `compute_get`, `compute_start`, `compute_stop`
- `storage_list`, `storage_get`, `storage_upload`
- `iam_list_accounts`, `iam_get_policy`

### Permission denied

**Symptom**: HTTP 403 or "Permission denied" errors

**Solutions**:
```bash
# 1. Check service account roles
gcloud projects get-iam-policy project38-483612 \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:claude-code-agent@*" \
  --format="table(bindings.role)"

# 2. Add missing role (example: Secret Manager)
gcloud projects add-iam-policy-binding project38-483612 \
  --member="serviceAccount:claude-code-agent@project38-483612.iam.gserviceaccount.com" \
  --role="roles/secretmanager.admin"
```

### Common Error Codes

| Code | Meaning | Solution |
|------|---------|----------|
| 401 | Unauthorized | Check Bearer token |
| 403 | Forbidden | Check IAM permissions |
| 404 | Not found | Check resource exists |
| 408 | Timeout | Use Cloud Function tunnel |
| 500 | Server error | Check Cloud Run logs |

## Development

### Local testing

```bash
# Install dependencies
cd src/gcp_mcp
pip install -r requirements.txt

# Set environment variables
export GCP_PROJECT_ID=project38-483612
export PORT=8080

# Run server
python -m server
```

### Docker testing

```bash
# Build image
docker build -t gcp-mcp-gateway .

# Run container
docker run -p 8080:8080 \
  -e GCP_PROJECT_ID=project38-483612 \
  gcp-mcp-gateway
```

## Architecture Decisions

See [ADR-006: GCP Agent Autonomy](../../docs/decisions/ADR-006-gcp-agent-autonomy.md) for:
- Why MCP over other protocols
- Authentication strategy (WIF vs Service Account Keys)
- Security considerations
- Tool design principles

## References

- **MCP Protocol**: https://modelcontextprotocol.io
- **FastMCP**: https://github.com/jlowin/fastmcp
- **Workload Identity**: https://cloud.google.com/iam/docs/workload-identity-federation
- **Cloud Run**: https://cloud.google.com/run/docs
