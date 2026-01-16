/**
 * S3 MCP Bridge
 *
 * A bridge that tunnels MCP (Model Context Protocol) messages through Amazon S3.
 * This enables MCP connectivity in environments with restricted egress (like Claude Code cloud).
 *
 * Components:
 * - Client: Runs in the restricted environment, sends requests to S3
 * - Server: Runs on your infrastructure, polls S3 and forwards to real MCP server
 */

export { S3McpBridgeClient } from "./client.js";
export { S3McpBridgeServer } from "./server.js";
