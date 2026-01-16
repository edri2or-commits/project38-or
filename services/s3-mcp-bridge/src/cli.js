#!/usr/bin/env node
/**
 * S3 MCP Bridge - CLI
 *
 * Usage:
 *   s3-mcp-bridge --bucket my-bucket --region us-east-1
 *
 * Environment variables:
 *   AWS_ACCESS_KEY_ID - AWS credentials
 *   AWS_SECRET_ACCESS_KEY - AWS credentials
 *   MCP_BUCKET - S3 bucket name
 *   MCP_REGION - AWS region (default: us-east-1)
 *   MCP_PREFIX - S3 key prefix (default: mcp-relay)
 *   MCP_SESSION_ID - Session identifier (default: auto-generated)
 *   MCP_POLL_INTERVAL - Poll interval in ms (default: 250)
 *   MCP_TIMEOUT - Request timeout in ms (default: 30000)
 */

import { S3McpBridgeClient } from "./client.js";

function parseArgs() {
  const args = process.argv.slice(2);
  const config = {};

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "--bucket" && args[i + 1]) {
      config.bucket = args[++i];
    } else if (arg === "--region" && args[i + 1]) {
      config.region = args[++i];
    } else if (arg === "--prefix" && args[i + 1]) {
      config.prefix = args[++i];
    } else if (arg === "--session-id" && args[i + 1]) {
      config.sessionId = args[++i];
    } else if (arg === "--poll-interval" && args[i + 1]) {
      config.pollIntervalMs = parseInt(args[++i], 10);
    } else if (arg === "--timeout" && args[i + 1]) {
      config.timeoutMs = parseInt(args[++i], 10);
    } else if (arg === "--help" || arg === "-h") {
      printHelp();
      process.exit(0);
    }
  }

  return config;
}

function printHelp() {
  console.log(`
S3 MCP Bridge - Tunnel MCP messages through Amazon S3

Usage:
  s3-mcp-bridge [options]

Options:
  --bucket <name>       S3 bucket name (required, or set MCP_BUCKET)
  --region <region>     AWS region (default: us-east-1)
  --prefix <prefix>     S3 key prefix (default: mcp-relay)
  --session-id <id>     Session identifier (default: auto-generated)
  --poll-interval <ms>  Poll interval in milliseconds (default: 250)
  --timeout <ms>        Request timeout in milliseconds (default: 30000)
  --help, -h            Show this help message

Environment Variables:
  AWS_ACCESS_KEY_ID     AWS access key
  AWS_SECRET_ACCESS_KEY AWS secret key
  MCP_BUCKET            S3 bucket name
  MCP_REGION            AWS region
  MCP_PREFIX            S3 key prefix
  MCP_SESSION_ID        Session identifier
  MCP_POLL_INTERVAL     Poll interval in ms
  MCP_TIMEOUT           Request timeout in ms

Example:
  # Using environment variables
  export AWS_ACCESS_KEY_ID=AKIA...
  export AWS_SECRET_ACCESS_KEY=...
  export MCP_BUCKET=my-mcp-relay-bucket
  s3-mcp-bridge

  # Using command line arguments
  s3-mcp-bridge --bucket my-mcp-relay-bucket --region us-east-1
`);
}

function main() {
  const cliConfig = parseArgs();

  // Merge CLI args with environment variables
  const config = {
    bucket: cliConfig.bucket || process.env.MCP_BUCKET,
    region: cliConfig.region || process.env.MCP_REGION || "us-east-1",
    prefix: cliConfig.prefix || process.env.MCP_PREFIX || "mcp-relay",
    sessionId: cliConfig.sessionId || process.env.MCP_SESSION_ID,
    pollIntervalMs: cliConfig.pollIntervalMs || parseInt(process.env.MCP_POLL_INTERVAL || "250", 10),
    timeoutMs: cliConfig.timeoutMs || parseInt(process.env.MCP_TIMEOUT || "30000", 10),
    credentials: process.env.AWS_ACCESS_KEY_ID ? {
      accessKeyId: process.env.AWS_ACCESS_KEY_ID,
      secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY
    } : undefined
  };

  if (!config.bucket) {
    console.error("Error: S3 bucket is required. Use --bucket or set MCP_BUCKET environment variable.");
    process.exit(1);
  }

  const client = new S3McpBridgeClient(config);
  client.start();
}

main();
