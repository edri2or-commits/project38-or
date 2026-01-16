# S3 MCP Bridge

Tunnel MCP (Model Context Protocol) messages through Amazon S3 for environments with restricted network egress.

## Problem

Claude Code cloud environments use an egress proxy that blocks most external domains (including `*.run.app`, `*.railway.app`, etc.). However, `s3.amazonaws.com` is whitelisted.

## Solution

This bridge tunnels MCP JSON-RPC messages through S3 objects:

```
Claude Code <--stdio--> Client Bridge <--S3--> Server Bridge <--stdio/http--> Real MCP Server
```

## Architecture

### Client (runs in Claude Code)
- Reads MCP messages from stdin
- Uploads to `s3://bucket/mcp-relay/requests/{session}/{id}.json`
- Polls `s3://bucket/mcp-relay/responses/{session}/{id}.json`
- Writes response to stdout

### Server (runs on Railway/etc)
- Polls `s3://bucket/mcp-relay/requests/` for new messages
- Forwards to real MCP server (stdio or HTTP)
- Uploads response to `s3://bucket/mcp-relay/responses/`
- Deletes request after processing

## Setup

### 1. Create S3 Bucket

```bash
aws s3 mb s3://my-mcp-relay-bucket
```

Add lifecycle rule to expire objects after 1 day:
```json
{
  "Rules": [
    {
      "ID": "ExpireOldMessages",
      "Status": "Enabled",
      "Filter": {"Prefix": "mcp-relay/"},
      "Expiration": {"Days": 1}
    }
  ]
}
```

### 2. Create IAM User

Create an IAM user with minimal permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::my-mcp-relay-bucket",
        "arn:aws:s3:::my-mcp-relay-bucket/*"
      ]
    }
  ]
}
```

### 3. Deploy Server to Railway

Set environment variables:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `MCP_BUCKET=my-mcp-relay-bucket`
- `MCP_URL=http://localhost:8080/mcp` (or use stdio mode)

Run:
```bash
npm install
npm run start:server
```

### 4. Configure Claude Code

```bash
# Install the bridge
npm install -g @project38/s3-mcp-bridge

# Add MCP server
claude mcp add --transport stdio \
  --env AWS_ACCESS_KEY_ID=AKIA... \
  --env AWS_SECRET_ACCESS_KEY=... \
  --env MCP_BUCKET=my-mcp-relay-bucket \
  my-mcp-server \
  -- s3-mcp-bridge
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AWS_ACCESS_KEY_ID` | AWS access key | (required) |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | (required) |
| `MCP_BUCKET` | S3 bucket name | (required) |
| `MCP_REGION` | AWS region | us-east-1 |
| `MCP_PREFIX` | S3 key prefix | mcp-relay |
| `MCP_POLL_INTERVAL` | Poll interval (ms) | 250 (client) / 500 (server) |
| `MCP_TIMEOUT` | Request timeout (ms) | 30000 |

## Performance

- **Latency**: ~0.5-1.0 seconds round trip
- **Throughput**: Limited by S3 request rate (3,500 PUT + 5,500 GET per second per prefix)
- **Cost**: ~$0.005 per 1000 requests

## Security

- All traffic uses HTTPS with AWS SigV4 authentication
- Every operation logged in CloudTrail
- No direct network path between Claude and your infrastructure
- Bucket can be restricted to specific IAM users only

## License

MIT
