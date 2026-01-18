# GCP MCP Server

**Autonomous GCP operations via MCP protocol for Claude Code**

## Overview

The GCP MCP Server provides Claude Code with full autonomous access to Google Cloud Platform operations through the Model Context Protocol (MCP). It runs as a Cloud Run service and authenticates using Workload Identity (keyless).

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

### Execute gcloud command

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

## Security

### Authentication

- **Bearer Token**: All requests require `Authorization: Bearer TOKEN` header
- **Token Storage**: Tokens stored in GCP Secret Manager (`GCP-MCP-GATEWAY-TOKEN`)
- **Token Rotation**: Regenerate tokens periodically using workflow

### Authorization

- **Service Account**: Runs as `claude-code-agent@project38-483612.iam.gserviceaccount.com`
- **Least Privilege**: Service account has minimal required permissions
- **Workload Identity**: Uses WIF (keyless) for authentication to GCP APIs

### Secret Handling

- **Masked Values**: `secret_get()` returns masked preview by default
- **No Logging**: Secrets never logged or exposed in responses
- **Audit Trail**: All operations logged via Cloud Logging

## Troubleshooting

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
curl https://gcp-mcp-gateway-XXXXX.run.app/health

# Check Cloud Run service
gcloud run services describe gcp-mcp-gateway --region=us-central1
```

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
