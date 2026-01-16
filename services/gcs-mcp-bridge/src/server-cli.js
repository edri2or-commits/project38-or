#!/usr/bin/env node
/**
 * GCS MCP Bridge - Server CLI
 *
 * Runs on Railway. Polls GCS and forwards to MCP server.
 */

import { GcsMcpBridgeServer } from "./server.js";

function parseArgs() {
  const args = process.argv.slice(2);
  const config = {};

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--bucket" && args[i + 1]) config.bucket = args[++i];
    else if (args[i] === "--prefix" && args[i + 1]) config.prefix = args[++i];
    else if (args[i] === "--mcp-url" && args[i + 1]) config.mcpUrl = args[++i];
    else if (args[i] === "--credentials" && args[i + 1]) config.keyFilename = args[++i];
    else if (args[i] === "--help") {
      console.log(`
GCS MCP Bridge Server

Usage: gcs-mcp-bridge-server [options]

Options:
  --bucket <name>      GCS bucket name (or set GCS_BUCKET)
  --prefix <prefix>    Object prefix (default: mcp-relay)
  --mcp-url <url>      URL of real MCP server (or set MCP_URL)
  --credentials <path> Path to service account JSON
  --help               Show this help
`);
      process.exit(0);
    }
  }
  return config;
}

const cli = parseArgs();
const config = {
  bucket: cli.bucket || process.env.GCS_BUCKET,
  prefix: cli.prefix || process.env.GCS_PREFIX || "mcp-relay",
  mcpUrl: cli.mcpUrl || process.env.MCP_URL,
  keyFilename: cli.keyFilename || process.env.GOOGLE_APPLICATION_CREDENTIALS
};

if (!config.bucket) {
  console.error("Error: GCS bucket required");
  process.exit(1);
}

if (!config.mcpUrl) {
  console.error("Error: MCP URL required. Use --mcp-url or set MCP_URL");
  process.exit(1);
}

const server = new GcsMcpBridgeServer(config);

process.on("SIGINT", () => { server.stop(); process.exit(0); });
process.on("SIGTERM", () => { server.stop(); process.exit(0); });

server.start();
