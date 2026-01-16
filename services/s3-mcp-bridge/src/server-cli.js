#!/usr/bin/env node
/**
 * S3 MCP Bridge - Server CLI
 *
 * Runs on Railway/other infrastructure to poll S3 and forward to MCP server.
 *
 * Usage:
 *   s3-mcp-bridge-server --bucket my-bucket --mcp-url http://localhost:8080/mcp
 *
 * Environment variables:
 *   AWS_ACCESS_KEY_ID - AWS credentials
 *   AWS_SECRET_ACCESS_KEY - AWS credentials
 *   MCP_BUCKET - S3 bucket name
 *   MCP_REGION - AWS region (default: us-east-1)
 *   MCP_PREFIX - S3 key prefix (default: mcp-relay)
 *   MCP_URL - HTTP URL of the real MCP server
 *   MCP_COMMAND - Command to run MCP server (for stdio mode)
 *   MCP_ARGS - Arguments for MCP command (JSON array)
 */

import { S3McpBridgeServer } from "./server.js";

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
    } else if (arg === "--mcp-url" && args[i + 1]) {
      config.mcpUrl = args[++i];
    } else if (arg === "--mcp-command" && args[i + 1]) {
      config.mcpCommand = args[++i];
    } else if (arg === "--mcp-args" && args[i + 1]) {
      config.mcpArgs = JSON.parse(args[++i]);
    } else if (arg === "--poll-interval" && args[i + 1]) {
      config.pollIntervalMs = parseInt(args[++i], 10);
    } else if (arg === "--help" || arg === "-h") {
      printHelp();
      process.exit(0);
    }
  }

  return config;
}

function printHelp() {
  console.log(`
S3 MCP Bridge Server - Poll S3 and forward to MCP server

Usage:
  s3-mcp-bridge-server [options]

Options:
  --bucket <name>        S3 bucket name (required, or set MCP_BUCKET)
  --region <region>      AWS region (default: us-east-1)
  --prefix <prefix>      S3 key prefix (default: mcp-relay)
  --mcp-url <url>        HTTP URL of real MCP server
  --mcp-command <cmd>    Command to run MCP server (stdio mode)
  --mcp-args <json>      Arguments as JSON array (stdio mode)
  --poll-interval <ms>   Poll interval in milliseconds (default: 500)
  --help, -h             Show this help message

Environment Variables:
  AWS_ACCESS_KEY_ID      AWS access key
  AWS_SECRET_ACCESS_KEY  AWS secret key
  MCP_BUCKET             S3 bucket name
  MCP_REGION             AWS region
  MCP_PREFIX             S3 key prefix
  MCP_URL                HTTP URL of real MCP server
  MCP_COMMAND            Command to run MCP server
  MCP_ARGS               Arguments as JSON array

Example (HTTP mode):
  s3-mcp-bridge-server --bucket my-bucket --mcp-url http://localhost:8080/mcp

Example (Stdio mode):
  s3-mcp-bridge-server --bucket my-bucket --mcp-command node --mcp-args '["./mcp-server.js"]'
`);
}

async function main() {
  const cliConfig = parseArgs();

  // Merge CLI args with environment variables
  const config = {
    bucket: cliConfig.bucket || process.env.MCP_BUCKET,
    region: cliConfig.region || process.env.MCP_REGION || "us-east-1",
    prefix: cliConfig.prefix || process.env.MCP_PREFIX || "mcp-relay",
    mcpUrl: cliConfig.mcpUrl || process.env.MCP_URL,
    mcpCommand: cliConfig.mcpCommand || process.env.MCP_COMMAND,
    mcpArgs: cliConfig.mcpArgs || (process.env.MCP_ARGS ? JSON.parse(process.env.MCP_ARGS) : []),
    pollIntervalMs: cliConfig.pollIntervalMs || parseInt(process.env.MCP_POLL_INTERVAL || "500", 10),
    credentials: process.env.AWS_ACCESS_KEY_ID ? {
      accessKeyId: process.env.AWS_ACCESS_KEY_ID,
      secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY
    } : undefined
  };

  if (!config.bucket) {
    console.error("Error: S3 bucket is required. Use --bucket or set MCP_BUCKET environment variable.");
    process.exit(1);
  }

  if (!config.mcpUrl && !config.mcpCommand) {
    console.error("Error: Either --mcp-url or --mcp-command is required.");
    process.exit(1);
  }

  const server = new S3McpBridgeServer(config);

  // Handle graceful shutdown
  process.on("SIGINT", () => {
    console.log("\nReceived SIGINT, shutting down...");
    server.stop();
    process.exit(0);
  });

  process.on("SIGTERM", () => {
    console.log("\nReceived SIGTERM, shutting down...");
    server.stop();
    process.exit(0);
  });

  await server.start();
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
