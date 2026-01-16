#!/usr/bin/env node
/**
 * GCS MCP Bridge - Client CLI
 *
 * Environment variables:
 *   GOOGLE_APPLICATION_CREDENTIALS - Path to service account JSON
 *   GCS_BUCKET - GCS bucket name
 *   GCS_PREFIX - Object prefix (default: mcp-relay)
 */

import { GcsMcpBridgeClient } from "./client.js";

function parseArgs() {
  const args = process.argv.slice(2);
  const config = {};

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--bucket" && args[i + 1]) config.bucket = args[++i];
    else if (args[i] === "--prefix" && args[i + 1]) config.prefix = args[++i];
    else if (args[i] === "--credentials" && args[i + 1]) config.keyFilename = args[++i];
    else if (args[i] === "--help") {
      console.log(`
GCS MCP Bridge Client

Usage: gcs-mcp-bridge [options]

Options:
  --bucket <name>      GCS bucket name (or set GCS_BUCKET)
  --prefix <prefix>    Object prefix (default: mcp-relay)
  --credentials <path> Path to service account JSON
  --help               Show this help

Environment:
  GCS_BUCKET                        Bucket name
  GCS_PREFIX                        Object prefix
  GOOGLE_APPLICATION_CREDENTIALS    Service account JSON path
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
  keyFilename: cli.keyFilename || process.env.GOOGLE_APPLICATION_CREDENTIALS
};

if (!config.bucket) {
  console.error("Error: GCS bucket required. Use --bucket or set GCS_BUCKET");
  process.exit(1);
}

const client = new GcsMcpBridgeClient(config);
client.start();
